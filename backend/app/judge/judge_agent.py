"""
Person 3: Judge agent.

Reads the full debate transcript (PRO/CON turns) plus the quality metadata
of every evidence snippet that was cited, and produces a single structured
verdict: JudgeVerdict (see app/core/schemas.py).

Runs on Groq (free tier). Uses Groq's native structured-output mode 
(response_format=json_schema, strict=True) to
get back JSON guaranteed to match the JudgeVerdict schema.

Test (from the backend/ folder):
    python -m app.judge.judge_agent
"""

import json
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import groq
from dotenv import load_dotenv

from app.core.schemas import DebateTurn, EvidenceSnippet, JudgeVerdict

# Load .env from the project root
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

# openai/gpt-oss-120b is OpenAI's open-weight reasoning model, served free via Groq's own hardware 
MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-oss-120b")


# ---------- Quality tiering (mirrors app/retrieval/quality_extractor.py's logic) ----------

QUALITY_TIER_NOTES = """
Evidence quality tiers, strongest to weakest (use this to weigh, not just count):
  1. systematic_review, meta_analysis   -- synthesizes many studies, strongest
  2. RCT                                -- randomized controlled trial, causal evidence
  3. cohort_study, clinical_trial       -- observational but structured, moderate
  4. pilot_trial, observational         -- smaller / less controlled
  5. case_report, narrative_review      -- weakest, anecdotal or non-systematic

Within a tier: larger sample_size and more recent pub_date both increase weight.
A study with sample_size=None or an unclear design should be treated as lower
confidence evidence, not ignored -- note that uncertainty in evidence_gap_note
if it affects the verdict.
"""


# ---------- Formatting helpers ----------

def format_transcript(transcript: list[DebateTurn]) -> str:
    lines = []
    for turn in transcript:
        lines.append(f"--- {turn.agent} | Round {turn.round} ---\n{turn.argument}\n")
    return "\n".join(lines)


def format_evidence_lookup(evidence: list[EvidenceSnippet]) -> str:
    """Full quality-metadata table for every snippet, keyed by ID, so the judge
    can look up the actual quality of anything either agent cited."""
    lines = []
    for e in evidence:
        lines.append(
            f"[{e.id}] stance={e.stance} | design={e.study_design or 'unknown'} | "
            f"n={e.sample_size if e.sample_size is not None else 'not stated'} | "
            f"year={e.pub_date or 'unknown'} | credibility={e.source_credibility or 'unknown'}\n"
            f"    \"{e.text}\""
        )
    return "\n".join(lines)

