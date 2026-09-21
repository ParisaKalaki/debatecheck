from pydantic import BaseModel
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


class JudgeVerdict(BaseModel):
    verdict: str
    confidence: float
    misinformation_risk: Literal["Low", "Medium", "High"]
    risk_reason: str
    top_counter_evidence: str
    evidence_gap_note: Optional[str] = None
