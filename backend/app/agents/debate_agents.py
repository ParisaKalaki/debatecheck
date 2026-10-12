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
from app.core.llm_clients import get_gemini_client
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.schemas import DebateTurn, EvidenceSnippet

# Load .env from project root (same approach as retrieval/stance_classifier.py)
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

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

OPENING_PROMPT = """You are the {agent} agent debating a health claim. Your role is to {role}.

Claim: "{claim}"

Use ONLY the evidence snippets below (each has an ID, stance, and quality metadata).

{evidence}

Rules:
1. Every point MUST cite at least one snippet ID. IDs go ONLY in "cited_ids", never in the text.
   Points without a valid ID are discarded.
2. Never invent studies, numbers, or findings that are not stated in the cited snippet.
3. Do not overstate evidence. Describe certainty, effect size, and study quality exactly as the
   snippet states them (e.g. never turn "moderate-certainty" into "high-certainty", or a "trend"
   into a "significant" effect). If a study is observational, small, or its sample size is not
   stated, do not present it as definitive.
4. Prioritise higher-quality evidence (systematic reviews, meta-analyses, RCTs, large samples).
5. Use neutral snippets only if they genuinely help your side, and never misrepresent them.
6. If the evidence does not actually address the claim (e.g. a different population, outcome,
   or species), say so plainly instead of stretching it to fit your side.
7. Give 2-3 points, each 1-2 sentences and under 30 words.

Tone: speak like a smart colleague chatting over coffee - first person ("I", "we"), friendly
and plain, with no jargon unless you briefly explain it. Being conversational must never make
a finding sound stronger than the snippet says.

Example:
Stiff: "A systematic review and network meta-analysis of randomized controlled trials found that
high-dose vitamin D demonstrated the greatest potential effect in preventing respiratory infections."
Conversational: "A big review of clinical trials found high-dose vitamin D had the most potential
for preventing kids' respiratory infections - though it was a trend, not a definite effect."

Return JSON: {{"points": [{{"text": "your point", "cited_ids": ["snippet_id"]}}]}}
"""

REBUTTAL_PROMPT = """You are the {agent} debater. Your role is to {role} in this rebuttal round.

Claim: "{claim}"

Your evidence:
{own_evidence}

OPPONENT'S OPENING ARGUMENT:
{opp_argument}

EVIDENCE THE OPPONENT CITED:
{opp_evidence}

Rules:
1. Respond directly to the opponent's points. Point out where they overstated findings,
   ignored study limitations, or used evidence that does not actually address the claim.
2. Every point MUST cite at least one ID from YOUR EVIDENCE or EVIDENCE THE OPPONENT CITED.
   IDs go ONLY in "cited_ids", never in the text. Points without a valid ID are discarded.
3. Never invent studies, numbers, or findings not stated in the cited snippet.
4. Describe certainty, effect size, and study quality exactly as the snippet states them.
5. If your own evidence does not actually address the claim, admit it rather than stretching it.
6. Give 2-3 points, each 1-2 sentences and under 30 words.

Tone: conversational, friendly debate - speak like a colleague over coffee and address the
opponent directly (e.g. "Actually, here's the thing...", "Hold on, you're only looking at half
the picture..."). Being conversational must never make a finding sound stronger than the snippet says.

Examples:
- Stiff: "Direct comparison meta-analysis has shown no statistically significant differences
  between low-dose vitamin D and placebo."
  Conversational: "Actually, a direct comparison found no real difference between low-dose
  vitamin D and a placebo - you're only looking at the high-dose result."
- Stiff: "The evidence cited by the affirmative is limited by observational methodology."
  Conversational: "Hold on - that study was just observational, not a controlled trial, so it
  can't show vitamin D caused that outcome."

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
        response = get_gemini_client().models.generate_content(model=MODEL, contents=prompt, config=config)
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