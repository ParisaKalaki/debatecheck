import sys
import time
from pathlib import Path

import pandas as pd


# Allow imports from backend/app
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))


from app.retrieval.evidence_pipeline import get_evidence_for_claim
from app.baseline.nli_classifier import (
    classify_stance_nli,
    majority_vote_verdict,
)

from label_mapping import normalize_baseline_label
from metrics import calculate_metrics, diagnostic_analysis


INPUT_PATH = PROJECT_ROOT / "evaluation" / "data" / "pubhealth_eval_150.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "results" / "baseline_results.csv"

RETMAX = 10


def run_baseline_for_claim(claim):
    """Run the traditional baseline for one claim."""

    evidence = get_evidence_for_claim(
        claim,
        retmax=RETMAX,
    )

    baseline_results = []

    for item in evidence:
        stance = classify_stance_nli(
            claim,
            item.text,
        )

        baseline_results.append(
            {
                "id": item.id,
                "stance": stance,
                "text": item.text,
            }
        )

    verdict = majority_vote_verdict(baseline_results)

    return verdict, len(evidence)


def main():
    df = pd.read_csv(INPUT_PATH)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    print(f"Running baseline on {len(df)} claims...\n")

    for index, row in df.head(10).iterrows():
        eval_id = row["eval_id"]
        claim = row["claim"]
        ground_truth = row["label"]

        print(f"[{index + 1}/10] {eval_id}")
        print(f"Claim: {claim}")

        start_time = time.perf_counter()

        try:
            verdict, evidence_count = run_baseline_for_claim(claim)

            latency = time.perf_counter() - start_time

            prediction = normalize_baseline_label(
                verdict["verdict"]
            )

            result = {
                "eval_id": eval_id,
                "claim": claim,
                "ground_truth": ground_truth,
                "raw_verdict": verdict["verdict"],
                "prediction": prediction,
                "support_count": verdict["support_count"],
                "contradict_count": verdict["contradict_count"],
                "neutral_count": verdict["neutral_count"],
                "evidence_count": evidence_count,
                "latency_seconds": latency,
                "error": "",
            }

            print(
                f"Prediction: {prediction} | "
                f"Ground truth: {ground_truth} | "
                f"Time: {latency:.2f}s"
            )

        except Exception as error:
            latency = time.perf_counter() - start_time

            result = {
                "eval_id": eval_id,
                "claim": claim,
                "ground_truth": ground_truth,
                "raw_verdict": "",
                "prediction": "",
                "support_count": "",
                "contradict_count": "",
                "neutral_count": "",
                "evidence_count": "",
                "latency_seconds": latency,
                "error": str(error),
            }

            print(f"ERROR: {error}")

        results.append(result)

        # Save after every claim so progress is not lost.
        pd.DataFrame(results).to_csv(
            OUTPUT_PATH,
            index=False,
        )

        print()

    results_df = pd.DataFrame(results)

    # Metrics only for successfully evaluated claims.
    valid_results = results_df[
        results_df["prediction"] != ""
    ].copy()

    if len(valid_results) == 0:
        print("\n=== BASELINE RESULTS ===")
        print("Successful claims: 0/1")
        print("No successful predictions. Metrics cannot be calculated.")
        print(f"\nResults saved to: {OUTPUT_PATH}")
        return

    y_true = valid_results["ground_truth"]
    y_pred = valid_results["prediction"]

    metrics = calculate_metrics(y_true, y_pred)
    diagnostics = diagnostic_analysis(y_true, y_pred)

    print("\n=== BASELINE RESULTS ===")
    print(f"Successful claims: {len(valid_results)}/10")

    for metric, value in metrics.items():
        print(f"{metric}: {value:.4f}")

    print("\n=== Per-Class Metrics ===")

    for label in ["true", "false", "mixture", "unproven"]:
        values = diagnostics["per_class"][label]

        print(
            f"{label}: "
            f"precision={values['precision']:.4f}, "
            f"recall={values['recall']:.4f}, "
            f"f1={values['f1-score']:.4f}"
        )

    print("\n=== Confusion Matrix ===")
    print(diagnostics["confusion_matrix"])

    print(
        f"\nAverage latency: "
        f"{valid_results['latency_seconds'].mean():.2f}s"
    )

    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
