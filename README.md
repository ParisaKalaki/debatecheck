# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, confidence score, misinformation risk level, and the strongest counter-evidence.

A traditional NLP baseline (keyword retrieval + stance classifier) is built alongside for comparison.

> Course project — 36118 Applied Natural Language Processing, UTS, Spring 2026 (AT2)

## Setup

```bash
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv
uv venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
uv pip install -r backend/requirements.txt

cp .env.example .env
# then fill in your own NCBI_EMAIL and GOOGLE_API_KEY in .env — never commit it
```

## Repo structure

- backend/app/retrieval/ evidence pipeline — DONE (Person 1)
- backend/app/baseline/ traditional NLP baseline — DONE (Person 1)
- backend/app/agents/ debate agents + judge — not started (Person 2, Person 3)
- backend/app/api/ FastAPI routes — not started (Person 4)
- backend/app/core/ shared schemas (used by everyone)
- frontend/ web app — not started (Person 4)
- evaluation/ benchmarking — not started (Person 5)

## What's done

**Evidence pipeline** (`backend/app/retrieval/`)

```python
from evidence_pipeline import get_evidence_for_claim
evidence = get_evidence_for_claim("vitamin D supplements prevent respiratory infections")
```

Returns a list of `EvidenceSnippet` objects (id, text, stance, study_design, sample_size, pub_date, source_credibility, source_url).

Internally: searches PubMed → filters irrelevant papers → chunks abstracts into snippets → tags each with study design/sample size/credibility (from PubMed's own metadata, falling back to regex) → classifies each as support/contradict/neutral via Gemini.

**Traditional baseline** (`backend/app/baseline/nli_classifier.py`) — pretrained zero-shot NLI model + majority vote, no LLM. This is the "traditional" comparison point against the agentic system.

**Shared schema** (`backend/app/core/schemas.py`) — `EvidenceSnippet`, `DebateTurn`, `JudgeVerdict` — import these instead of building your own dicts.

## Not yet started

Debate agents (Person 2), judge agent (Person 3), web app (Person 4), full PubHealth evaluation (Person 5).

## Git workflow

```bash
git checkout main
git pull
git checkout -b personX-your-part
# ...work, commit...
git push -u origin personX-your-part
# then open a pull request into main
```
