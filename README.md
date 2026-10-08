# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, an agreement-based confidence score, a misinformation risk level, and the strongest counter-evidence. The app also gives a one-line quick answer and a plain-language conclusion of the debate.

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

| Key | What it is | Where to get it |
|-----|-----------|-----------------|
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
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # install uv (restart PowerShell afterwards)

uv venv
.venv\Scripts\activate
uv pip install -r backend/requirements.txt          # installs backend + frontend packages
```

> **Windows:** if `.venv\Scripts\activate` is blocked with a "running scripts is disabled" error, run this once and try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4. Add your keys

**Easiest: do it in the app.** Skip this step, start the app (step 5), and it shows a **one-time setup form** for any missing keys. Each key is checked before it is saved, and ticking *"Remember these keys on this computer"* saves them to `.env` for next time. You can change them later under **API keys** in the sidebar.

**Or edit `.env` yourself:**

```bash
cp .env.example .env        # macOS   (then: open -e .env)
copy .env.example .env      # Windows (then: notepad .env)
```

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

Wait for `Application startup complete`. You can check it is running at <http://127.0.0.1:8002/health>. The backend starts even if keys are missing.

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

### 6. Demo mode (no API calls, no keys needed)

To try the interface without using any API quota, add this line to `.env` and restart the backend:

```dotenv
DEBATECHECK_USE_FIXTURE=true
```

Every claim then returns the saved vitamin D example instantly, and the key setup screen is skipped. Set it back to `false` (or delete the line) for real results.

---

## Using the app

1. **Enter a health claim** in the search box, e.g. *"Vitamin D supplements prevent respiratory infections"* or *"Intermittent fasting increases longevity"*.
2. Click **Check claim**.
3. **Watch the progress.** A progress bar shows the current step and the elapsed time. Click **"Verifying your claim…"** to open the step-by-step log (searching PubMed, checking each study, each debate turn, the judge, the conclusion). A run usually takes 1–3 minutes; the timer keeps ticking during slow steps (e.g. when the judge waits on Groq's rate limit), so you can see it is still working.

### Reading the results (top to bottom)

| Section | What it shows |
|---------|---------------|
| **Quick Answer • General Medical Knowledge** | A **one-line** answer from the AI's general medical knowledge, with a pointer to read the Debate Conclusion for a more informed, evidence-based answer. Below it, a red ⚠️ note says it is AI-generated and not from the retrieved studies. If it disagrees with the debate result, a warning says so. |
| **Checked against the evidence as / PubMed search used** | How the claim was rephrased into a testable statement, and the exact PubMed query used. |
| **Judge's verdict** card | The verdict, a ring showing **agreement** (how many of 4 independent judge runs chose this verdict — not a probability that the claim is true), a plain-language answer, and how many sources were cited. |
| **Misinformation risk** card | Low / Medium / High on a scale, with the reason. |
| **Evidence by study quality** card | How many retrieved snippets came from each study type (strongest first), plus how many support vs contradict the claim. These are counts; the judge weighs quality, not counts. |
| **Debate Conclusion • In Plain Language** | A short summary of the debate and its result, built only from the debate and the verdict. |
| **The debate** | **PRO** and **CON** cards with numbered points for each round (opening, rebuttal). Every point has clickable source tags like `S3 · Randomised trial · n=31521 ↗`. The **Traceable sources** card lists each cited paper (S1, S2, …) with its study type, year and credibility dots. The debate is revealed turn by turn when a new result arrives. |
| **Strongest evidence against this verdict** (gold box) | The opposing side's best point, so you can judge whether the verdict could be wrong. |
| **Detailed Clinical Dossier** (collapsed) | The judge's reasoning and evidence limitations, and every retrieved PubMed snippet (filterable by support / contradict / neutral) with study design, sample size, year and credibility. |

**When there is nothing to debate.** If PubMed finds no studies, or none that directly **support or contradict** the claim, the debate is skipped. The app shows a plain-language notice (*"Not enough research to debate this claim"* or *"No research found for this claim"*) with tips for rephrasing, plus any loosely related studies it found.

### Tips for good results

- Make the claim **specific and about human health**: name the intervention and the outcome (*"X improves/prevents/causes Y"*).
- Very new or niche topics may have little PubMed evidence, which gives *Mixed* or *Unverifiable* results. That is an honest outcome, not an error.
- Groq's free tier is rate-limited, so leave a short pause between claims.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` (e.g. `No module named 'groq'`) | The virtual environment isn't active, or packages are out of date. Activate it and run `uv pip install -r backend/requirements.txt` again (do this after every `git pull` that changes requirements). |
| `uv` / `streamlit` / `uvicorn` "not recognized" or "command not found" | Restart the terminal after installing uv, and make sure the virtual environment is activated. |
| **"Can't reach the DebateCheck backend"** | Terminal 1 (backend) isn't running or crashed. Start it, check <http://127.0.0.1:8002/health>, then refresh the page. |
| **"An API key is missing"** | Open **API keys** in the sidebar and add it. |
| **"Could not verify this key – …"** when saving a key | The message after the dash is the real error from Google or Groq (e.g. invalid key, no internet). The full details are printed in Terminal 1. |
| "Backend returned 500" / "Verification pipeline failed" | Check Terminal 1 for the error. |
| Very slow run, or `rate limited by Groq` in Terminal 1 | Expected on Groq's free tier. The judge waits and retries automatically. |
| Port 8002 already in use | Start the backend on another port (e.g. `--port 8003`) and tell the frontend: macOS `export DEBATECHECK_API_URL=http://127.0.0.1:8003`, Windows `$env:DEBATECHECK_API_URL="http://127.0.0.1:8003"`, then run Streamlit in that same terminal. (This variable is read from the terminal, not from `.env`.) |
| Claim box doesn't have the navy styling | The styling needs a recent Streamlit version (`uv pip install -U streamlit`). Everything still works without it. |
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
python -m app.agents.explainer                # one-line quick answer test
python -m app.agents.debate_summary           # debate conclusion test (uses saved fixtures)
```

Running a file directly (e.g. `python evidence_pipeline.py` from inside `retrieval/`) will fail with import errors.

### Optional settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBATECHECK_USE_FIXTURE` | `false` | `true` = demo mode with saved results, no API calls or keys |
| `DEBATE_MODEL` | `gemini-3.5-flash-lite` | Debate agents model |
| `ANALYZER_MODEL` | `gemini-3.5-flash-lite` | Claim analyzer model |
| `EXPLAINER_MODEL` | `gemini-3.5-flash-lite` | Quick-answer model |
| `SUMMARY_MODEL` | `gemini-3.5-flash-lite` | Debate conclusion model |
| `JUDGE_MODEL` | `openai/gpt-oss-120b` | Judge model (Groq) |
| `DEBATECHECK_API_URL` | `http://127.0.0.1:8002` | Backend address used by the frontend. Set in the **terminal**, not `.env`. |