JUDGE_PROMPT = """You are the JUDGE in DebateCheck, a system that evaluates health claims by
reading a structured debate between a PRO agent (arguing the claim is true) and a CON agent
(arguing it is false). You did not participate in the debate -- you are an independent evaluator.

CLAIM: "{claim}"

FULL DEBATE TRANSCRIPT:
{transcript}

EVIDENCE QUALITY LOOKUP (every snippet either side cited, with its quality metadata):
{evidence_lookup}

{quality_tiers}

Your task:
1. Weigh each cited point by the QUALITY of its evidence, not by which side cited more snippets.
   A single well-powered RCT or systematic review can and should outweigh several small,
   low-quality, or outdated observational studies on the other side.
2. Check whether either agent overstated their evidence (e.g. presenting a small or
   low-certainty study as if it were definitive). Penalize overstated points in your reasoning.
3. top_counter_evidence is a devil's-advocate check on your OWN verdict, not a restatement
   of why you reached it. First decide your verdict direction (True-leaning or False-leaning).
   Then find the single strongest point RAISED BY THE OPPOSING SIDE of that direction -- i.e.
   the best evidence that argues you might be wrong. Example: if your verdict leans False
   (siding with CON), top_counter_evidence must be PRO's strongest point, not another CON
   point. Do not pick evidence that agrees with your own verdict here -- that would defeat
   the purpose of this field.
4. Note explicitly if the evidence on either side is thin, old, small-sample, or missing
   entirely for some aspect of the claim -- this becomes evidence_gap_note (use null if
   evidence coverage is genuinely solid on both sides).
5. Assess misinformation_risk: how risky would it be for a member of the public to believe
   this claim is settled, given what the evidence actually shows? High risk means confidently
   wrong or confidently overstated in a way that could cause real harm; Low risk means the
   claim is well-supported, or clearly a case of genuine ongoing scientific uncertainty that
   isn't being misrepresented.
6. Give a confidence score on a 0.0-1.0 scale: how confident are you that the verdict LABEL
   you chose (whichever of the 6 it is) is the right one for this evidence -- not "how likely
   is the claim true". This must work the same way for every label, including "Mixed / Unclear":
   a HIGH confidence "Mixed / Unclear" means you're sure the evidence is genuinely split or
   contested; a LOW confidence on any label (including "Mixed / Unclear") means a different
   label might actually fit better. Do not treat confidence as a measure of how true the claim
   is -- it measures how sure you are that your chosen label is the correct description of the
   evidence.
7. If a point in the transcript has no matching entry in the EVIDENCE QUALITY LOOKUP (its
   citation was invalid and got dropped, or nothing was cited for it), treat that point as
   UNVERIFIED -- you cannot check its quality, so do not weigh it as if it were backed
   evidence just because it reads persuasively. If this applies to most or all of the debate
   (the evidence lookup above is empty, or nearly empty, while the transcript still makes
   claims), that is itself the deciding factor: choose "Unverifiable" rather than judging
   based on which side's unsupported claims sound more convincing.

Length and tone:
- reasoning: 2-4 sentences maximum. State the strongest point on each side with its
  key number (e.g. sample size, effect size, certainty level), then your conclusion.
  Do not restate the full debate -- summarize only what drove your decision.
- risk_reason: 1-2 sentences maximum. State the risk level's cause directly, not a
  full argument.
- top_counter_evidence: 1 sentence maximum. State the single strongest opposing point
  and its source, without extra justification.
- evidence_gap_note: 1-2 sentences maximum, or null if coverage is genuinely solid.

Fill "reasoning" first, briefly, before the other fields -- walk through the quality
comparison explicitly (e.g. "PRO's strongest point is an RCT with n=X vs CON's three
observational studies with n<100 each, so..."). Then fill the remaining fields consistently
with that reasoning.
"""


# ---------- Rate-limit retry. Groq's free tier caps total tokens-per-minute (TPM)
#            across every call sharing the API key.
#            Instead of letting that crash the whole judge run, retry using the
#            wait time Groq itself reports. ----------

def _seconds_until_retry(error: groq.RateLimitError, default: float = 15.0) -> float:
    retry_after = error.response.headers.get("retry-after")
    if retry_after is not None:
        try:
            return float(retry_after) + 1  # small buffer
        except ValueError:
            pass
    # Fallback: Groq's error message includes text like "Please try again in XX.XXs."
    match = re.search(r"try again in ([\d.]+)s", str(error))
    if match:
        return float(match.group(1)) + 1
    return default


def _call_groq_with_retry(max_retries: int = 2, **kwargs):
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except groq.RateLimitError as e:
            if attempt == max_retries:
                raise  # out of retries -- let the real error surface
            wait_s = _seconds_until_retry(e)
            print(f"  [rate limited by Groq -- waiting {wait_s:.0f}s, retry {attempt + 1}/{max_retries}]")
            time.sleep(wait_s)


