"""
Step 0: Analyse the user's claim before retrieval.

Turns a messy (possibly misconceived) claim into:
- checkable_claim: the SAME assertion restated in precise, testable scientific terms
- pubmed_query: a PubMed boolean query for studies that test it
- intervention_terms / outcome_terms: keywords for the relevance filter

Returns None on failure; evidence_pipeline.py then falls back to the raw claim.

Test (from backend/):
    python -m app.retrieval.claim_analyzer
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.schemas import ClaimAnalysis

env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = os.getenv("ANALYZER_MODEL", "gemini-3.5-flash-lite")


class _AnalyzerOutput(BaseModel):
    checkable_claim: str
    pubmed_query: str
    intervention_terms: list[str]
    outcome_terms: list[str]


ANALYZER_PROMPT = """You prepare health claims for evidence retrieval from PubMed.

USER CLAIM: "{claim}"

Produce:
1. checkable_claim: restate the SAME assertion as a relationship a study could measure
   (exposure/intervention -> outcome, plus any condition such as timing, dose, or population).
   - If the wording is loose or scientifically imprecise, express the measurable relationship
     it implies, but keep exactly what the user asserts, including any part that may be wrong.
   - Never correct, soften, or reverse the claim - a later step checks whether it is true.
   Examples:
   "coffee dries you out" -> "Drinking coffee causes net dehydration in humans."
   "you can get a tan through a window" -> "UV exposure through window glass causes skin tanning in humans."
2. pubmed_query: a PubMed search query for studies that test this claim.
   - Use AND between the 2-3 core concepts, and OR between synonyms inside brackets.
   - KEEP any qualifier the claim depends on (timing, dose, duration, population, setting)
     and translate it into searchable medical terms
     (e.g. "all day" -> ("time of day" OR "time factors" OR season OR "solar zenith angle")).
   - Use standard medical terminology. Leave out words that carry no meaning for the claim.
   - Do not add filters such as humans[mh] or date limits.
3. intervention_terms: 2-6 lowercase keywords or synonyms for the exposure/intervention.
4. outcome_terms: 2-6 lowercase keywords or synonyms for the outcome or health effect.
   Terms must be specific; avoid generic words like "health", "effect", "day", "people".

Return JSON only."""


def analyze_claim(claim: str) -> ClaimAnalysis | None:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_AnalyzerOutput,
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    try:
        response = client.models.generate_content(
            model=MODEL, contents=ANALYZER_PROMPT.format(claim=claim), config=config
        )
        out = _AnalyzerOutput.model_validate_json(response.text)
    except Exception as e:  # network, quota, or invalid JSON -> caller falls back
        print(f"WARNING: claim analysis failed ({type(e).__name__}); using raw-claim fallback")
        return None

    return ClaimAnalysis(
        original_claim=claim,
        checkable_claim=out.checkable_claim.strip(),
        pubmed_query=out.pubmed_query.strip(),
        intervention_terms=[t.lower().strip() for t in out.intervention_terms if t.strip()],
        outcome_terms=[t.lower().strip() for t in out.outcome_terms if t.strip()],
    )


if __name__ == "__main__":
    for c in ["Vitamin D is present in the sun during entire day",
              "vitamin D supplements prevent respiratory infections"]:
        print(analyze_claim(c), "\n")