All except `DEBATECHECK_API_URL` go in `.env`.

---

## Repo structure

- `backend/app/retrieval/` evidence pipeline incl. claim analyzer — DONE (Person 1, Person 2)
- `backend/app/baseline/` traditional NLP baseline — DONE (Person 1)
- `backend/app/agents/` debate agents, quick-answer explainer, debate conclusion — DONE (Person 2)
- `backend/app/judge/` judge agent — DONE (Person 3)
- `backend/app/api/` FastAPI routes incl. streaming and key setup — DONE (Person 4, Person 2)
- `backend/app/core/` shared schemas, lazy API clients (`llm_clients.py`), key settings (`settings.py`)
- `backend/tests/` saved test fixtures (real pipeline outputs)
- `frontend/` Streamlit web app — DONE (Person 4, Person 1, Person 2)
- `evaluation/` benchmarking — not started (Person 5)

## Full pipeline

```text
User claim
   ↓
Claim analyzer (Gemini)        → checkable claim + PubMed query + keywords
   ↓
Evidence pipeline              → PubMed search → relevance filter → snippets → quality metadata → stance
   ↓
Any snippet that supports or contradicts the claim?
   ├─ No  → rule-based "Unverifiable" (debate and judge skipped)
   └─ Yes ↓
PRO vs CON debate (LangGraph)  → 2 rounds, every point must cite a snippet ID
   ↓
Judge (Groq, 4 runs)           → verdict + agreement confidence + misinformation risk
   ↓
Debate conclusion (Gemini)     → plain-language summary of the debate result
   ↓
Quick answer (Gemini)          → one-line general-knowledge answer, shown separately
   ↓
FastAPI /verify/stream (live progress) → Streamlit UI
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

Returns `EvidenceSnippet` objects (id, text, stance, study_design, sample_size, pub_date, source_credibility, source_url). `get_evidence_with_analysis` also takes an optional `on_progress(message, fraction)` callback, used for the live progress bar.

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
- `debate_graph.py` — LangGraph flow and `run_debate()` entry point (optional `on_progress` callback, called before each turn)
- Agents receive each snippet's quality metadata (study design, sample size, year, credibility), are told to prioritise higher-quality evidence, describe certainty exactly as the snippet states it, and say so when evidence doesn't actually address the claim.
- Agents speak in a conversational tone, with the rule that tone must never make a finding sound stronger than the snippet says.

### Quick answer (`backend/app/agents/explainer.py`)

A **one-sentence** answer from **general medical knowledge**. It is kept separate from the evidence-based verdict: it is labelled as general knowledge in the UI, never changes the verdict, points users to the evidence-based Debate Conclusion, and flags it (`differs_from_evidence_verdict` + `verdict_note`) when it disagrees. It is generated after the judge, so it can compare itself with the verdict.

### Debate conclusion (`backend/app/agents/debate_summary.py`)

A plain-language answer and summary of the debate, built **only** from the transcript and the judge's verdict (no outside knowledge). It must agree with the verdict.

| | Quick answer | Debate conclusion |
|---|---|---|
| Based on | General medical knowledge | Only the debate and the judge's verdict |
| Can disagree with the verdict? | Yes, and it says so | No, it must match the verdict |

Disagreement between the two usually means either the retrieved studies didn't fully cover the claim, or the AI's general knowledge is outdated or wrong. Neither is automatically right, which is why the app shows the disagreement instead of hiding it.

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

### Shared code (`backend/app/core/`)

- `schemas.py` — common data structures (`EvidenceSnippet`, `DebateTurn`, `JudgeVerdict`, `ClaimAnalysis`, `BackgroundExplainer`, `DebateConclusion`) so all components use the same format.
- `llm_clients.py` — Gemini and Groq clients are created **lazily**, the first time they are needed, using whatever key is set at that moment. So the backend starts even without keys, and keys entered in the UI work immediately without a restart.
- `settings.py` — checks which keys are set, validates new keys, applies them at runtime and optionally saves them to `.env`.

### Web Application (`backend/app/api/` and `frontend/`)

#### Backend endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /verify` | Full result in one response (use this for evaluation) |
| `POST /verify/stream` | Same result, streamed as newline-delimited JSON: `progress` events, a `heartbeat` every 3 s, then `result` (or `error`). Used by the UI for the live progress bar. |
| `GET /config/status` | Which API keys are set, and whether the app is ready |
| `POST /config/keys` | Validate and apply API keys from the UI, optionally saving them to `.env`. Only accepts requests from the same computer. |
| `GET /health` | Simple health check |

