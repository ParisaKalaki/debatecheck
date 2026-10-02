"""
DebateCheck - Person 4 FastAPI backend.

Run from the repository's backend/ folder:
    uvicorn app.api.main:app --reload

This API connects the completed Person 1 -> Person 2 -> Person 3 pipeline:
claim -> PubMed evidence -> PRO/CON debate -> judge verdict.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.debate_graph import run_debate
from app.core.schemas import DebateTurn, EvidenceSnippet, JudgeVerdict
from app.judge.judge_agent import judge_debate_with_confidence
from app.retrieval.evidence_pipeline import get_evidence_for_claim
import json
from pathlib import Path
import os
from dotenv import load_dotenv

# Explicitly load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=True)

# Set to True while testing the UI to avoid hitting rate limits.
# Set back to False before final submission/demo.
USE_FIXTURE = os.getenv("DEBATECHECK_USE_FIXTURE", "false").lower() == "true"
print(f"[DebateCheck] USE_FIXTURE = {USE_FIXTURE}")



FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixture_vitd_debate.json"
EVIDENCE_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixture_vitd.json"
VERDICT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixture_vitd_verdict.json"

app = FastAPI(
    title="DebateCheck API",
    description="Evidence-grounded multi-agent health claim verification.",
    version="1.0.0",
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
    claim: str
    verdict: JudgeVerdict
    transcript: list[DebateTurn]
    evidence: list[EvidenceSnippet]
    citation_log: list[dict]
    evidence_count: int


@app.get("/")
def root():
    return {
        "name": "DebateCheck API",
        "status": "running",
        "docs": "/docs",
    }


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
            evidence_raw = json.loads(EVIDENCE_FIXTURE_PATH.read_text())
            evidence = [EvidenceSnippet(**e) for e in evidence_raw]

            debate_raw = json.loads(FIXTURE_PATH.read_text())
            transcript = [DebateTurn(**t) for t in debate_raw["transcript"]]
            citation_log = debate_raw["citation_log"]

            verdict = JudgeVerdict(**json.loads(VERDICT_FIXTURE_PATH.read_text()))
            claim = debate_raw["claim"]

        else:
            # ---- Live mode: real pipeline ----
            evidence = get_evidence_for_claim(claim, retmax=request.retmax)

            if not evidence:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "No sufficiently relevant PubMed evidence was retrieved for this "
                        "claim. Try rewriting the claim more specifically."
                    ),
                )

            debate = run_debate(claim, evidence)
            transcript = debate["transcript"]
            citation_log = debate["citation_log"]

            verdict = judge_debate_with_confidence(
                claim=claim, transcript=transcript, evidence=evidence, verbose=False,
            )

        return VerificationResponse(
            claim=claim,
            verdict=verdict,
            transcript=transcript,
            evidence=evidence,
            citation_log=citation_log,
            evidence_count=len(evidence),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Verification pipeline failed: {type(exc).__name__}.",
        ) from exc