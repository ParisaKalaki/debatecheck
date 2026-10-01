"""
Person 2: PRO and CON debate agents.

Each agent may only argue from its own evidence pile and must cite snippet IDs.
Internally the LLM returns a list of points (each with its own cited IDs).
Points with no valid citation are dropped before being joined into a DebateTurn.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.schemas import DebateTurn, EvidenceSnippet

# Load .env from project root (same approach as retrieval/stance_classifier.py)
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = os.getenv("DEBATE_MODEL", "gemini-3.5-flash-lite")

# Matches inline ID brackets like "[E-42143317-5]" or "[E-42143317-5, E-42143317-6]"
INLINE_ID_PATTERN = re.compile(r"\s*\[\s*E-\d+-\d+(?:\s*,\s*E-\d+-\d+)*\s*\]")


# ---------- Internal schemas (not shared with other components) ----------

class Point(BaseModel):
    text: str
    cited_ids: list[str]


class AgentOutput(BaseModel):
    points: list[Point]


ROLE = {
    "PRO": "argue that the claim is TRUE",
    "CON": "argue that the claim is FALSE",
}


# ---------- Prompts ----------

OPENING_PROMPT = """You are the {agent} agent in a structured debate about a health claim.
Your job is to {role}.

CLAIM: "{claim}"

You may ONLY use the evidence snippets below. Each snippet has an ID in square brackets,
followed by its stance and quality metadata.

{evidence}

Rules:
1. Every point MUST cite at least one snippet ID from the list above. Points without a valid ID are discarded.
2. Never invent studies, numbers, or findings that are not stated in the cited snippet.
3. Do not overstate evidence. If a study is observational, small, or its sample size is not stated, do not present it as definitive.
4. Prioritise higher-quality evidence (systematic reviews, meta-analyses, RCTs, large samples).
5. Use neutral snippets only if they genuinely help your side, and never misrepresent them.
6. Put snippet IDs ONLY in "cited_ids", NEVER inside the point text itself.
7. Describe certainty, effect size, and study quality accurately as the snippet states them (never turn "low-certainty" into "definitive").

TONE & STYLE -- SOUND LIKE A SMART HUMAN IN A REAL CONVERSATION:
Speak in the first person ("I", "we", "here's why", "look at"). Do NOT sound like a stiff academic literature review or a medical journal abstract. Phrase your points naturally, like two smart colleagues having an engaging debate over coffee. Keep each point to 1-2 punchy, readable sentences (under 30 words).

STUDY THESE EXAMPLES TO MATCH THE CONVERSATIONAL PATTERN:
Example 1:
- STIFF (DO NOT WRITE LIKE THIS): "A systematic review and network meta-analysis of randomized controlled trials involving children under 18 years old found that high-dose vitamin D demonstrated the greatest potential effect in preventing respiratory infections compared to other nutritional supplements and placebo."
- CONVERSATIONAL (WRITE LIKE THIS): "Based on this large review of clinical trials, I don't think this is harmless -- high-dose vitamin D actually showed a real effect at preventing respiratory infections in kids, more than other supplements or a placebo."

Example 2:
- STIFF (DO NOT WRITE LIKE THIS): "Clinical practice guideline synthesis demonstrates an inverse correlation between supplementation and acute pediatric respiratory morbidity."
- CONVERSATIONAL (WRITE LIKE THIS): "Major clinical guidelines back this up -- regular supplementation really does help protect kids from catching common respiratory infections."

Example 3:
- STIFF (DO NOT WRITE LIKE THIS): "Observational cohort analysis indicates statistically significant attenuation of breakthrough infection risk following mRNA vaccination in cholecalciferol-replete cohorts."
- CONVERSATIONAL (WRITE LIKE THIS): "When you look at real patient data, people taking regular vitamin D had noticeably fewer breakthrough infections after getting vaccinated."

Return JSON in this format:
{{"points": [{{"text": "your point", "cited_ids": ["snippet_id"]}}]}}
"""

REBUTTAL_PROMPT = """You are the {agent} agent in a structured debate about a health claim.
Your job is to {role}. This is the REBUTTAL round.

CLAIM: "{claim}"

YOUR EVIDENCE:
{own_evidence}

OPPONENT'S OPENING ARGUMENT:
{opp_argument}

EVIDENCE THE OPPONENT CITED:
{opp_evidence}

Rules:
1. Respond directly to the opponent's points. Point out where they overstated findings, ignored study limitations, or overlooked counter-evidence.
2. Every point MUST cite at least one ID from YOUR EVIDENCE or EVIDENCE THE OPPONENT CITED. Points without a valid ID are discarded.
3. Never invent studies, numbers, or findings not stated in the cited snippet.
4. Put snippet IDs ONLY in "cited_ids", NEVER inside the point text itself.
5. Describe certainty, effect size, and study quality accurately as the snippet states them.

TONE & STYLE -- DIRECT, LIVELY BACK-AND-FORTH SPOKEN DEBATE:
Sound like two smart people having a real, direct back-and-forth discussion -- not two people reading written reports aloud. Directly address the other agent in first and second person ("I think you're wrong about that," "Actually, here's the thing," "Hold on, you're only looking at half the picture"). Keep points crisp and conversational (1-2 sentences, under 30 words).

