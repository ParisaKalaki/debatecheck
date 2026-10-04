"""
Debate conclusion: a short, plain-language summary of the debate and its result.

Built ONLY from the debate transcript and the judge's verdict - no outside knowledge.
It restates the judge's decision in everyday language; it never re-judges the claim.
Returns None on failure so the rest of the response still works.

Test (from backend/):
    python -m app.agents.debate_summary
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.schemas import DebateConclusion, DebateTurn, JudgeVerdict

env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = os.getenv("SUMMARY_MODEL", "gemini-3.5-flash-lite")

# Removes citation IDs like "[E-123-4, E-123-5]" so they don't appear in plain-language text
ID_PATTERN = re.compile(r"\s*[\[(]\s*E-\d+-\d+(?:\s*,\s*E-\d+-\d+)*\s*[\])]")


class _SummaryOutput(BaseModel):
    answer: str
    summary: str
    caveat: Optional[str] = None


SUMMARY_PROMPT = """You write the final conclusion of a debate about a health claim, for a
non-expert reader.

CLAIM: "{claim}"

DEBATE TRANSCRIPT:
{transcript}

JUDGE'S VERDICT: {verdict}
JUDGE'S REASONING: {reasoning}
EVIDENCE GAPS NOTED BY THE JUDGE: {gap}

Write:
1. answer: one plain-language sentence that answers the claim and matches the judge's verdict
   (e.g. "Probably not - ...", "Yes, mostly - ...", "The evidence is split - ...").
2. summary: 2-3 sentences in plain language: the strongest point from each side, and why the
   judge sided as it did.
3. caveat: one sentence on the main limitation of the evidence, or null if there is none.

Rules:
- Use ONLY information from the transcript and the judge's verdict and reasoning above.
  Do not add facts, numbers, or studies from outside knowledge.
- Your answer must agree with the judge's verdict. Do not re-judge the claim.
- No citation IDs, no jargon (explain any technical term briefly), no medical advice.
- Keep the whole thing under 90 words.

Return JSON only."""


def _format_transcript(transcript: list[DebateTurn]) -> str:
    return "\n".join(f"{t.agent} (round {t.round}):\n{t.argument}" for t in transcript)


def _clean(text: Optional[str]) -> Optional[str]:
    return ID_PATTERN.sub("", text).strip() if text else text


def generate_conclusion(claim: str, transcript: list[DebateTurn], verdict: JudgeVerdict) -> DebateConclusion | None:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_SummaryOutput,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    prompt = SUMMARY_PROMPT.format(
        claim=claim,
        transcript=_format_transcript(transcript),
        verdict=verdict.verdict,
        reasoning=verdict.reasoning,
        gap=verdict.evidence_gap_note or "none",
    )
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
        out = _SummaryOutput.model_validate_json(response.text)
    except Exception as e:
        print(f"WARNING: debate conclusion failed ({type(e).__name__})")
        return None

    return DebateConclusion(
        answer=_clean(out.answer),
        summary=_clean(out.summary),
        caveat=_clean(out.caveat),
    )


if __name__ == "__main__":
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    debate = json.loads((tests_dir / "fixture_vitd_debate.json").read_text())
    verdict = JudgeVerdict(**json.loads((tests_dir / "fixture_vitd_verdict.json").read_text()))
    transcript = [DebateTurn(**t) for t in debate["transcript"]]
    print(generate_conclusion(debate["claim"], transcript, verdict))