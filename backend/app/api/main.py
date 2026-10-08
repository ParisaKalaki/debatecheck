"""
DebateCheck - Person 4 FastAPI backend.

Run from the repository's backend/ folder:
        uvicorn app.api.main:app --reload --port 8002

Pipeline:
claim -> claim analysis -> PubMed evidence -> PRO/CON debate -> judge verdict
      -> background explainer (general knowledge, shown separately from the verdict)
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.debate_graph import run_debate
from app.agents.debate_summary import generate_conclusion
from app.agents.explainer import generate_background
from app.core.schemas import (
    BackgroundExplainer,
    ClaimAnalysis,
    DebateConclusion,
    DebateTurn,
    EvidenceSnippet,
    JudgeVerdict,
)
from app.judge.judge_agent import judge_debate_with_confidence
from app.retrieval.evidence_pipeline import get_evidence_with_analysis

# Explicitly load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=True)

# Set DEBATECHECK_USE_FIXTURE=true while testing the UI to avoid hitting rate limits.
USE_FIXTURE = os.getenv("DEBATECHECK_USE_FIXTURE", "false").lower() == "true"
print(f"[DebateCheck] USE_FIXTURE = {USE_FIXTURE}")

TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
FIXTURE_PATH = TESTS_DIR / "fixture_vitd_debate.json"
EVIDENCE_FIXTURE_PATH = TESTS_DIR / "fixture_vitd.json"
VERDICT_FIXTURE_PATH = TESTS_DIR / "fixture_vitd_verdict.json"

app = FastAPI(
    title="DebateCheck API",
    description="Evidence-grounded multi-agent health claim verification.",
    version="1.1.0",
)

# Suitable for local development. Restrict origins before a public deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClaimRequest(BaseModel):
    claim: str = Field(min_length=5, max_length=500)
    retmax: int = Field(default=8, ge=1, le=20)


class VerificationResponse(BaseModel):
    claim: str                                        # original user claim
    analysis: Optional[ClaimAnalysis] = None          # how the claim was checked (None in fixture mode)
    verdict: JudgeVerdict
    transcript: list[DebateTurn]
    evidence: list[EvidenceSnippet]
    citation_log: list[dict]
    evidence_count: int
    background: Optional[BackgroundExplainer] = None  # general knowledge, separate from verdict
    conclusion: Optional[DebateConclusion] = None     # plain-language summary of the debate result


def has_debatable_evidence(evidence: list[EvidenceSnippet]) -> bool:
    """A debate needs at least one snippet that actually supports or contradicts the claim.
    Neutral-only evidence (background, different outcome, etc.) is not enough to argue from."""
    return any(e.stance in ("support", "contradict") for e in evidence)


def no_evidence_verdict(papers_found: bool) -> JudgeVerdict:
    """Rule-based verdict used when there is no evidence to debate.
    Not produced by the judge LLM; the UI hides confidence and risk for this case.
    These rows can be identified by an empty transcript."""
    reason = (
        "PubMed studies were found, but none directly supported or contradicted this claim, "
        "so no evidence-based debate or judgement was possible."
        if papers_found else
        "No relevant PubMed studies were retrieved for this claim, so no evidence-based "
        "debate or judgement was possible."
    )
    return JudgeVerdict(
        reasoning=reason,
        verdict="Unverifiable",
        confidence=1.0,
        misinformation_risk="Medium",
        risk_reason="Risk could not be assessed because no relevant evidence was retrieved.",
        top_counter_evidence="None - no evidence was retrieved.",
        evidence_gap_note="The PubMed search returned no studies that address this claim directly.",
    )


@app.get("/")
def root():
    return {"name": "DebateCheck API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "use_fixture": USE_FIXTURE}


@app.post("/verify", response_model=VerificationResponse)
def verify_claim(request: ClaimRequest):
    claim = request.claim.strip()

    if not claim:
        raise HTTPException(status_code=400, detail="Claim cannot be empty.")

    try:
        if USE_FIXTURE:
            # ---- Fixture mode: zero API calls, instant response ----
            evidence = [EvidenceSnippet(**e) for e in json.loads(EVIDENCE_FIXTURE_PATH.read_text())]
            debate_raw = json.loads(FIXTURE_PATH.read_text())
            transcript = [DebateTurn(**t) for t in debate_raw["transcript"]]
            citation_log = debate_raw["citation_log"]
            verdict = JudgeVerdict(**json.loads(VERDICT_FIXTURE_PATH.read_text()))
            claim = debate_raw["claim"]
            analysis = None
            background = None
            conclusion = None

        else:
            # ---- Live mode: real pipeline ----
            analysis, evidence = get_evidence_with_analysis(claim, retmax=request.retmax)

            checked_claim = analysis.checkable_claim

            if not has_debatable_evidence(evidence):
                # Nothing supports or contradicts the claim: skip debate + judge and return a
                # rule-based "Unverifiable" verdict. Retrieved papers are still returned for display.
                transcript, citation_log = [], []
                verdict = no_evidence_verdict(papers_found=bool(evidence))
                conclusion = None
            else:
                # Debate and judge work on the checkable version of the claim
                debate = run_debate(checked_claim, evidence)
                transcript = debate["transcript"]
                citation_log = debate["citation_log"]

                verdict = judge_debate_with_confidence(
                    claim=checked_claim, transcript=transcript, evidence=evidence, verbose=False,
                )

                # Plain-language conclusion of the debate (from transcript + verdict only)
                conclusion = generate_conclusion(checked_claim, transcript, verdict)

            # Separate, labelled one-line quick answer (never alters the verdict)
            background = generate_background(
                claim, checked_claim, verdict.verdict if transcript else None
            )

        return VerificationResponse(
            claim=claim,
            analysis=analysis,
            verdict=verdict,
            transcript=transcript,
            evidence=evidence,
            citation_log=citation_log,
            evidence_count=len(evidence),
            background=background,
            conclusion=conclusion,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Verification pipeline failed: {type(exc).__name__}.",
        ) from exc