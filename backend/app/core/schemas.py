from pydantic import BaseModel, computed_field
from typing import Literal, Optional
 
 
class EvidenceSnippet(BaseModel):
    id: str
    text: str
    stance: Literal["support", "contradict", "neutral"]
    study_design: Optional[str] = None
    sample_size: Optional[int] = None
    pub_date: Optional[str] = None
    source_credibility: Optional[str] = None
    source_url: Optional[str] = None
 
 
class DebateTurn(BaseModel):
    agent: Literal["PRO", "CON"]
    round: int
    argument: str
    cited_ids: list[str]
 
 
_FINAL_ANSWER_PHRASES = {
    "True": "this claim is TRUE",
    "Likely True": "this claim is MOSTLY TRUE",
    "Mixed / Unclear": "this claim is PARTIALLY TRUE -- the evidence is genuinely mixed",
    "Likely False": "this claim is MOSTLY FALSE",
    "False": "this claim is FALSE",
    "Unverifiable": "this claim CANNOT BE VERIFIED with the available evidence",
}
 
 
class JudgeVerdict(BaseModel):
    reasoning: str
    verdict: Literal["True", "Likely True", "Mixed / Unclear", "Likely False", "False", "Unverifiable"]
    confidence: float
    misinformation_risk: Literal["Low", "Medium", "High"]
    risk_reason: str
    top_counter_evidence: str
    evidence_gap_note: Optional[str] = None
 
    @computed_field
    @property
    def final_answer(self) -> str:
        """One human-readable headline sentence, e.g. for a UI verdict card.
 
        Because this is a @computed_field, pydantic excludes it from
        JudgeVerdict.model_json_schema() (the schema sent to Groq for structured
        output) -- the model is never asked to fill it in -- but it IS included
        automatically in .model_dump() / .model_dump_json(), so any API response
        built from a JudgeVerdict carries it without extra wiring.
        """
        phrase = _FINAL_ANSWER_PHRASES[self.verdict]
        return f"Based on the evidence, {phrase} ({self.confidence:.0%} confidence)."


class ClaimAnalysis(BaseModel):
    """Output of the claim analyzer (app/retrieval/claim_analyzer.py)."""
    original_claim: str
    checkable_claim: str                 # same assertion, restated in testable scientific terms
    pubmed_query: str                    # query proposed by the analyzer
    intervention_terms: list[str]        # used by the relevance filter
    outcome_terms: list[str]
    search_query_used: Optional[str] = None   # query that actually returned results
    analysis_fallback: bool = False           # True if the analyzer failed and raw-claim fallback was used


class BackgroundExplainer(BaseModel):
    """Plain-language background answer from general medical knowledge.
    Shown separately from (and never merged into) the evidence-based JudgeVerdict."""
    headline: str
    takeaway: str
    explanation_points: list[str]
    misconception: Optional[str] = None
    differs_from_evidence_verdict: bool = False
    verdict_note: Optional[str] = None


class DebateConclusion(BaseModel):
    """Plain-language conclusion of the debate, built ONLY from the transcript and the
    judge's verdict (no outside knowledge). Never changes the verdict."""
    answer: str                    # one-sentence plain answer, consistent with the verdict
    summary: str                   # what each side argued and what decided it
    caveat: Optional[str] = None   # main limitation of the evidence