Request for `/verify` and `/verify/stream`: `{"claim": "...", "retmax": 8}`

Response fields: `claim`, `analysis`, `verdict`, `transcript`, `evidence`, `citation_log`, `evidence_count`, `background`, `conclusion`.

```text
User health claim
        ↓
Analyse claim → retrieve PubMed evidence          (progress reported at each step)
        ↓
No snippet supports or contradicts the claim? → rule-based "Unverifiable" verdict (debate and judge skipped)
        ↓
Run PRO vs CON debate                              (progress reported before each turn)
        ↓
Judge evaluates the debate and evidence
        ↓
Debate conclusion + one-line quick answer
        ↓
API returns everything to the frontend
```

> **Note for evaluation (Person 5):** when `transcript` is empty, the verdict is rule-based, not produced by the judge. Its `confidence` and `misinformation_risk` are placeholders (the schema requires them), so exclude these rows from judge accuracy and calibration metrics and report them separately (e.g. "X of 150 claims had no debatable evidence"). It is also worth measuring how often the quick answer disagrees with the verdict (`background.differs_from_evidence_verdict`), as an indicator of retrieval gaps.

> **Security:** `/config/keys` writes to `.env` and is limited to local requests. Remove it or add authentication before any public deployment.

#### Frontend (`frontend/app.py`)

```text
App opens → checks the backend and API keys
        ↓
Missing keys? → one-time setup form (keys validated, optionally saved to .env)
        ↓
User enters a health claim → "Check claim"
        ↓
Live progress bar + collapsible step-by-step log (from /verify/stream)
        ↓
Quick answer (one line) + how the claim was checked
        ↓
Summary cards: Judge's verdict (agreement ring) · Misinformation risk · Evidence by study quality
        ↓
Debate Conclusion in plain language
        ↓
The debate: PRO card · CON card · Traceable sources (revealed turn by turn)
        ↓
Strongest evidence against this verdict
        ↓
Detailed Clinical Dossier: judge reasoning + limitations + PubMed literature (stance filter)
```

- Dashboard-style layout with a navy header and cream cards; cards set their own colours, so they are readable in both light and dark mode, and stack into one column on phones.
- Only real pipeline data is shown. The verdict ring is labelled **agreement** (it is the judge's agreement rate, not a probability), and the quality card shows **counts** per study type rather than invented weights.
- Sidebar: ✅/❌ status for each key and an *Add or update keys* form; it collapses after keys are set up successfully.

## Known limitations

- **Abstracts only, few papers.** Evidence comes from PubMed abstracts of up to 8 papers per claim, so important studies can be missed.
- **`humans[mh]` filter.** It excludes very recent papers that PubMed hasn't indexed yet. The pipeline falls back to an unfiltered search if the filtered one finds nothing.
- **Valid citations ≠ faithful citations.** Every debate point must cite a real snippet ID, but an agent can still overstate what a snippet says. The prompts and the judge reduce this, but don't eliminate it.
- **`humanize_text()` in the frontend** rewrites some agent wording for readability (several rules are specific to vitamin D), which can occasionally change nuance.
- **Placeholder values for "Unverifiable" results** (see the evaluation note above).
- **Groq free-tier rate limits** can add multi-minute waits.
- **Cost per claim:** roughly 1 analyzer + 1 stance call per relevant paper + 4 debate calls + 1 conclusion + 1 quick answer (Gemini), and 4 judge calls (Groq).

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