def judge_debate(claim: str, transcript: list[DebateTurn], evidence: list[EvidenceSnippet]) -> JudgeVerdict:
    # Only send quality metadata for snippets actually cited somewhere in the transcript. 
    cited_ids = {cid for turn in transcript for cid in turn.cited_ids}
    cited_evidence = [e for e in evidence if e.id in cited_ids]

    prompt = JUDGE_PROMPT.format(
        claim=claim,
        transcript=format_transcript(transcript),
        evidence_lookup=format_evidence_lookup(cited_evidence),
        quality_tiers=QUALITY_TIER_NOTES,
    )

    schema = JudgeVerdict.model_json_schema()
    # Groq's strict json_schema mode (like OpenAI's) wants no extra keys allowed,
    # AND every property listed in "required" -- even optional ones. Optionality
    # for evidence_gap_note is expressed by its "anyOf [string, null]" type instead,
    # not by leaving it out of "required" (which is what pydantic does by default).
    schema.pop("title", None)
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"].keys())

    response = _call_groq_with_retry(
        model=MODEL,
        temperature=0.2,  # low: consistency matters more than variety for a judge
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "judge_verdict",
                "description": "Structured verdict for this health claim debate.",
                "schema": schema,
                "strict": True,
            },
        },
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content
    return JudgeVerdict.model_validate(json.loads(raw))


# ---------- Tie-breaking for a split self-consistency vote. ----------
#
#   True (+2) -- Likely True (+1) -- Mixed/Unclear (0) -- Likely False (-1) -- False (-2)
#
# "Unverifiable" sits off this line entirely -- it doesn't mean "the truth is
# in the middle", it means the evidence couldn't support ANY placement on it.
VERDICT_POLARITY = {
    "True": 2,
    "Likely True": 1,
    "Mixed / Unclear": 0,
    "Likely False": -1,
    "False": -2,
}


def _resolve_majority(labels: list[str]) -> tuple[str, int, bool]:
    """Pick the winning verdict label out of n_runs self-consistency runs.

    Returns (winning_label, winning_count, synthesized). `synthesized` is
    True only for a genuine opposing-direction tie (see below) -- the one
    case where the returned label did NOT literally come from any single
    run, so the caller can't just look up a representative run by matching
    verdict text and has to build one instead.
    """
    counts = Counter(labels)
    max_count = max(counts.values())
    tied = [label for label, c in counts.items() if c == max_count]

    if len(tied) == 1:
        return tied[0], max_count, False

    # Multiple labels tied for first place. "Unverifiable" tied with
    # anything wins outright: it means at least one full run concluded the
    # evidence couldn't support ANY point on the true/false line at all,
    # which is a stronger signal than a strength disagreement among the rest.
    if "Unverifiable" in tied:
        return "Unverifiable", max_count, False

    polarities = [VERDICT_POLARITY[label] for label in tied]
    all_same_side = all(p >= 0 for p in polarities) or all(p <= 0 for p in polarities)

    if all_same_side:
        # Every tied label leans the same direction (e.g. "Likely False" vs
        # "False") -- the runs agree on WHICH WAY the evidence points, they
        # only disagree on how strongly. Report the most moderate of the
        # tied labels rather than an arbitrary pick.
        moderate_label = min(tied, key=lambda label: abs(VERDICT_POLARITY[label]))
        return moderate_label, max_count, False

    # Tied labels span both sides of the line (e.g. "True" vs "False", or
    # "Likely True" vs "Likely False") -- a genuine disagreement about
    # DIRECTION, not just degree. "Mixed / Unclear" is the honest call here.
    return "Mixed / Unclear", max_count, True


# ---------- STANDARD WAY TO CALL THE JUDGE. Instead of trusting one LLM call's
#            self-reported confidence, run the judge n_runs times on the SAME input and
#            use the fraction of runs that agree on the verdict as confidence instead. ----------

