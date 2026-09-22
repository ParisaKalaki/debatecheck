# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, confidence score, misinformation risk level, and the strongest counter-evidence.

A traditional NLP baseline (keyword retrieval + stance classifier) is built alongside for comparison.

> Course project — 36118 Applied Natural Language Processing, UTS, Spring 2026 (AT2)

## How it works

CLAIM → RETRIEVE → ANALYSE → WEIGH → DEBATE → VERDICT

## Repo structure

- backend/app/retrieval — PubMed search, snippet chunking, quality metadata
- backend/app/agents — PRO, CON, JUDGE agent logic
- backend/app/baseline — traditional NLP baseline
- backend/app/api — FastAPI routes
- backend/app/core — shared config, schemas
- frontend — web app
- evaluation — benchmarking scripts and results
- docs — report drafts, poster assets

## Setup

git clone https://github.com/\<org\>/debatecheck.git
cd debatecheck
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

## Status

In development — AT2 due 14 October 2026.

## Progress Log

- Evidence retrieval pipeline (PubMed search, fetch, relevance filtering, 
  snippet chunking, quality metadata, stance classification) — DONE
- Traditional NLP baseline (pretrained NLI + majority vote) — DONE
- Entry point for other components: `get_evidence_for_claim(claim)` in 
  `backend/app/retrieval/evidence_pipeline.py`
