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