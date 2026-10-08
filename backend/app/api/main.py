"""
DebateCheck - Person 4 FastAPI backend.

Run from the repository's backend/ folder:
        uvicorn app.api.main:app --reload --port 8002

Pipeline:
claim -> claim analysis -> PubMed evidence -> PRO/CON debate -> judge verdict
      -> debate conclusion + one-line quick answer

Endpoints:
- POST /verify         full result in one response (used by evaluation)
- POST /verify/stream  same result, streamed as NDJSON progress events (used by the UI)
- GET  /config/status  which API keys are set
- POST /config/keys    set API keys from the UI (local requests only)
"""

import json
import os
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.debate_graph import run_debate
from app.agents.debate_summary import generate_conclusion
from app.agents.explainer import generate_background
from app.core.llm_clients import MissingAPIKeyError
from app.core.schemas import (
    BackgroundExplainer,
    ClaimAnalysis,
    DebateConclusion,
    DebateTurn,
    EvidenceSnippet,
    JudgeVerdict,
)
from app.core.settings import apply_keys, key_status, validate_keys
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

HEARTBEAT_SECONDS = 3   # stream sends a heartbeat this often so the UI never looks frozen
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}

app = FastAPI(
    title="DebateCheck API",
    description="Evidence-grounded multi-agent health claim verification.",
    version="1.2.0",
)

# Suitable for local development. Restrict origins before a public deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Models ----------

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
    background: Optional[BackgroundExplainer] = None  # one-line general-knowledge answer
    conclusion: Optional[DebateConclusion] = None     # plain-language summary of the debate result


class KeysRequest(BaseModel):
    ncbi_email: Optional[str] = None
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    ncbi_api_key: Optional[str] = None
    save_to_env: bool = True


# ---------- Helpers ----------

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


ProgressFn = Callable[[str, float], None]


def run_pipeline(claim: str, retmax: int, report: ProgressFn) -> VerificationResponse:
    """The full pipeline. report(message, fraction) is called at each step."""
    if USE_FIXTURE:
        report("Demo mode: loading the saved example...", 0.5)
        evidence = [EvidenceSnippet(**e) for e in json.loads(EVIDENCE_FIXTURE_PATH.read_text())]
        debate_raw = json.loads(FIXTURE_PATH.read_text())
        return VerificationResponse(
            claim=debate_raw["claim"],
            verdict=JudgeVerdict(**json.loads(VERDICT_FIXTURE_PATH.read_text())),
            transcript=[DebateTurn(**t) for t in debate_raw["transcript"]],
            evidence=evidence,
            citation_log=debate_raw["citation_log"],
            evidence_count=len(evidence),
        )

    analysis, evidence = get_evidence_with_analysis(claim, retmax=retmax, on_progress=report)
    checked_claim = analysis.checkable_claim

    if not has_debatable_evidence(evidence):
        # Nothing supports or contradicts the claim: skip debate + judge and return a
        # rule-based "Unverifiable" verdict. Retrieved papers are still returned for display.
        report("Not enough directly relevant research to hold a debate.", 0.85)
        transcript, citation_log = [], []
        verdict = no_evidence_verdict(papers_found=bool(evidence))
        conclusion = None
    else:
        report(f"Collected {len(evidence)} evidence snippets - starting the debate...", 0.52)
        debate = run_debate(checked_claim, evidence, on_progress=report)
        transcript = debate["transcript"]
        citation_log = debate["citation_log"]

        report("The judge is weighing the evidence (4 independent reviews)... "
               "this can take a minute on the free tier.", 0.80)
        verdict = judge_debate_with_confidence(
            claim=checked_claim, transcript=transcript, evidence=evidence, verbose=False,
        )

        report("Writing the plain-language conclusion...", 0.90)
        conclusion = generate_conclusion(checked_claim, transcript, verdict)

    report("Preparing the quick answer...", 0.95)
    background = generate_background(claim, checked_claim, verdict.verdict if transcript else None)

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


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, MissingAPIKeyError):
        return f"An API key is missing ({exc}). Add it in the app's API key setup panel."
    return f"Verification pipeline failed: {type(exc).__name__}."


def require_local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="API keys can only be set from this computer.")


# ---------- Routes ----------

@app.get("/")
def root():
    return {"name": "DebateCheck API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "use_fixture": USE_FIXTURE}


@app.get("/config/status")
def config_status():
    status = key_status()
    status["use_fixture"] = USE_FIXTURE
    if USE_FIXTURE:
        status["ready"] = True   # demo mode needs no keys
    return status


@app.post("/config/keys")
def config_keys(body: KeysRequest, request: Request):
    require_local(request)

    values = {
        name: value.strip()
        for name, value in {
            "NCBI_EMAIL": body.ncbi_email,
            "GOOGLE_API_KEY": body.google_api_key,
            "GROQ_API_KEY": body.groq_api_key,
            "NCBI_API_KEY": body.ncbi_api_key,
        }.items()
        if value and value.strip()
    }
    if not values:
        raise HTTPException(status_code=400, detail={"form": "Please enter at least one value."})

    errors = validate_keys(values)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    apply_keys(values, save_to_env=body.save_to_env)
    return config_status()


@app.post("/verify", response_model=VerificationResponse)
def verify_claim(request: ClaimRequest):
    claim = request.claim.strip()
    if not claim:
        raise HTTPException(status_code=400, detail="Claim cannot be empty.")
    try:
        return run_pipeline(claim, request.retmax, report=lambda message, fraction: None)
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=400, detail=friendly_error(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=friendly_error(exc)) from exc


@app.post("/verify/stream")
def verify_claim_stream(request: ClaimRequest):
    """Streams newline-delimited JSON events:
    {"type": "progress", "message": str, "progress": float}
    {"type": "heartbeat"}
    {"type": "result", "data": VerificationResponse}
    {"type": "error", "detail": str}
    """
    claim = request.claim.strip()
    if not claim:
        raise HTTPException(status_code=400, detail="Claim cannot be empty.")

    events: "queue.Queue[dict | None]" = queue.Queue()

    def report(message: str, fraction: float) -> None:
        events.put({"type": "progress", "message": message, "progress": round(fraction, 3)})

    def worker() -> None:
        try:
            result = run_pipeline(claim, request.retmax, report)
            report("Done!", 1.0)
            events.put({"type": "result", "data": result.model_dump(mode="json")})
        except Exception as exc:
            events.put({"type": "error", "detail": friendly_error(exc)})
        finally:
            events.put(None)  # end of stream

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            try:
                event = events.get(timeout=HEARTBEAT_SECONDS)
            except queue.Empty:
                yield json.dumps({"type": "heartbeat"}) + "\n"
                continue
            if event is None:
                break
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")