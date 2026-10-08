# DebateCheck

Multi-agent LLM system for evidence-grounded health claim verification. Two AI agents (PRO and CON) debate a submitted health claim using quality-weighted evidence retrieved from PubMed. A judge agent evaluates the debate and produces a verdict, confidence score, misinformation risk level, and the strongest counter-evidence.

A traditional NLP baseline (keyword retrieval + stance classifier) is built alongside for comparison.

> Course project — 36118 Applied Natural Language Processing, UTS, Spring 2026 (AT2)

## Team Members

| Person | Student Name | Student ID |
|:------:|--------------|:----------:|
| Person 1 | Parisasadat Kalaki | 25969686 |
| Person 2 | Agam Singh Saini | 25531702 |
| Person 3 | Chenchira Bamrung | 26037349 |
| Person 4 | Ezgi Kemer Alp | 25510658 |
| Person 5 | Seyoung Kim | 25726050 |

## Setup

```bash
git clone https://github.com/ParisaKalaki/debatecheck.git
cd debatecheck

# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh                          # macOS/Linux
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows

uv venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
# This installs both backend and frontend dependencies.
uv pip install -r backend/requirements.txt

cp .env.example .env                               # Windows: copy .env.example .env
# then fill in your own NCBI_EMAIL, GOOGLE_API_KEY, and GROQ_API_KEY in .env — never commit it
```

## How to run code (for development/testing individual components)

All code uses package imports (`from app.retrieval... import ...`), so **always run from the `backend/` folder using `python -m`**:

```bash
cd backend
python -m app.retrieval.evidence_pipeline     # evidence retrieval test
python -m app.baseline.nli_classifier         # traditional baseline test
python -m app.agents.debate_graph             # debate agents test (uses saved fixture)
python -m app.judge.judge_agent               # judge agent test (uses saved fixture)
```

Running a file directly (e.g. `python evidence_pipeline.py` from inside `retrieval/`) will fail with import errors.

## Run the web app (the full product, end to end)
Install the requirements for the environment: `uv pip install -r backend/requirements.txt`
Make sure your virtual environment is activated first: `source .venv/bin/activate` or `.venv\Scripts\activate`

Start the FastAPI backend from the `backend/` folder:

```bash
cd backend
uvicorn app.api.main:app --reload --port 8002
```

In a second terminal, from the repository root, start the Streamlit frontend:

```bash
streamlit run frontend/app.py
```

The frontend uses `http://127.0.0.1:8002` by default. Set `DEBATECHECK_API_URL` to use a different backend URL.

## Repo structure

- `backend/app/retrieval/` evidence pipeline — DONE (Person 1)
- `backend/app/baseline/` traditional NLP baseline — DONE (Person 1)
- `backend/app/agents/` debate agents — DONE (Person 2)
- `backend/app/judge/` judge agent — DONE (Person 3)
- `backend/app/api/` FastAPI routes — DONE (Person 4)
- `backend/app/core/` shared schemas (used by everyone)
- `backend/tests/` saved test fixtures (real pipeline outputs)
- `frontend/` web app — DONE (Person 4, Person 1)
- `evaluation/` PubHealth benchmarking, baseline comparison, and system evaluation — DONE (Person 5)

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
- `fixture_vitd_debate.json` — real debate transcript (input for the judge, Person 3)

Use these to develop and test without calling PubMed/Gemini every time.

### Shared schema (`backend/app/core/schemas.py`)

Defines common data structures such as `EvidenceSnippet`, `DebateTurn`, and `JudgeVerdict`, so all components use the same format when passing information between them.

### Web Application (`backend/app/api/` and `frontend/`)

#### How it works — Backend

```text
User health claim
        ↓
FastAPI /verify endpoint
        ↓
Retrieve relevant PubMed evidence
        ↓
Run PRO vs CON debate
        ↓
Judge evaluates the debate and evidence
        ↓
Judge returns verdict + confidence + misinformation risk
        ↓
API returns transcript, evidence and verdict to the frontend
```

#### How it works — Frontend

```text
User enters a health claim
        ↓
Streamlit sends the claim to the FastAPI backend
        ↓
Receive debate transcript + PubMed evidence + judge verdict
        ↓
Display PRO and CON arguments as a live-style debate chat
        ↓
Show Moderator Ruling
Verdict + Consensus Agreement + Misinformation Risk
        ↓
Detailed Clinical Dossier
Judge reasoning + limitations + counter-evidence + PubMed literature
```

