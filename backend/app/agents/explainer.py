"""
Background explainer: a short, plain-language answer from GENERAL MEDICAL KNOWLEDGE.

This is deliberately kept SEPARATE from the evidence-based verdict:
- it is labelled in the UI as general knowledge, not as findings from retrieved studies
- it never changes the judge's verdict
- if it disagrees with the verdict, it says so (differs_from_evidence_verdict + verdict_note)

Returns None on failure so the rest of the response still works.

Test (from backend/):
    python -m app.agents.explainer
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.schemas import BackgroundExplainer

env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = os.getenv("EXPLAINER_MODEL", "gemini-3.5-flash-lite")


class _ExplainerOutput(BaseModel):
    headline: str
    differs_from_evidence_verdict: bool
    verdict_note: Optional[str] = None


EXPLAINER_PROMPT = """You write a ONE-SENTENCE quick answer to a health claim for a non-expert
reader, based on well-established general medical knowledge. It is shown SEPARATELY from an
evidence-based debate verdict and is clearly labelled as general knowledge.

USER CLAIM: "{claim}"
CLAIM AS CHECKED: "{checkable_claim}"
EVIDENCE-BASED VERDICT (from a separate debate over retrieved PubMed studies): {verdict}

Write:
1. headline: ONE plain-language sentence (max 25 words) that directly answers whether the claim
   is accurate. If the claim rests on a misunderstanding, the sentence should gently correct it.
   No jargon.
2. differs_from_evidence_verdict: true only if a verdict is given above AND well-established
   knowledge points in a meaningfully different direction from it; otherwise false.
3. verdict_note: if differs_from_evidence_verdict is true, one short sentence on the likely
   reason (e.g. the retrieved studies did not cover the claim fully); otherwise null.

Rules:
- Only state what is well established in mainstream medicine; if it is genuinely uncertain, say so.
- Do not cite studies or sources. Do not adjust your answer to agree with the verdict.
- Do not give personal medical advice or dosing instructions.

Return JSON only."""


def generate_background(claim: str, checkable_claim: str, verdict_label: Optional[str]) -> BackgroundExplainer | None:
    """verdict_label=None means no debate was possible (no usable evidence)."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_ExplainerOutput,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    prompt = EXPLAINER_PROMPT.format(
        claim=claim, checkable_claim=checkable_claim,
        verdict=verdict_label or "none - no debate was possible for this claim",
    )
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
        out = _ExplainerOutput.model_validate_json(response.text)
    except Exception as e:
        print(f"WARNING: background explainer failed ({type(e).__name__})")
        return None

    return BackgroundExplainer(**out.model_dump())


if __name__ == "__main__":
    print(generate_background(
        "Vitamin D is present in the sun during entire day",
        "Sun exposure enables vitamin D synthesis in human skin at all times of day.",
        "Likely False",
    ))