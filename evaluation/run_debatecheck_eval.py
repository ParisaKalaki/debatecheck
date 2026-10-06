import sys
import time
from pathlib import Path

import pandas as pd


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from app.retrieval.evidence_pipeline import get_evidence_for_claim
from app.agents.debate_graph import run_debate
from app.judge.judge_agent import judge_debate_with_confidence


DATA_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "data"
    / "pubhealth_eval_101.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "debatecheck_results_101_n_runs4.csv"
)


# ============================================================
# Final evaluation configuration
# ============================================================

LIMIT = 101
RETMAX = 8
JUDGE_RUNS = 4

# Retry configuration
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 65


# ============================================================
# Judge label mapping
# ============================================================

def normalize_judge_label(verdict):
    verdict = str(verdict).strip().lower()

    mapping = {
        "true": "true",
        "likely true": "true",
        "mixed": "mixture",
        "mixed / unclear": "mixture",
        "unclear": "mixture",
        "likely false": "false",
        "false": "false",
        "unverifiable": "unproven",
        "unproven": "unproven",
    }

    return mapping.get(verdict, verdict)


# ============================================================
# Run DebateCheck for one claim
# ============================================================

def run_debatecheck_for_claim(claim):

    total_start = time.perf_counter()

    # --------------------------------------------------------
    # 1. Retrieval
    # --------------------------------------------------------

    retrieval_start = time.perf_counter()

    evidence = get_evidence_for_claim(
        claim,
        retmax=RETMAX,
    )

    retrieval_latency = (
        time.perf_counter() - retrieval_start
    )

    evidence_count = len(evidence)

    # Evaluation policy:
    # no usable evidence -> unproven
    if evidence_count == 0:

        total_latency = (
            time.perf_counter() - total_start
        )

        return {
            "raw_verdict": "Unverifiable",
            "prediction": "unproven",
            "confidence": 0.0,
            "evidence_count": 0,
            "retrieval_latency": retrieval_latency,
            "debate_latency": 0.0,
            "judge_latency": 0.0,
            "total_latency": total_latency,
            "status": "no_evidence",
        }

    # --------------------------------------------------------
    # 2. Debate
    # --------------------------------------------------------

    debate_start = time.perf_counter()

    debate_result = run_debate(
        claim,
        evidence,
    )

    debate_latency = (
        time.perf_counter() - debate_start
    )

    transcript = debate_result["transcript"]

    # --------------------------------------------------------
    # 3. Judge
    # --------------------------------------------------------

    judge_start = time.perf_counter()

    verdict = judge_debate_with_confidence(
        claim=claim,
        transcript=transcript,
        evidence=evidence,
        n_runs=JUDGE_RUNS,
        verbose=False,
    )

    judge_latency = (
        time.perf_counter() - judge_start
    )

    total_latency = (
        time.perf_counter() - total_start
    )

    raw_verdict = verdict.verdict

    prediction = normalize_judge_label(
        raw_verdict
    )

    confidence = verdict.confidence

    return {
        "raw_verdict": raw_verdict,
        "prediction": prediction,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "retrieval_latency": retrieval_latency,
        "debate_latency": debate_latency,
        "judge_latency": judge_latency,
        "total_latency": total_latency,
        "status": "completed",
    }


# ============================================================
# Retry wrapper
# ============================================================

def run_with_retry(claim):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            result = run_debatecheck_for_claim(claim)
            return result, ""

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed: "
                f"{last_error}"
            )

            if attempt < MAX_RETRIES:
                print(
                    f"Waiting {RETRY_WAIT_SECONDS} seconds "
                    f"before retry..."
                )
                time.sleep(RETRY_WAIT_SECONDS)

    # Both attempts failed
    result = {
        "raw_verdict": "",
        "prediction": "",
        "confidence": 0.0,
        "evidence_count": 0,
        "retrieval_latency": 0.0,
        "debate_latency": 0.0,
        "judge_latency": 0.0,
        "total_latency": 0.0,
        "status": "error",
    }

    return result, last_error


# ============================================================
# Load existing checkpoint
# ============================================================

def load_checkpoint():

    if not OUTPUT_PATH.exists():
        return [], set()

    try:
        checkpoint_df = pd.read_csv(OUTPUT_PATH)
    except Exception as exc:
        print(
            f"Could not read existing checkpoint: {exc}"
        )
        return [], set()

    if checkpoint_df.empty:
        return [], set()

    # Only completed/no-evidence rows are considered finished.
    finished_mask = checkpoint_df["status"].isin(
        ["completed", "no_evidence"]
    )

    finished_df = checkpoint_df[
        finished_mask
    ].copy()

    completed_ids = set(
        finished_df["eval_id"].astype(str)
    )

    results = finished_df.to_dict(
        orient="records"
    )

    print(
        f"Existing checkpoint found: "
        f"{len(results)} completed claims."
    )

    if len(checkpoint_df) > len(finished_df):
        print(
            f"{len(checkpoint_df) - len(finished_df)} "
            f"unfinished/error claims will be retried."
        )

    return results, completed_ids


