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

OPENING_PROMPT = """
You are the {agent} agent debating a health claim. Your role is to {role}.

Claim: "{claim}"

Use only the evidence snippets below (each with an ID, stance, and metadata).

{evidence}

Guidelines:
- Cite at least one snippet ID per point (IDs go in "cited_ids", not in the text).
- Do not fabricate data.
- Prioritize high‑quality evidence.
- Keep each point short (1‑2 sentences, under 30 words).

Tone: Speak like two smart colleagues chatting over coffee. Use first‑person ("I", "we") and a friendly, conversational style. Directly address the other debater (e.g., "I think you're right...", "Actually, here's what the data shows...").

Examples:
Stiff: "A systematic review and network meta-analysis of randomized controlled trials involving children under 18 years old found that high-dose vitamin D demonstrated the greatest potential effect in preventing respiratory infections compared to other nutritional supplements and placebo."
Conversational: "Based on this large review of clinical trials, I don't think this is harmless — high-dose vitamin D actually reduced kids' respiratory infections more than a placebo."

Return JSON: {{"points": [{{"text": "your point", "cited_ids": ["snippet_id"]}}]}}
"""

# Opening prompt defined above

REBUTTAL_PROMPT = """You are a {agent} debater. Your role is to {role} in this rebuttal round.

Claim: "{claim}"

Your evidence:
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

TONE & STYLE -- CONVERSATIONAL, FRIENDLY DEBATE:
Speak like a colleague over coffee. Directly address the opponent (e.g., "I think you're wrong about that...", "Actually, here's the thing...", "Hold on, you're only looking at half the picture..."). Keep points short (1-2 sentences, under 30 words).

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