def judge_debate_with_confidence(
    claim: str,
    transcript: list[DebateTurn],
    evidence: list[EvidenceSnippet],
    n_runs: int = 4,
    verbose: bool = True,
) -> JudgeVerdict:
    with ThreadPoolExecutor(max_workers=n_runs) as pool:
        runs = list(pool.map(lambda _: judge_debate(claim, transcript, evidence), range(n_runs)))

    labels = [r.verdict for r in runs]
    majority_label, majority_count, synthesized = _resolve_majority(labels)
    agreement_rate = majority_count / n_runs

    if verbose:
        # Diagnostic only -- doesn't affect what's returned. One line: each verdict
        # label that came up, how many runs gave it, and THEIR OWN self-reported
        # confidence for each of those runs -- vs. agreement_rate at the end, which
        # is the number actually used as verdict.confidence below. Those two numbers
        # are different things (self-reported = the model's guess about itself;
        # agreement rate = how often independent runs actually landed on this label)
        # and can disagree, e.g. unanimous 3/3 runs whose own confidence still varies.
        # Set verbose=False to silence this (e.g. once called from an API route).
        by_label: dict[str, list[float]] = {}
        for r in runs:
            by_label.setdefault(r.verdict, []).append(r.confidence)
        groups = " | ".join(
            f"{label} x{len(confs)} (self-reported {', '.join(f'{c:.0%}' for c in confs)})"
            for label, confs in by_label.items()
        )
        tie_note = " [tie resolved]" if synthesized else ""
        print(
            f"Self-consistency ({n_runs} runs): {groups} -> verdict '{majority_label}'"
            f"{tie_note}, agreement confidence {agreement_rate:.0%}"
        )

    if synthesized:
        # Genuine opposing-direction tie (e.g. 2x "True", 2x "False") -- no
        # run produced "Mixed / Unclear" itself, so build a verdict that says
        # so honestly instead of borrowing one run's reasoning for a label
        # it never actually reached.
        label_counts = Counter(labels)
        tied_runs = [r for r in runs if label_counts[r.verdict] == majority_count]
        tied_labels_str = " vs ".join(sorted({r.verdict for r in tied_runs}))
        representative = tied_runs[0].model_copy(update={
            "verdict": "Mixed / Unclear",
            "reasoning": (
                f"Self-consistency check split {majority_count}/{n_runs} runs between "
                f"{tied_labels_str} with no majority direction, so this is reported as "
                f"Mixed / Unclear rather than arbitrarily picking a side. One individual "
                f"run's reasoning, for reference: {tied_runs[0].reasoning}"
            ),
        })
    else:
        # Representative verdict: the first run that actually produced the
        # winning label, so its reasoning / risk_reason / top_counter_evidence
        # text stays internally consistent with that label.
        representative = next(r for r in runs if r.verdict == majority_label)

    # Swap the model's single self-reported confidence for the measured
    # agreement rate. final_answer is a @computed_field on JudgeVerdict, so it
    # recalculates itself off this new confidence automatically.
    return representative.model_copy(update={"confidence": agreement_rate})


# ---------- Fixture loader -- reads an evidence file + a debate file from tests/ ----------

def load_fixture(evidence_filename: str, debate_filename: str):
    tests_dir = Path(__file__).resolve().parents[2] / "tests"

    evidence_raw = json.loads((tests_dir / evidence_filename).read_text())
    evidence = [EvidenceSnippet(**d) for d in evidence_raw]

    debate_raw = json.loads((tests_dir / debate_filename).read_text())
    claim = debate_raw["claim"]
    transcript = [DebateTurn(**t) for t in debate_raw["transcript"]]

    return claim, transcript, evidence


if __name__ == "__main__":
    # Real data: Person 1's live PubMed evidence + Person 2's live Gemini debate.
    claim, transcript, evidence = load_fixture("fixture_vitd.json", "fixture_vitd_debate.json")

    verdict = judge_debate_with_confidence(claim, transcript, evidence, n_runs=4)

    print(f"\nCLAIM: {claim}\n")
    print(f"{verdict.final_answer}\n")  # already states verdict + confidence in one line
    print(f"REASONING:\n{verdict.reasoning}\n")
    print(f"MISINFORMATION RISK: {verdict.misinformation_risk} -- {verdict.risk_reason}")
    print(f"STRONGEST COUNTER-EVIDENCE: {verdict.top_counter_evidence}")
    if verdict.evidence_gap_note:
        print(f"EVIDENCE GAP NOTE: {verdict.evidence_gap_note}")
