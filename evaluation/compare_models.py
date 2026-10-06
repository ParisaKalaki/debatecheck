from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"

BASELINE_PATH = RESULTS_DIR / "baseline_results_101.csv"
DEBATECHECK_PATH = RESULTS_DIR / "debatecheck_results_101_n_runs4.csv"

SUMMARY_PATH = RESULTS_DIR / "model_comparison_101.csv"
CONFUSION_PATH = RESULTS_DIR / "confusion_matrices_101.csv"
EVIDENCE_SUBSET_PATH = RESULTS_DIR / "evidence_subset_comparison_101.csv"


LABELS = ["true", "false", "mixture", "unproven"]


# ============================================================
# Helpers
# ============================================================

def normalize_label(value):
    if pd.isna(value):
        return ""

    value = str(value).strip().lower()

    mapping = {
        "true": "true",
        "false": "false",
        "mixture": "mixture",
        "mixed": "mixture",
        "mixed / unclear": "mixture",
        "unproven": "unproven",
        "unverifiable": "unproven",
        "likely true": "true",
        "likely false": "false",
    }

    return mapping.get(value, value)


def prepare_dataframe(path):
    df = pd.read_csv(path)

    required = {"eval_id", "ground_truth", "prediction", "evidence_count"}

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: {sorted(missing)}"
        )

    df = df.copy()

    df["ground_truth"] = df["ground_truth"].apply(normalize_label)
    df["prediction"] = df["prediction"].apply(normalize_label)

    df["evidence_count"] = pd.to_numeric(
        df["evidence_count"],
        errors="coerce",
    ).fillna(0)

    return df


def calculate_metrics(df):
    y_true = df["ground_truth"]
    y_pred = df["prediction"]

    accuracy = accuracy_score(y_true, y_pred)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        average="macro",
        zero_division=0,
    )

    evidence_mask = df["evidence_count"] > 0
    evidence_df = df[evidence_mask]

    no_evidence_df = df[~evidence_mask]

    if len(evidence_df) > 0:
        evidence_accuracy = accuracy_score(
            evidence_df["ground_truth"],
            evidence_df["prediction"],
        )

        ev_precision, ev_recall, ev_f1, _ = (
            precision_recall_fscore_support(
                evidence_df["ground_truth"],
                evidence_df["prediction"],
                labels=LABELS,
                average="macro",
                zero_division=0,
            )
        )
    else:
        evidence_accuracy = np.nan
        ev_precision = np.nan
        ev_recall = np.nan
        ev_f1 = np.nan

    return {
        "n_claims": len(df),
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,

        "evidence_found": len(evidence_df),
        "evidence_found_pct": len(evidence_df) / len(df),

        "no_evidence": len(no_evidence_df),
        "no_evidence_pct": len(no_evidence_df) / len(df),

        "evidence_subset_accuracy": evidence_accuracy,
        "evidence_subset_macro_precision": ev_precision,
        "evidence_subset_macro_recall": ev_recall,
        "evidence_subset_macro_f1": ev_f1,
    }


def calculate_latency(df):
    latency_column = None

    for candidate in [
        "total_latency",
        "total_latency_s",
        "latency",
        "latency_s",
    ]:
        if candidate in df.columns:
            latency_column = candidate
            break

    if latency_column is None:
        return {
            "mean_latency_s": np.nan,
            "median_latency_s": np.nan,
            "total_latency_s": np.nan,
        }

    latency = pd.to_numeric(
        df[latency_column],
        errors="coerce",
    ).dropna()

    if len(latency) == 0:
        return {
            "mean_latency_s": np.nan,
            "median_latency_s": np.nan,
            "total_latency_s": np.nan,
        }

    return {
        "mean_latency_s": latency.mean(),
        "median_latency_s": latency.median(),
        "total_latency_s": latency.sum(),
    }


def get_confusion_matrix(df, model_name):
    cm = confusion_matrix(
        df["ground_truth"],
        df["prediction"],
        labels=LABELS,
    )

    rows = []

    for i, true_label in enumerate(LABELS):
        for j, pred_label in enumerate(LABELS):
            rows.append(
                {
                    "model": model_name,
                    "ground_truth": true_label,
                    "prediction": pred_label,
                    "count": int(cm[i, j]),
                }
            )

    return pd.DataFrame(rows)


def print_confusion(df, model_name):
    cm = confusion_matrix(
        df["ground_truth"],
        df["prediction"],
        labels=LABELS,
    )

    cm_df = pd.DataFrame(
        cm,
        index=[f"GT_{label}" for label in LABELS],
        columns=[f"PRED_{label}" for label in LABELS],
    )

    print(f"\n{model_name} Confusion Matrix")
    print("-" * 70)
    print(cm_df.to_string())


