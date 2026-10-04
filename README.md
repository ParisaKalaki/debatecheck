# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, confidence score, misinformation risk level, and the strongest counter-evidence. The app also gives a plain-language quick answer and a plain-language conclusion of the debate.

A traditional NLP baseline (keyword retrieval + stance classifier) is built alongside for comparison.

> Course project — 36118 Applied Natural Language Processing, UTS, Spring 2026 (AT2)

> ⚠️ DebateCheck is an educational evidence-exploration tool. It does not give medical advice.

## Team Members

| Person | Student Name | Student ID |
|:------:|--------------|:----------:|
| Person 1 | Parisasadat Kalaki | 25969686 |
| Person 2 | Agam Singh Saini | 25531702 |
| Person 3 | Chenchira Bamrung | 26037349 |
| Person 4 | Ezgi Kemer Alp | 25510658 |
| Person 5 | Seyoung Kim | 25726050 |

---

## Quick Start (macOS and Windows)

### 1. Prerequisites

| What | Why | Get it |
|------|-----|--------|
| **Git** | to download the code | [git-scm.com/downloads](https://git-scm.com/downloads) |
| **Python 3.10 or newer** | runs the app (the team has used 3.14) | [python.org/downloads](https://www.python.org/downloads/) |
| **uv** | installs packages and creates the virtual environment | installed in step 3 below |

### 2. Get your API keys (all free)

| Key in `.env` | What it is | Where to get it |
|---------------|-----------|-----------------|
| `NCBI_EMAIL` | Not a key — just your email address. PubMed requires it to identify who is calling. | Use your own email |
| `NCBI_API_KEY` | *Optional.* Raises the PubMed rate limit. | [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/) → sign in → Account Settings → API Key Management |
| `GOOGLE_API_KEY` | Gemini — used for claim analysis, stance classification, debate agents, quick answer and conclusion | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key** |
| `GROQ_API_KEY` | Groq — used by the judge agent | [console.groq.com/keys](https://console.groq.com/keys) → **Create API Key** |

Never share these keys or commit your `.env` file (it is already in `.gitignore`).

### 3. Install

**macOS (Terminal)**

```bash
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

curl -LsSf https://astral.sh/uv/install.sh | sh     # install uv (restart Terminal afterwards)

uv venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt          # installs backend + frontend packages

cp .env.example .env
open -e .env                                        # opens .env in TextEdit to add your keys
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # install uv (restart PowerShell afterwards)

uv venv
.venv\Scripts\activate
uv pip install -r backend/requirements.txt          # installs backend + frontend packages

copy .env.example .env
notepad .env                                        # opens .env in Notepad to add your keys
```

> **Windows:** if `.venv\Scripts\activate` is blocked with a "running scripts is disabled" error, run this once and try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4. Fill in `.env`

```dotenv
NCBI_EMAIL=you@example.com
NCBI_API_KEY=
GOOGLE_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
ENVIRONMENT=development
```

### 5. Start the app (two terminals)

The app has two parts that run at the same time: a **backend** (FastAPI, does the work) and a **frontend** (Streamlit, the website). Open **two** terminal windows in the `debatecheck` folder and **activate the virtual environment in each one**.

**Terminal 1 — backend**

```bash
# macOS
source .venv/bin/activate
cd backend
uvicorn app.api.main:app --reload --port 8002
```

```powershell
# Windows
.venv\Scripts\activate
cd backend
uvicorn app.api.main:app --reload --port 8002
```

Wait for `Application startup complete`. You can check it is running at <http://127.0.0.1:8002/health>.

**Terminal 2 — frontend** (from the `debatecheck` root folder, not `backend/`)

```bash
# macOS
source .venv/bin/activate
streamlit run frontend/app.py
```

```powershell
# Windows
.venv\Scripts\activate
streamlit run frontend/app.py
```

Your browser opens <http://localhost:8501> automatically. If it doesn't, open that link yourself.

To stop the app, press `Ctrl + C` in both terminals.

### 6. Demo mode (no API calls)

To try the interface without using any API quota, add this line to `.env` and restart the backend:

```dotenv
DEBATECHECK_USE_FIXTURE=true
```

Every claim then returns the saved vitamin D example instantly. Set it back to `false` (or delete the line) for real results.

---

## Using the app

1. **Enter a health claim** in the text box, e.g. *"Vitamin D supplements prevent respiratory infections"* or *"Vitamin D is present in the sun during the entire day"*.
2. Click **Verify Health Claim**.
3. **Wait.** A live run searches PubMed and makes several AI calls, so it can take a minute or more. If the judge hits Groq's free-tier rate limit, it waits and retries automatically (see *Groq free-tier rate limit* below).

### Reading the results (top to bottom)

| Section | What it shows |
|---------|---------------|
| **Quick Answer • General Medical Knowledge** (amber card) | A plain-language answer from the AI's general medical knowledge. It is **not** based on the retrieved studies, and it says so if it disagrees with the evidence-based verdict. |
| **Checked against the evidence as / PubMed search used** | How the claim was rephrased into a testable statement, and the exact PubMed query used. |
| **Live Evidence Debate** | PRO argues the claim is true, CON argues it is false, over two rounds. Every point links to its PubMed source (**Source ↗**). |
| **Moderator Ruling** | The judge's verdict, consensus agreement (how many independent judge runs agreed) and misinformation risk. |
| **Debate Conclusion • In Plain Language** (green card) | A short plain-language summary of the debate and its result, built only from the debate and the verdict. |
| **Detailed Clinical Dossier** | Expandable sections: risk explanation and evidence limitations, the judge's reasoning, the strongest evidence *against* the verdict, and every retrieved PubMed snippet (filterable by support / contradict / neutral) with study design, sample size, year and credibility. |

If no relevant PubMed evidence is found, the app shows the quick answer plus a notice that the claim is **unverifiable with the available PubMed evidence**, instead of a debate.

### Tips for good results

- Make the claim **specific and about human health**: name the intervention and the outcome (*"X improves/prevents/causes Y"*).
- Very new or niche topics may have little PubMed evidence, which gives *Mixed* or *Unverifiable* results. That is an honest outcome, not an error.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` (e.g. `No module named 'groq'`) | The virtual environment isn't active, or packages are out of date. Activate it and run `uv pip install -r backend/requirements.txt` again (do this after every `git pull` that changes requirements). |
| `uv` / `streamlit` / `uvicorn` "not recognized" or "command not found" | Restart the terminal after installing uv, and make sure the virtual environment is activated. |
| **"Could not connect to the backend"** in the app | Terminal 1 (backend) isn't running or crashed. Start it and check <http://127.0.0.1:8002/health>. |
| "Backend returned 500" | Check Terminal 1 for the error. Usually a missing or wrong key in `.env`. |
| Very slow run, or `rate limited by Groq` in Terminal 1 | Expected on Groq's free tier. Wait between claims. |
| Port 8002 already in use | Start the backend on another port (e.g. `--port 8003`) and tell the frontend: macOS `export DEBATECHECK_API_URL=http://127.0.0.1:8003`, Windows `$env:DEBATECHECK_API_URL="http://127.0.0.1:8003"`, then run Streamlit in that same terminal. (This variable is read from the terminal, not from `.env`.) |
| Import errors when running a single file | Run modules from `backend/` with `python -m ...` (see below), not `python file.py`. |

---

## How to run individual components (development/testing)

All code uses package imports (`from app.retrieval... import ...`), so **always run from the `backend/` folder using `python -m`**:

```bash
cd backend
python -m app.retrieval.claim_analyzer        # claim → checkable claim + PubMed query
python -m app.retrieval.evidence_pipeline     # evidence retrieval test
python -m app.baseline.nli_classifier         # traditional baseline test
python -m app.agents.debate_graph             # debate agents test (uses saved fixture)
python -m app.judge.judge_agent               # judge agent test (uses saved fixture)
python -m app.agents.explainer                # quick-answer (background) test
python -m app.agents.debate_summary           # debate conclusion test (uses saved fixtures)
```

Running a file directly (e.g. `python evidence_pipeline.py` from inside `retrieval/`) will fail with import errors.

### Optional `.env` settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBATECHECK_USE_FIXTURE` | `false` | `true` = demo mode with saved results, no API calls |
| `DEBATE_MODEL` | `gemini-3.5-flash-lite` | Debate agents model |
| `ANALYZER_MODEL` | `gemini-3.5-flash-lite` | Claim analyzer model |
| `EXPLAINER_MODEL` | `gemini-3.5-flash-lite` | Quick-answer model |
| `SUMMARY_MODEL` | `gemini-3.5-flash-lite` | Debate conclusion model |
| `JUDGE_MODEL` | `openai/gpt-oss-120b` | Judge model (Groq) |

---

## Repo structure

- `backend/app/retrieval/` evidence pipeline incl. claim analyzer — DONE (Person 1, Person 2)
- `backend/app/baseline/` traditional NLP baseline — DONE (Person 1)
- `backend/app/agents/` debate agents, quick-answer explainer, debate conclusion — DONE (Person 2)
- `backend/app/judge/` judge agent — DONE (Person 3)
- `backend/app/api/` FastAPI routes — DONE (Person 4)
- `backend/app/core/` shared schemas (used by everyone)
- `backend/tests/` saved test fixtures (real pipeline outputs)
- `frontend/` web app — DONE (Person 4, Person 1)
- `evaluation/` benchmarking — not started (Person 5)

## Full pipeline

```text
User claim
   ↓
Claim analyzer (Gemini)        → checkable claim + PubMed query + keywords
   ↓
Evidence pipeline              → PubMed search → relevance filter → snippets → quality metadata → stance
   ↓
PRO vs CON debate (LangGraph)  → 2 rounds, every point must cite a snippet ID
   ↓
Judge (Groq, 4 runs)           → verdict + agreement confidence + misinformation risk
   ↓
Debate conclusion (Gemini)     → plain-language summary of the debate result
Quick answer (Gemini)          → general-knowledge background, shown separately
   ↓
FastAPI /verify → Streamlit UI
```

## What's done

### Claim analyzer (`backend/app/retrieval/claim_analyzer.py`)

Turns a messy or loosely worded claim into:

- `checkable_claim`: the **same** assertion restated as something a study could measure (it never corrects the claim; that is the judge's job)
- `pubmed_query`: a PubMed boolean query that keeps the qualifiers the claim depends on (timing, dose, population)
- `intervention_terms` / `outcome_terms`: keywords for the relevance filter

If the analyzer fails, the pipeline falls back to searching the raw claim.

### Evidence pipeline (`backend/app/retrieval/`)

```python
from app.retrieval.evidence_pipeline import get_evidence_with_analysis, get_evidence_for_claim
analysis, evidence = get_evidence_with_analysis("vitamin D supplements prevent respiratory infections")
evidence = get_evidence_for_claim("vitamin D supplements prevent respiratory infections")   # evidence only
```

Returns `EvidenceSnippet` objects (id, text, stance, study_design, sample_size, pub_date, source_credibility, source_url).

- Search tries the most precise query first: analyzer query `AND humans[mh]` → analyzer query → raw claim. Results are sorted by PubMed relevance.
- The stance prompt is **claim-generic**: Gemini first identifies the claim's intervention and outcome, and a snippet must address both to be labelled `support` or `contradict`.

#### Example: Evidence Retrieval Pipeline

```text
Claim
"Vitamin D supplements prevent respiratory infections."
        ↓
Claim analyzer
Builds a PubMed query and intervention/outcome keywords
        ↓
PubMed search (humans only, sorted by relevance)
Returns PubMed IDs (PMIDs)
Example: ["42235406", "42143317", "42124073", ...]
        ↓
Fetch abstracts + PubMed metadata
Gets title, abstract, publication date, and study type
Example: "Systematic Review", "RCT", etc.
        ↓
Relevance filter
Paper must mention an intervention term AND an outcome term
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
result = run_debate(claim, evidence)   # evidence = output of the evidence pipeline
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
- Agents receive each snippet's quality metadata (study design, sample size, year, credibility), are told to prioritise higher-quality evidence, describe certainty exactly as the snippet states it, and say so when evidence doesn't actually address the claim.
- Agents speak in a conversational tone, with the rule that tone must never make a finding sound stronger than the snippet says.

### Quick answer / background explainer (`backend/app/agents/explainer.py`)

A short plain-language answer from **general medical knowledge** (headline, takeaway, 3–5 explanation points, common misconception). It is kept separate from the evidence-based verdict: it is labelled as background knowledge in the UI, never changes the verdict, and flags it (`differs_from_evidence_verdict`) when it disagrees.

### Debate conclusion (`backend/app/agents/debate_summary.py`)

A plain-language answer and summary of the debate, built **only** from the transcript and the judge's verdict (no outside knowledge). It must agree with the verdict.

| | Quick answer | Debate conclusion |
|---|---|---|
| Based on | General medical knowledge | Only the debate and the judge's verdict |
| Can disagree with the verdict? | Yes, and it says so | No, it must match the verdict |

### Judge agent (`backend/app/judge/`)

```python
from app.judge.judge_agent import judge_debate_with_confidence
verdict = judge_debate_with_confidence(claim, transcript, evidence, n_runs=4)   # transcript/evidence = debate_graph.run_debate() output
```

Returns a `JudgeVerdict`:

```text
{
  "reasoning": str,               # written FIRST, walks through the quality comparison
  "verdict": str,                 # "True" | "Likely True" | "Mixed / Unclear" | "Likely False" | "False" | "Unverifiable"
  "confidence": float,            # 0.0-1.0 -- confidence in the LABEL chosen
  "misinformation_risk": str,     # "Low" | "Medium" | "High"
  "risk_reason": str,
  "top_counter_evidence": str,    # strongest point from the side OPPOSING the verdict
  "evidence_gap_note": str | None,
  "final_answer": str,            # computed automatically, e.g. "Based on the evidence, this claim is MOSTLY FALSE (78% confidence)."
}
```

How it works:

```text
Debate transcript + evidence quality metadata (study_design, sample_size, pub_date, source_credibility)
        ↓
Evidence quality lookup table
Every cited snippet's quality metadata, keyed by ID, so the judge can check either side's citations
        ↓
Groq (openai/gpt-oss-120b), structured JSON output (response_format=json_schema, strict=True)
Weighs evidence by QUALITY (study design > sample size > recency)
        ↓
JudgeVerdict
reasoning fills in first, then verdict/confidence/risk/counter-evidence stay consistent with it
```

- Runs on **Groq**, free tier (`GROQ_API_KEY` in `.env`).
- `top_counter_evidence` is deliberately the strongest point from the side **opposing** the verdict.
- `confidence` measures how sure the judge is that its chosen **label** is correct — this works the same way for all 6 labels, including "Mixed / Unclear" (a confident "genuinely contested" vs. an unsure one). It's the **agreement rate across `n_runs` independent runs** (see "Self-consistency confidence" below), not a single self-reported number.
- `final_answer` isn't a separate LLM call — it's a `@computed_field` on `JudgeVerdict` (see schemas.py) that's computed automatically from verdict + confidence. Because it's just a lookup, it can never drift out of sync with those two fields, and Groq is never asked to generate it. It shows up automatically whenever a JudgeVerdict is serialized (`.model_dump()` / `.model_dump_json()`), so any API response built from one gets it for free.
- The judge only sends evidence quality metadata for snippets actually **cited** somewhere in the transcript, not Person 1's full evidence list. A debate transcript usually cites well under half of what gets retrieved, so including the rest would just burn prompt tokens for no benefit. On real fixtures, this cuts prompt size roughly in half.
- If Groq returns a rate-limit error, the judge automatically waits the time Groq reports and retries, up to twice, instead of crashing — this happens more often than you'd expect. See "Groq free-tier rate limit" below for details.

#### Evidence quality scoring

Before the judge ever sees a snippet, `study_design` is set from PubMed's own official PublicationType field when available (authoritative — curated by PubMed/NLM's indexers), falling back to regex matching on the snippet text (e.g. `"randomized controlled trial"`, `"cohort study"`) only when PubMed didn't provide one. `sample_size` is regex-only (no PubMed field for it), left `None` when nothing matches.

Two different quality scales get built from `study_design`, at different points in the pipeline:

**`source_credibility`** (`high` / `medium` / `low` / `unknown`) — set once, in `quality_extractor.py`, stored on the `EvidenceSnippet` itself, and shown to the judge as a quick-glance label alongside each citation:

| source_credibility | study_design                                             |
| ------------------ | -------------------------------------------------------- |
| high               | systematic_review, meta_analysis, RCT                    |
| medium             | cohort_study, clinical_trial, pilot_trial, observational |
| low                | case_report, narrative_review                            |
| unknown            | no study design could be determined                      |

**`QUALITY_TIER_NOTES`** — a separate, finer-grained ordering baked directly into the judge's prompt (`judge_agent.py`), which is what the judge is actually told to weigh evidence by:

| tier          | study_design                     | note                                   |
| ------------- | -------------------------------- | -------------------------------------- |
| 1 (strongest) | systematic_review, meta_analysis | synthesizes many studies               |
| 2             | RCT                              | randomized, causal evidence            |
| 3             | cohort_study, clinical_trial     | observational but structured, moderate |
| 4             | pilot_trial, observational       | smaller / less controlled              |
| 5 (weakest)   | case_report, narrative_review    | anecdotal or non-systematic            |

Both use the same underlying ordering — the standard evidence-hierarchy pyramid from evidence-based medicine (synthesis > randomized > observational > anecdotal), so the ordering itself is a common, recognized one, just a simplification of a full grading system like GRADE or Oxford CEBM. The difference is granularity: `source_credibility` collapses tiers 1+2 into "high" and tiers 3+4 into "medium," while `QUALITY_TIER_NOTES` keeps all 5 separate. The judge's prompt also adds _"within a tier, larger sample_size and more recent pub_date both increase weight,"_ which lets it rank two studies at the same tier.

Since both `study_design` detection and `sample_size` extraction are regex-based fallbacks, not guaranteed — a study design phrased unusually can come back `unknown`/`None`. The judge is explicitly told to treat that as lower-confidence evidence rather than ignore it, and to flag it in `evidence_gap_note` if it affects the verdict.

#### Self-consistency confidence

`judge_debate_with_confidence(claim, transcript, evidence, n_runs=4)` is the decided way to call the judge, not `judge_debate` directly. Instead of trusting one self-reported confidence number, it runs the judge `n_runs` times in parallel and uses the **fraction of runs that agree on the verdict** as confidence — e.g. "this verdict held on 3 of 4 independent runs" is a real, code-computed number, not the model's self-assessment.

`judge_debate(claim, transcript, evidence)` — a single call, no self-consistency — still exists in `judge_agent.py` as the function `judge_debate_with_confidence` is built on.

#### Groq free-tier rate limit

Groq's free tier caps total token usage at **8000 tokens-per-minute (TPM)** per API key, shared across _every_ call the judge makes, including all `n_runs=4` calls `judge_debate_with_confidence` fires at once. This is a real, hard ceiling and it's easy to hit in normal use, not just edge cases:

- Calling the judge many times in quick succession (e.g. testing several different claims within a minute or two) can trigger a `429` rate-limit error.
- `judge_debate`'s automatic retry (`_call_groq_with_retry`) waits the time Groq itself reports and retries up to twice, so a single hit usually recovers on its own — but that wait has been anywhere from ~45 seconds to several minutes on real runs, depending on how far over the limit the request was.
- Practical guidance: don't run several different new claims back to back without a short pause between them. A multi-minute wait mid-run is expected behavior on the free tier, not something to debug.
- This is specific to the free tier — Groq's paid tier raises the TPM limit considerably, which would remove this constraint entirely if the project ever needed to run many claims reliably in quick succession.

### Test fixtures (`backend/tests/`)

- `fixture_vitd.json` — real evidence output for the vitamin D claim
- `fixture_vitd_debate.json` — real debate transcript (input for the judge)
- `fixture_vitd_verdict.json` — real judge verdict (used by demo mode)

Use these to develop and test without calling PubMed/Gemini/Groq every time.

### Shared schema (`backend/app/core/schemas.py`)

Defines common data structures (`EvidenceSnippet`, `DebateTurn`, `JudgeVerdict`, `ClaimAnalysis`, `BackgroundExplainer`, `DebateConclusion`) so all components use the same format when passing information between them.

### Web Application (`backend/app/api/` and `frontend/`)

#### Backend — `POST /verify`

Request: `{"claim": "...", "retmax": 8}`

Response fields: `claim`, `analysis`, `verdict`, `transcript`, `evidence`, `citation_log`, `evidence_count`, `background`, `conclusion`.

```text
User health claim
        ↓
FastAPI /verify endpoint
        ↓
Analyse claim → retrieve relevant PubMed evidence
        ↓
No relevant evidence? → rule-based "Unverifiable" verdict (debate and judge skipped)
        ↓
Run PRO vs CON debate
        ↓
Judge evaluates the debate and evidence
        ↓
Debate conclusion + quick answer
        ↓
API returns everything to the frontend
```

> **Note for evaluation:** when `evidence_count == 0`, the verdict is rule-based, not produced by the judge. Its `confidence` and `misinformation_risk` are placeholders (the schema requires them), so exclude these rows from judge accuracy and calibration metrics and report them separately.

#### Frontend

```text
User enters a health claim
        ↓
Streamlit sends the claim to the FastAPI backend
        ↓
Quick answer (general knowledge) + how the claim was checked
        ↓
PRO and CON arguments as a live-style debate chat
        ↓
Moderator Ruling: verdict + consensus agreement + misinformation risk
        ↓
Debate Conclusion in plain language
        ↓
Detailed Clinical Dossier
Judge reasoning + limitations + strongest evidence against the verdict + PubMed literature
```

## Not yet started

Full PubHealth evaluation (Person 5).

## Git workflow

```bash
git checkout main
git pull
git checkout -b personX-your-part
# ...work, commit...
git push -u origin personX-your-part
# then open a pull request into main
```