# ============================================================
# Save checkpoint
# ============================================================

def save_checkpoint(results):

    results_df = pd.DataFrame(results)

    # Keep one row per eval_id.
    # If an errored claim is later successfully retried,
    # the newest result replaces the older one.
    if not results_df.empty:
        results_df = results_df.drop_duplicates(
            subset=["eval_id"],
            keep="last",
        )

    results_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )


# ============================================================
# Main
# ============================================================

def main():

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = pd.read_csv(DATA_PATH)

    eval_df = df.head(LIMIT).copy()

    print("=" * 60)
    print("DEBATECHECK FINAL EVALUATION")
    print("=" * 60)

    print(f"Claims: {len(eval_df)}")
    print(f"RETMAX: {RETMAX}")
    print(f"Judge runs: {JUDGE_RUNS}")
    print(f"Max retries: {MAX_RETRIES}")

    # --------------------------------------------------------
    # Resume from existing checkpoint
    # --------------------------------------------------------

    results, completed_ids = load_checkpoint()

    remaining = (
        len(eval_df) - len(completed_ids)
    )

    print(
        f"Remaining claims: {remaining}"
    )

    wall_start = time.perf_counter()

    # --------------------------------------------------------
    # Evaluation loop
    # --------------------------------------------------------

    for number, (_, row) in enumerate(
        eval_df.iterrows(),
        start=1,
    ):

        eval_id = str(row["eval_id"])
        claim = str(row["claim"])
        ground_truth = str(
            row["label"]
        ).strip().lower()

        # Skip claims already completed in checkpoint
        if eval_id in completed_ids:
            print(
                f"[{number}/{len(eval_df)}] "
                f"{eval_id} already completed -> skipping."
            )
            continue

        print("\n" + "-" * 60)

        print(
            f"[{number}/{len(eval_df)}] "
            f"{eval_id}"
        )

        print(f"Claim: {claim}")

        print(
            f"Ground truth: {ground_truth}"
        )

        # ----------------------------------------------------
        # Run with retry
        # ----------------------------------------------------

        result, error = run_with_retry(
            claim
        )

        if result["status"] == "error":

            print(
                f"FINAL ERROR: {error}"
            )

        else:

            print(
                f"Prediction: "
                f"{result['prediction']}"
            )

            print(
                f"Raw verdict: "
                f"{result['raw_verdict']}"
            )

            print(
                f"Evidence: "
                f"{result['evidence_count']}"
            )

            print(
                f"Status: "
                f"{result['status']}"
            )

            print(
                f"Confidence: "
                f"{result['confidence']}"
            )

            print(
                f"Total latency: "
                f"{result['total_latency']:.2f}s"
            )

        # ----------------------------------------------------
        # Add/update result
        # ----------------------------------------------------

        # Remove an older row for this eval_id if one exists
        results = [
            r for r in results
            if str(r["eval_id"]) != eval_id
        ]

        results.append({
            "eval_id": eval_id,
            "claim": claim,
            "ground_truth": ground_truth,
            **result,
            "error": error,
        })

        # ----------------------------------------------------
        # Save after every claim
        # ----------------------------------------------------

        save_checkpoint(results)

        if result["status"] in [
            "completed",
            "no_evidence",
        ]:
            completed_ids.add(eval_id)

        print("Checkpoint saved.")

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    wall_time = (
        time.perf_counter() - wall_start
    )

    results_df = pd.DataFrame(results)

    if not results_df.empty:

        results_df = results_df.drop_duplicates(
            subset=["eval_id"],
            keep="last",
        )

        # Sort back into dataset order
        order = {
            str(eval_id): i
            for i, eval_id in enumerate(
                eval_df["eval_id"]
            )
        }

        results_df["_order"] = (
            results_df["eval_id"]
            .astype(str)
            .map(order)
        )

        results_df = (
            results_df
            .sort_values("_order")
            .drop(columns="_order")
        )

        results_df.to_csv(
            OUTPUT_PATH,
            index=False,
        )

    print("\n" + "=" * 60)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 60)

    if not results_df.empty:

        print(
            results_df[
                [
                    "eval_id",
                    "ground_truth",
                    "prediction",
                    "evidence_count",
                    "status",
                ]
            ].to_string(index=False)
        )

        error_count = (
            results_df["status"]
            .eq("error")
            .sum()
        )

        completed_count = (
            results_df["status"]
            .isin(
                ["completed", "no_evidence"]
            )
            .sum()
        )

        print(
            f"\nCompleted: "
            f"{completed_count}/{len(eval_df)}"
        )

        print(
            f"Errors remaining: "
            f"{error_count}"
        )

    print(
        f"\nSession wall time: "
        f"{wall_time:.2f}s"
    )

    print(
        f"\nResults saved to:\n"
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