def print_metrics(name, metrics):
    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    print(f"Claims:              {metrics['n_claims']}")
    print(f"Accuracy:            {metrics['accuracy']:.4f}")
    print(f"Macro Precision:     {metrics['macro_precision']:.4f}")
    print(f"Macro Recall:        {metrics['macro_recall']:.4f}")
    print(f"Macro F1:            {metrics['macro_f1']:.4f}")

    print(
        f"Evidence found:      "
        f"{metrics['evidence_found']}/{metrics['n_claims']} "
        f"({metrics['evidence_found_pct'] * 100:.1f}%)"
    )

    print(
        f"No evidence:         "
        f"{metrics['no_evidence']}/{metrics['n_claims']} "
        f"({metrics['no_evidence_pct'] * 100:.1f}%)"
    )

    print("\nEvidence-found subset:")
    print(
        f"  Accuracy:          "
        f"{metrics['evidence_subset_accuracy']:.4f}"
    )
    print(
        f"  Macro Precision:   "
        f"{metrics['evidence_subset_macro_precision']:.4f}"
    )
    print(
        f"  Macro Recall:      "
        f"{metrics['evidence_subset_macro_recall']:.4f}"
    )
    print(
        f"  Macro F1:          "
        f"{metrics['evidence_subset_macro_f1']:.4f}"
    )

    if not np.isnan(metrics["mean_latency_s"]):
        print("\nLatency:")
        print(
            f"  Mean:              "
            f"{metrics['mean_latency_s']:.2f}s"
        )
        print(
            f"  Median:            "
            f"{metrics['median_latency_s']:.2f}s"
        )
        print(
            f"  Total:             "
            f"{metrics['total_latency_s']:.2f}s"
        )


# ============================================================
# Main
# ============================================================

def main():

    print("Loading evaluation results...")

    baseline = prepare_dataframe(BASELINE_PATH)
    debatecheck = prepare_dataframe(DEBATECHECK_PATH)

    # --------------------------------------------------------
    # Verify same evaluation claims
    # --------------------------------------------------------

    baseline_ids = set(baseline["eval_id"])
    debate_ids = set(debatecheck["eval_id"])

    if baseline_ids != debate_ids:
        only_baseline = sorted(baseline_ids - debate_ids)
        only_debate = sorted(debate_ids - baseline_ids)

        raise ValueError(
            "Baseline and DebateCheck were not evaluated on "
            "exactly the same claims.\n"
            f"Only baseline: {only_baseline}\n"
            f"Only DebateCheck: {only_debate}"
        )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    baseline_metrics = calculate_metrics(baseline)
    debate_metrics = calculate_metrics(debatecheck)

    baseline_metrics.update(calculate_latency(baseline))
    debate_metrics.update(calculate_latency(debatecheck))

    print_metrics("BASELINE", baseline_metrics)
    print_metrics("DEBATECHECK", debate_metrics)

    # --------------------------------------------------------
    # Improvement
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("DEBATECHECK vs BASELINE")
    print("=" * 70)

    accuracy_diff = (
        debate_metrics["accuracy"]
        - baseline_metrics["accuracy"]
    )

    f1_diff = (
        debate_metrics["macro_f1"]
        - baseline_metrics["macro_f1"]
    )

    evidence_acc_diff = (
        debate_metrics["evidence_subset_accuracy"]
        - baseline_metrics["evidence_subset_accuracy"]
    )

    print(
        f"Accuracy change:              "
        f"{accuracy_diff:+.4f} "
        f"({accuracy_diff * 100:+.2f} percentage points)"
    )

    print(
        f"Macro F1 change:              "
        f"{f1_diff:+.4f}"
    )

    print(
        f"Evidence-subset accuracy:     "
        f"{evidence_acc_diff:+.4f} "
        f"({evidence_acc_diff * 100:+.2f} percentage points)"
    )

    # --------------------------------------------------------
    # Confusion matrices
    # --------------------------------------------------------

    print_confusion(baseline, "BASELINE")
    print_confusion(debatecheck, "DEBATECHECK")

    baseline_cm = get_confusion_matrix(
        baseline,
        "baseline",
    )

    debate_cm = get_confusion_matrix(
        debatecheck,
        "debatecheck",
    )

    confusion_output = pd.concat(
        [baseline_cm, debate_cm],
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Evidence subset comparison
    # --------------------------------------------------------

    merged = baseline[
        [
            "eval_id",
            "ground_truth",
            "prediction",
            "evidence_count",
        ]
    ].merge(
        debatecheck[
            [
                "eval_id",
                "prediction",
                "evidence_count",
            ]
        ],
        on="eval_id",
        suffixes=("_baseline", "_debatecheck"),
    )

    merged = merged.rename(
        columns={
            "prediction_baseline": "baseline_prediction",
            "prediction_debatecheck": "debatecheck_prediction",
            "evidence_count_baseline": "baseline_evidence_count",
            "evidence_count_debatecheck": "debatecheck_evidence_count",
        }
    )

    merged["baseline_correct"] = (
        merged["ground_truth"]
        == merged["baseline_prediction"]
    )

    merged["debatecheck_correct"] = (
        merged["ground_truth"]
        == merged["debatecheck_prediction"]
    )

    evidence_subset = merged[
        (merged["baseline_evidence_count"] > 0)
        | (merged["debatecheck_evidence_count"] > 0)
    ].copy()

    # --------------------------------------------------------
    # Save summary
    # --------------------------------------------------------

    summary = pd.DataFrame(
        [
            {
                "model": "baseline",
                **baseline_metrics,
            },
            {
                "model": "debatecheck",
                **debate_metrics,
            },
        ]
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
    )

    confusion_output.to_csv(
        CONFUSION_PATH,
        index=False,
    )

    evidence_subset.to_csv(
        EVIDENCE_SUBSET_PATH,
        index=False,
    )

    print("\n" + "=" * 70)
    print("FILES SAVED")
    print("=" * 70)

    print(SUMMARY_PATH)
    print(CONFUSION_PATH)
    print(EVIDENCE_SUBSET_PATH)


if __name__ == "__main__":
    main()