## Evaluation (`evaluation/`)

The final DebateCheck system was evaluated on a fixed set of **101 health claims** selected from the PubHealth dataset. Claims were screened for suitability for biomedical evidence verification using PubMed.

The same 101 claims were evaluated using:

1. **Traditional baseline** — retrieved evidence is classified using a pretrained NLI stance classifier and combined through majority voting.
2. **DebateCheck** — the same evidence retrieval pipeline is followed by PRO/CON debate agents and an LLM judge with four-run self-consistency.

Using the same evaluation claims and retrieval pipeline allows the comparison to focus on the effect of the downstream reasoning architecture.

### Evaluation setup

- Evaluation claims: **101**
- Ground-truth labels: `true`, `false`, `mixture`, `unproven`
- PubMed retrieval limit: **8 papers per query**
- Baseline: NLI stance classification + majority vote
- DebateCheck: PRO/CON multi-agent debate + judge
- Judge self-consistency: **`n_runs=4`**
- Claims for which no usable PubMed evidence was retrieved were assigned `unproven` as the evaluation prediction rather than being removed from the test set.
- Both systems completed all **101/101 claims with zero evaluation errors**.

### Final results

| Metric | Traditional Baseline | DebateCheck (`n_runs=4`) |
|---|---:|---:|
| Accuracy | 7.92% | **9.90%** |
| Macro Precision | 21.81% | **38.35%** |
| Macro Recall | 16.24% | **24.10%** |
| Macro F1 | 7.31% | **10.86%** |
| Evidence retrieved | 17/101 (16.8%) | 17/101 (16.8%) |
| No usable evidence | 84/101 (83.2%) | 84/101 (83.2%) |
| Evidence-subset Accuracy | 35.29% | **47.06%** |
| Evidence-subset Macro F1 | 23.08% | **35.54%** |

Across all 101 claims, DebateCheck improved accuracy by **1.98 percentage points** and Macro F1 by **3.55 percentage points** over the traditional baseline.

The difference was larger when the analysis was restricted to the 17 claims for which usable PubMed evidence was retrieved. On this evidence-available subset, accuracy increased from **35.29% to 47.06%** (+11.76 percentage points), while Macro F1 increased from **23.08% to 35.54%** (+12.46 percentage points).

### Retrieval bottleneck

The most important finding from the end-to-end evaluation was the low evidence retrieval coverage.

Both systems retrieved usable evidence for only **17 of 101 claims (16.8%)**. The remaining **84 claims (83.2%)** therefore defaulted to the `unproven` evaluation outcome.

This substantially limited the overall end-to-end performance of both systems. Because the baseline and DebateCheck used the same retrieval pipeline and achieved identical retrieval coverage, the evidence-available subset provides a more focused comparison of their downstream reasoning components.

When usable evidence was available, the multi-agent DebateCheck pipeline outperformed the traditional NLI majority-vote baseline. However, this downstream improvement translated into only a modest increase in overall end-to-end performance because usable PubMed evidence was retrieved for just 16.8% of the evaluation claims.

Retrieval was the primary bottleneck, but not the only one. DebateCheck achieved **47.06% accuracy** on the evidence-available subset, indicating that the debate and judging stages also leave substantial room for improvement.

### Prediction behaviour

The traditional baseline never predicted the `mixture` class in the 101-claim evaluation. DebateCheck correctly classified **two ground-truth mixture claims** as `mixture`.

This provides preliminary evidence that the adversarial PRO/CON architecture may be better suited than simple majority voting to representing conflicting or mixed evidence. However, the evidence-available subset contains only 17 claims, so this observation should be interpreted cautiously rather than as evidence of general superiority.

### Citation validity

Citation grounding was evaluated separately on all **17 evidence-bearing claims** for which the debate stage could run.

| Citation metric | Result |
|---|---:|
| Evidence-bearing claims evaluated | **17/17** |
| Total citation attempts | **181** |
| Valid evidence-ID citations | **181** |
| Invalid evidence-ID citations | **0** |
| Citation validity | **100.00%** |
| Dropped argument points | **2** |
| Invalid citations surviving validation | **0** |
| Evaluation errors | **0** |

All **181 citation attempts** referenced valid evidence IDs, resulting in a citation-ID validity rate of **100%**. No invalid citation IDs survived the validation layer.

