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
    takeaway: str
    explanation_points: list[str]
    misconception: Optional[str] = None
    differs_from_evidence_verdict: bool
    verdict_note: Optional[str] = None


EXPLAINER_PROMPT = """You write a short, plain-language background explanation of a health claim
for a non-expert reader. It is shown SEPARATELY from an evidence-based verdict and is clearly
labelled as general medical knowledge, not as findings from the retrieved studies.

USER CLAIM: "{claim}"
CLAIM AS CHECKED: "{checkable_claim}"
EVIDENCE-BASED VERDICT (from a separate debate over retrieved PubMed studies): {verdict}

Write:
1. headline: one sentence that directly answers whether the claim is accurate, based on
   well-established medical knowledge.
2. takeaway: one or two sentences with the key practical point.
3. explanation_points: 3-5 short bullet points explaining the facts or mechanism behind the
   answer, in plain language. Briefly define any technical term you use.
4. misconception: if the claim rests on a misunderstanding (e.g. wrong mechanism or wording),
   state it in one sentence; otherwise null.
5. differs_from_evidence_verdict: true if well-established knowledge points in a meaningfully
   different direction from the evidence-based verdict above; otherwise false.
6. verdict_note: if differs_from_evidence_verdict is true, one sentence on the likely reason
   (e.g. the retrieved studies did not address the claim directly); otherwise null.

Rules:
- Only state facts that are well established in mainstream medicine. If something is
  uncertain or debated, say so instead of guessing.
- Do not cite specific studies or sources - you have none here.
- Do not adjust your explanation to agree with the verdict; report disagreement in verdict_note.
- Do not give personal medical advice or dosing instructions.
- Keep the whole answer under 150 words.

Return JSON only."""


def generate_background(claim: str, checkable_claim: str, verdict_label: str) -> BackgroundExplainer | None:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_ExplainerOutput,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    prompt = EXPLAINER_PROMPT.format(
        claim=claim, checkable_claim=checkable_claim, verdict=verdict_label
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