STUDY THESE EXAMPLES TO MATCH THE CONVERSATIONAL PATTERN:
Example 1:
- STIFF (DO NOT WRITE LIKE THIS): "Direct comparison meta-analysis has shown no statistically significant differences between low-dose vitamin D and placebo regarding the prevention of childhood respiratory infections."
- CONVERSATIONAL (WRITE LIKE THIS): "Actually, I think you're wrong about that -- a direct comparison study found no real difference between low-dose vitamin D and a placebo. The dose really matters here, and you're only looking at the high-dose result."

Example 2:
- STIFF (DO NOT WRITE LIKE THIS): "The opponent's assertion regarding universal prevention is undermined by Cochrane systematic review data demonstrating merely low-certainty evidence of modest effect size."
- CONVERSATIONAL (WRITE LIKE THIS): "You're overstating your case -- that Cochrane review you cited warns that the evidence is low-certainty and only found a slight drop in doctor visits."

Example 3:
- STIFF (DO NOT WRITE LIKE THIS): "The evidence cited by the affirmative is limited by observational methodology, which precludes causal attribution."
- CONVERSATIONAL (WRITE LIKE THIS): "Hold on -- that study was just observational, not a controlled trial. You can't claim vitamin D caused that outcome when other lifestyle factors weren't accounted for."

Return JSON in this format:
{{"points": [{{"text": "your point", "cited_ids": ["snippet_id"]}}]}}
"""


# ---------- Helpers ----------

def split_evidence(evidence: list[EvidenceSnippet]):
    """PRO gets support + neutral, CON gets contradict + neutral."""
    pro = [e for e in evidence if e.stance in ("support", "neutral")]
    con = [e for e in evidence if e.stance in ("contradict", "neutral")]
    return pro, con


def format_evidence(snippets: list[EvidenceSnippet]) -> str:
    if not snippets:
        return "(none)"
    lines = []
    for s in snippets:
        meta = (
            f"design={s.study_design or 'unknown'}, "
            f"n={s.sample_size if s.sample_size is not None else 'not stated'}, "
            f"year={s.pub_date or 'unknown'}, "
            f"credibility={s.source_credibility or 'unknown'}"
        )
        lines.append(f"[{s.id}] ({s.stance}; {meta}) {s.text}")
    return "\n".join(lines)


def _call_llm(prompt: str, retries: int = 2) -> AgentOutput:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AgentOutput,
        temperature=0.3,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    last_err = None
    for _ in range(retries):
        response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
        try:
            return AgentOutput.model_validate_json(response.text)
        except ValidationError as e:
            last_err = e
    raise RuntimeError(f"Agent returned invalid JSON after {retries} attempts: {last_err}")


def _enforce_citations(output: AgentOutput, allowed_ids: set[str]):
    """Keep only valid IDs per point; drop points left with no valid ID.
    Also strips any inline ID brackets the model put in the text (safety net)."""
    kept, dropped, invalid_ids = [], [], []
    for p in output.points:
        valid = [i for i in p.cited_ids if i in allowed_ids]
        invalid_ids.extend(i for i in p.cited_ids if i not in allowed_ids)
        clean_text = INLINE_ID_PATTERN.sub("", p.text).strip()
        if valid and clean_text:
            kept.append(Point(text=clean_text, cited_ids=valid))
        else:
            dropped.append(p)
    return kept, dropped, invalid_ids


def _to_turn(agent: str, rnd: int, points: list[Point]) -> DebateTurn:
    if not points:
        return DebateTurn(
            agent=agent, round=rnd,
            argument="No valid, evidence-backed points could be made.",
            cited_ids=[],
        )
    argument = "\n".join(f"- {p.text} [{', '.join(p.cited_ids)}]" for p in points)
    cited = list(dict.fromkeys(i for p in points for i in p.cited_ids))  # unique, ordered
    return DebateTurn(agent=agent, round=rnd, argument=argument, cited_ids=cited)


def _log(agent, rnd, dropped, invalid_ids) -> dict:
    return {
        "agent": agent,
        "round": rnd,
        "dropped_points": [p.model_dump() for p in dropped],
        "invalid_ids": invalid_ids,  # hallucinated/out-of-pile citations (useful for evaluation)
    }


# ---------- Public functions ----------

def opening(agent: str, claim: str, own: list[EvidenceSnippet]):
    if not own:
        turn = DebateTurn(agent=agent, round=1,
                          argument="No evidence was retrieved for this side.", cited_ids=[])
        return turn, _log(agent, 1, [], [])

    prompt = OPENING_PROMPT.format(
        agent=agent, role=ROLE[agent], claim=claim, evidence=format_evidence(own)
    )
    output = _call_llm(prompt)
    kept, dropped, invalid = _enforce_citations(output, {s.id for s in own})
    return _to_turn(agent, 1, kept), _log(agent, 1, dropped, invalid)


def rebuttal(agent: str, claim: str, own: list[EvidenceSnippet],
             opp_turn: DebateTurn, evidence_by_id: dict[str, EvidenceSnippet]):
    opp_evidence = [evidence_by_id[i] for i in opp_turn.cited_ids if i in evidence_by_id]
    prompt = REBUTTAL_PROMPT.format(
        agent=agent, role=ROLE[agent], claim=claim,
        own_evidence=format_evidence(own),
        opp_argument=opp_turn.argument,
        opp_evidence=format_evidence(opp_evidence),
    )
    output = _call_llm(prompt)
    allowed = {s.id for s in own} | {s.id for s in opp_evidence}
    kept, dropped, invalid = _enforce_citations(output, allowed)
    return _to_turn(agent, 2, kept), _log(agent, 2, dropped, invalid)