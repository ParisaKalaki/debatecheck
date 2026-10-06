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
sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))

from run_baseline import run_baseline_for_claim
from metrics import calculate_metrics, diagnostic_analysis


RESULTS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "baseline_results_101.csv"
)

MAX_RETRIES = 5
WAIT_SECONDS = 65


# ============================================================
# Retry one failed claim
# ============================================================

def retry_claim(claim):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}")

            result = run_baseline_for_claim(claim)

            return result, ""

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

            print(f"ERROR: {last_error}")

            if attempt < MAX_RETRIES:
                print(
                    f"Waiting {WAIT_SECONDS} seconds "
                    f"before retry..."
                )
                time.sleep(WAIT_SECONDS)

    return None, last_error


# ============================================================
# Main
# ============================================================

def main():

    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Results file not found:\n{RESULTS_PATH}"
        )

    df = pd.read_csv(RESULTS_PATH)

    failed_mask = (
        df["error"]
        .fillna("")
        .astype(str)
        .str.strip()
        != ""
    )

    failed_indices = df.index[failed_mask].tolist()

    print("=" * 60)
    print("RETRY FAILED BASELINE CLAIMS")
    print("=" * 60)

    print(f"Total rows: {len(df)}")
    print(f"Failed rows to retry: {len(failed_indices)}")

    if len(failed_indices) == 0:
        print("No failed rows. Nothing to retry.")

    else:

        for retry_number, idx in enumerate(
            failed_indices,
            start=1,
        ):

            row = df.loc[idx]

            eval_id = row["eval_id"]
            claim = str(row["claim"])
            ground_truth = row["ground_truth"]

            print("\n" + "-" * 60)
            print(
                f"[{retry_number}/{len(failed_indices)}] "
                f"{eval_id}"
            )
            print(f"Claim: {claim}")
            print(f"Ground truth: {ground_truth}")

            result, error = retry_claim(claim)

            if result is not None:

                df.at[idx, "raw_verdict"] = (
                    result["raw_verdict"]
                )

                df.at[idx, "prediction"] = (
                    result["prediction"]
                )

                df.at[idx, "evidence_count"] = (
                    result["evidence_count"]
                )

                df.at[idx, "latency_seconds"] = (
                    result["latency_seconds"]
                )

                df.at[idx, "error"] = ""

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
                    f"Latency: "
                    f"{result['latency_seconds']:.2f}s"
                )

            else:

                df.at[idx, "error"] = error

                print("FAILED after all retry attempts.")

            # Save after every claim
            df.to_csv(
                RESULTS_PATH,
                index=False,
            )

            print("Checkpoint saved.")

            # Avoid Gemini rate limit
            #if retry_number < len(failed_indices):

             #   print(
              #      f"Waiting {WAIT_SECONDS} seconds "
               #     f"before next claim..."
                #)

               # time.sleep(WAIT_SECONDS)

    # ========================================================
    # Final results
    # ========================================================

    failed_after_retry = df[
        df["error"]
        .fillna("")
        .astype(str)
        .str.strip()
        != ""
    ]

    successful = df[
        df["prediction"]
        .fillna("")
        .astype(str)
        .str.strip()
        != ""
    ]

    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)

    print(
        f"Successful claims: "
        f"{len(successful)}/{len(df)}"
    )

    print(
        f"Failed claims: "
        f"{len(failed_after_retry)}/{len(df)}"
    )

    if len(failed_after_retry) > 0:

        print("\nStill failed:")

        print(
            failed_after_retry[
                ["eval_id", "error"]
            ].to_string(index=False)
        )

    # ========================================================
    # Metrics
    # ========================================================

    if len(successful) > 0:

        y_true = successful["ground_truth"]
        y_pred = successful["prediction"]

        metrics = calculate_metrics(
            y_true,
            y_pred,
        )

        diagnostics = diagnostic_analysis(
            y_true,
            y_pred,
        )

        print("\n" + "=" * 60)
        print("BASELINE RESULTS")
        print("=" * 60)

        for metric, value in metrics.items():
            print(
                f"{metric}: {value:.4f}"
            )

        print("\n=== Per-Class Metrics ===")

        for label in [
            "true",
            "false",
            "mixture",
            "unproven",
        ]:

            values = diagnostics["per_class"][label]

            print(
                f"{label}: "
                f"precision={values['precision']:.4f}, "
                f"recall={values['recall']:.4f}, "
                f"f1={values['f1-score']:.4f}"
            )

        print("\n=== Confusion Matrix ===")

        print(
            diagnostics["confusion_matrix"]
        )

    print(
        f"\nFinal results saved to:\n"
        f"{RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()
