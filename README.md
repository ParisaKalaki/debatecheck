# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, confidence score, misinformation risk level, and the strongest counter-evidence.

A traditional NLP baseline (keyword retrieval + stance classifier) is built alongside for comparison.

> Course project — 36118 Applied Natural Language Processing, UTS, Spring 2026 (AT2)

## Setup

```bash
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh                          # macOS/Linux
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows

uv venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
uv pip install -r backend/requirements.txt

cp .env.example .env                               # Windows: copy .env.example .env
# then fill in your own NCBI_EMAIL and GOOGLE_API_KEY in .env — never commit it
```

## How to run code (important)

All code uses package imports (`from app.retrieval... import ...`), so **always run from the `backend/` folder using `python -m`**:

```bash
cd backend
python -m app.retrieval.evidence_pipeline     # evidence retrieval test
python -m app.baseline.nli_classifier         # traditional baseline test
python -m app.agents.debate_graph             # debate agents test (uses saved fixture)
```

Running a file directly (e.g. `python evidence_pipeline.py` from inside `retrieval/`) will fail with import errors.

## Repo structure

- `backend/app/retrieval/` evidence pipeline — DONE (Person 1)
- `backend/app/baseline/` traditional NLP baseline — DONE (Person 1)
- `backend/app/agents/` debate agents — DONE (Person 2); judge — not started (Person 3)
- `backend/app/api/` FastAPI routes — not started (Person 4)
- `backend/app/core/` shared schemas (used by everyone)
- `backend/tests/` saved test fixtures (real pipeline outputs)
- `frontend/` web app — not started (Person 4)
- `evaluation/` benchmarking — not started (Person 5)

## What's done

### Evidence pipeline (`backend/app/retrieval/`)

```python
from app.retrieval.evidence_pipeline import get_evidence_for_claim
evidence = get_evidence_for_claim("vitamin D supplements prevent respiratory infections")
```

Returns a list of `EvidenceSnippet` objects (id, text, stance, study_design, sample_size, pub_date, source_credibility, source_url).

The stance prompt is **claim-generic**: Gemini first identifies the claim's intervention and outcome, and a snippet must address both to be labelled `support` or `contradict`.

#### Example: Evidence Retrieval Pipeline

```text
Claim
"Vitamin D supplements prevent respiratory infections."
        ↓
PubMed search
Sends the claim as a search query → returns PubMed IDs (PMIDs)
Example: ["42235406", "42143317", "42124073", ...]
        ↓
Potentially relevant papers
Candidate papers returned by PubMed
Example: papers about vitamin D + respiratory infections
        ↓
Fetch abstracts + PubMed metadata
Gets title, abstract, publication date, and study type
Example: "Systematic Review", "RCT", etc.
        ↓
Relevance filter
Checks whether the paper matches the claim
Example: vitamin D + respiratory infection → keep
         vitamin D + osteoporosis → remove
        ↓
Evidence snippets
Splits relevant abstracts into small pieces
Example: "Vitamin D supplementation reduces respiratory infections..."
        ↓
Study design / sample size / credibility
Adds information about the evidence
Example: systematic review | 31,521 participants | high
        ↓
Gemini
Classifies each snippet
Example: support / contradict / neutral
```

### Traditional baseline (`backend/app/baseline/nli_classifier.py`)

Uses a pretrained NLI model to classify each evidence snippet as support, contradict, or neutral, then combines the results using a simple majority vote. No LLM prompting or agents are used. This provides a simple traditional comparison point for the agentic system.

### Debate agents (`backend/app/agents/`)

```python
from app.agents.debate_graph import run_debate
result = run_debate(claim, evidence)   # evidence = output of get_evidence_for_claim
```

Returns:

```text
{
  "claim": str,
  "transcript": list[DebateTurn],   # 4 turns: PRO r1, CON r1, PRO r2, CON r2
  "citation_log": list[dict]        # per turn: dropped_points, invalid_ids
}
```

How it works:

```text
Evidence snippets
        ↓
Split into piles
PRO pile = support + neutral     CON pile = contradict + neutral
        ↓
Round 1 — Opening (LangGraph)
PRO argues TRUE from its pile → CON argues FALSE from its pile
        ↓
Round 2 — Rebuttal
Each agent sees the opponent's opening and may cite the opponent's
snippets to call out misrepresentation
        ↓
Citation enforcement
Every point must cite a valid snippet ID from the allowed evidence.
Invalid IDs are removed; points with no valid ID are dropped and logged.
        ↓
DebateTurn objects (shared schema) → passed to the judge
```

- `debate_agents.py` — prompts, Gemini calls (structured JSON output), citation enforcement
- `debate_graph.py` — LangGraph flow and `run_debate()` entry point
- Agents receive each snippet's quality metadata (study design, sample size, year, credibility) and are instructed to prioritise higher-quality evidence and not overstate certainty.
- Model can be changed via `DEBATE_MODEL` in `.env` (default: `gemini-3.5-flash-lite`).

### Test fixtures (`backend/tests/`)

- `fixture_vitd.json` — real evidence output for the vitamin D claim
- `fixture_vitd_debate.json` — real debate transcript (input for the judge, Person 3)

Use these to develop and test without calling PubMed/Gemini every time.

### Shared schema (`backend/app/core/schemas.py`)

Defines common data structures such as `EvidenceSnippet`, `DebateTurn`, and `JudgeVerdict`, so all components use the same format when passing information between them.

## Not yet started

Judge agent (Person 3), web app (Person 4), full PubHealth evaluation (Person 5).

## Git workflow

```bash
git checkout main
git pull
git checkout -b personX-your-part
# ...work, commit...
git push -u origin personX-your-part
# then open a pull request into main
```