This metric evaluates **citation-ID grounding**, i.e. whether an agent's citation refers to evidence that was actually available to the system. It does **not** establish that every cited source semantically entails or fully supports the associated argument. Semantic citation faithfulness would require a separate entailment-based or human evaluation.

Two argument points were dropped by the citation-enforcement mechanism. `dropped_points` is reported separately from invalid citation IDs and should not be interpreted as two hallucinated citations.

### Runtime

For the final `n_runs=4` DebateCheck evaluation, the recorded end-to-end latency across all 101 claims was:

- Mean latency: **4.50 seconds per claim**
- Median latency: **1.22 seconds per claim**
- Total recorded latency: **454.26 seconds**

Because **84 of 101 claims** terminated after retrieval when no usable evidence was found, the overall mean understates the runtime of the complete multi-agent pipeline.

Among the **17 evidence-bearing claims** that proceeded through retrieval, debate, and judging:

- Mean end-to-end latency: **21.41 seconds per claim**
- Median end-to-end latency: **18.53 seconds per claim**

The difference between overall and evidence-bearing latency reflects the pipeline structure: no-evidence claims terminate early, whereas evidence-bearing claims require additional PRO/CON debate and four independent judge runs.

API rate limits were encountered during development and batch evaluation. Evaluation scripts therefore use checkpointing and retry handling so completed claims are preserved and interrupted or rate-limited evaluations can resume safely.

### API usage and cost

Operational API usage was also recorded during the final evaluation period.

| Provider / Service | Observed usage | Observed monetary cost |
|---|---:|---:|
| Groq — `openai/gpt-oss-120b` | 81 requests / 284.2K tokens | **$0.08 USD** |
| Google Gemini — `gemini-3.5-flash-lite` | Free-tier usage | **$0.00 USD** |
| PubMed / NCBI E-utilities | Free API | **$0.00 USD** |

The observed Groq usage consisted of:

- Cached input tokens: **16.1K**
- Uncached input tokens: **175.8K**
- Total input tokens: **191.9K**
- Output tokens: **92.3K**
- Total tokens: **284.2K**
- Requests: **81**
- Observed Groq charge: **$0.08 USD**

Gemini was operated under its free tier during the evaluation, while PubMed retrieval used the free NCBI E-utilities service.

The Groq dashboard statistics cover **all project activity recorded on 6 October 2026**, including development and evaluation calls, rather than exclusively the final 101-claim benchmark. Therefore, the $0.08 figure is reported as **observed project API expenditure**, not as an exact isolated benchmark cost or production cost per claim.

### Evaluation files

```text
evaluation/
├── data/
│   └── pubhealth_eval_101.csv
├── results/
│   ├── baseline_results_101.csv
│   ├── debatecheck_results_101_n_runs4.csv
│   ├── model_comparison_101.csv
│   ├── confusion_matrices_101.csv
│   ├── evidence_subset_comparison_101.csv
│   ├── citation_evaluation_101.csv
│   └── api_cost_analysis.csv
├── run_baseline.py
├── retry_failed_baseline.py
├── run_debatecheck_eval.py
├── run_citation_eval.py
├── compare_models.py
└── analyze_api_cost.py
```

`compare_models.py` calculates the baseline-vs-DebateCheck performance metrics, confusion matrices, retrieval coverage, evidence-available subset performance, and latency statistics.

`run_citation_eval.py` evaluates citation-ID grounding on evidence-bearing claims, including valid and invalid citation attempts, dropped argument points, and citations surviving validation.

`analyze_api_cost.py` records and summarizes observed API usage and monetary cost from the final evaluation period.


## Git workflow

```bash
git checkout main
git pull
git checkout -b personX-your-part
# ...work, commit...
git push -u origin personX-your-part
# then open a pull request into main
```

## Live Deployment

DebateCheck is publicly deployed on Render.

- **Live Web App:** https://debatecheck-frontend.onrender.com
- **Backend API:** https://debatecheck-backend.onrender.com


### Deployment Architecture

```text
User
  -> Streamlit Frontend (Render)
  -> FastAPI Backend (Render)
  -> PubMed Evidence Retrieval
  -> PRO / CON Multi-Agent Debate
  -> LLM Judge
  -> Verdict, Confidence, and Misinformation Risk
```

### Render Configuration

**Backend**

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
```

**Frontend**

```text
Root Directory: frontend
Build Command: pip install streamlit requests
Start Command: streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```
