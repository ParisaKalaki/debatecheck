from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)


LABELS = ["true", "false", "mixture", "unproven"]


def calculate_metrics(y_true, y_pred):
    """
    Calculate the main evaluation metrics specified in the project plan.
    """

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(
            y_true,
            y_pred,
            labels=LABELS,
            average="macro",
            zero_division=0,
        ),
        "recall": recall_score(
            y_true,
            y_pred,
            labels=LABELS,
            average="macro",
            zero_division=0,
        ),
        "f1": f1_score(
            y_true,
            y_pred,
            labels=LABELS,
            average="macro",
            zero_division=0,
        ),
    }


def diagnostic_analysis(y_true, y_pred):
    """
    Additional diagnostic information for result interpretation.
    """

    per_class = classification_report(
        y_true,
        y_pred,
        labels=LABELS,
        output_dict=True,
        zero_division=0,
    )

    matrix = confusion_matrix(
        y_true,
        y_pred,
        labels=LABELS,
    )

    return {
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


if __name__ == "__main__":
    # Simple test
    y_true = ["true", "false", "mixture", "unproven"]
    y_pred = ["true", "false", "true", "unproven"]

    metrics = calculate_metrics(y_true, y_pred)
    diagnostics = diagnostic_analysis(y_true, y_pred)

    print("=== Main Metrics ===")
    for metric, value in metrics.items():
        print(f"{metric}: {value:.4f}")

    print("\n=== Per-Class Metrics ===")
    for label in LABELS:
        result = diagnostics["per_class"][label]
        print(
            f"{label}: "
            f"precision={result['precision']:.4f}, "
            f"recall={result['recall']:.4f}, "
            f"f1={result['f1-score']:.4f}"
        )

    print("\n=== Confusion Matrix ===")
    print(diagnostics["confusion_matrix"])
