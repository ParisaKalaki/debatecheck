from pathlib import Path
import pandas as pd


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "api_cost_analysis.csv"
)


# ============================================================
# Observed API usage
# Groq Developer dashboard — 6 October 2026
# ============================================================

GROQ_REQUESTS = 81

GROQ_CACHED_INPUT_TOKENS = 16_100
GROQ_UNCACHED_INPUT_TOKENS = 175_800
GROQ_OUTPUT_TOKENS = 92_300
GROQ_TOTAL_TOKENS = 284_200

GROQ_OBSERVED_COST_USD = 0.08

# Gemini was used under the free tier.
GEMINI_OBSERVED_COST_USD = 0.00

# PubMed / NCBI E-utilities is free.
PUBMED_OBSERVED_COST_USD = 0.00


# ============================================================
# Evaluation information
# ============================================================

TOTAL_EVAL_CLAIMS = 101
EVIDENCE_BEARING_CLAIMS = 17

JUDGE_RUNS = 4


# ============================================================
# Calculations
# ============================================================

groq_input_tokens = (
    GROQ_CACHED_INPUT_TOKENS
    + GROQ_UNCACHED_INPUT_TOKENS
)

total_observed_cost = (
    GROQ_OBSERVED_COST_USD
    + GEMINI_OBSERVED_COST_USD
    + PUBMED_OBSERVED_COST_USD
)

# These normalized values are descriptive only.
# The Groq dashboard usage covers the full Oct 6 project activity,
# not exclusively the 101-claim benchmark.

cost_per_101_claim = (
    total_observed_cost / TOTAL_EVAL_CLAIMS
)

cost_per_evidence_claim = (
    total_observed_cost / EVIDENCE_BEARING_CLAIMS
)

tokens_per_request = (
    GROQ_TOTAL_TOKENS / GROQ_REQUESTS
)


# ============================================================
# Build output table
# ============================================================

rows = [
    {
        "provider": "Groq",
        "model_or_service": "openai/gpt-oss-120b",
        "plan": "Developer",
        "requests": GROQ_REQUESTS,
        "cached_input_tokens": GROQ_CACHED_INPUT_TOKENS,
        "uncached_input_tokens": GROQ_UNCACHED_INPUT_TOKENS,
        "input_tokens_total": groq_input_tokens,
        "output_tokens": GROQ_OUTPUT_TOKENS,
        "total_tokens": GROQ_TOTAL_TOKENS,
        "observed_cost_usd": GROQ_OBSERVED_COST_USD,
        "notes": (
            "Observed Groq dashboard usage for 6 Oct 2026. "
            "Includes project activity beyond the isolated "
            "101-claim benchmark."
        ),
    },
    {
        "provider": "Google",
        "model_or_service": "gemini-3.5-flash-lite",
        "plan": "Free tier",
        "requests": None,
        "cached_input_tokens": None,
        "uncached_input_tokens": None,
        "input_tokens_total": None,
        "output_tokens": None,
        "total_tokens": None,
        "observed_cost_usd": GEMINI_OBSERVED_COST_USD,
        "notes": (
            "Used under Gemini free tier during evaluation; "
            "rate-limit errors were observed."
        ),
    },
    {
        "provider": "NCBI",
        "model_or_service": "PubMed E-utilities",
        "plan": "Free",
        "requests": None,
        "cached_input_tokens": None,
        "uncached_input_tokens": None,
        "input_tokens_total": None,
        "output_tokens": None,
        "total_tokens": None,
        "observed_cost_usd": PUBMED_OBSERVED_COST_USD,
        "notes": "PubMed retrieval API has no observed monetary API cost.",
    },
]


df = pd.DataFrame(rows)


# ============================================================
# Save
# ============================================================

OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

df.to_csv(
    OUTPUT_PATH,
    index=False,
)


# ============================================================
# Print summary
# ============================================================

print("=" * 70)
print("API COST ANALYSIS")
print("=" * 70)

print(f"Groq requests:                 {GROQ_REQUESTS}")
print(f"Groq cached input tokens:      {GROQ_CACHED_INPUT_TOKENS:,}")
print(f"Groq uncached input tokens:    {GROQ_UNCACHED_INPUT_TOKENS:,}")
print(f"Groq total input tokens:       {groq_input_tokens:,}")
print(f"Groq output tokens:            {GROQ_OUTPUT_TOKENS:,}")
print(f"Groq total tokens:             {GROQ_TOTAL_TOKENS:,}")
print(f"Average tokens/request:        {tokens_per_request:,.1f}")

print()
print(f"Groq observed cost:            ${GROQ_OBSERVED_COST_USD:.2f}")
print(f"Gemini observed cost:          ${GEMINI_OBSERVED_COST_USD:.2f}")
print(f"PubMed observed cost:          ${PUBMED_OBSERVED_COST_USD:.2f}")
print(f"Total observed paid cost:      ${total_observed_cost:.2f}")

print()
print("Descriptive normalization only:")
print(
    f"Observed cost / 101 claims:    "
    f"${cost_per_101_claim:.6f}"
)
print(
    f"Observed cost / 17 evidence claims: "
    f"${cost_per_evidence_claim:.6f}"
)

print()
print(
    "IMPORTANT: Groq dashboard usage represents all project activity "
    "on 6 Oct 2026, not exclusively the final benchmark."
)

print()
print("Results saved to:")
print(OUTPUT_PATH)
