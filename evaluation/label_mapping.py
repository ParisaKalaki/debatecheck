VALID_LABELS = {"true", "false", "mixture", "unproven"}


JUDGE_LABEL_MAP = {
    "True": "true",
    "Likely True": "true",
    "Mixed / Unclear": "mixture",
    "Likely False": "false",
    "False": "false",
    "Unverifiable": "unproven",
}


BASELINE_LABEL_MAP = {
    "leans true": "true",
    "leans false": "false",
    "mixed": "mixture",
    "insufficient evidence": "unproven",
}


def normalize_ground_truth(label):
    """Normalize a PubHealth ground-truth label."""
    if label is None:
        raise ValueError("Ground-truth label cannot be None.")

    normalized = str(label).strip().lower()

    if normalized not in VALID_LABELS:
        raise ValueError(f"Unknown PubHealth label: {label}")

    return normalized


def normalize_judge_label(label):
    """Map a DebateCheck judge verdict to the PubHealth label space."""
    if label is None:
        raise ValueError("Judge label cannot be None.")

    cleaned = str(label).strip()

    if cleaned not in JUDGE_LABEL_MAP:
        raise ValueError(f"Unknown judge verdict: {label}")

    return JUDGE_LABEL_MAP[cleaned]


def normalize_baseline_label(label):
    """Map a baseline prediction to the PubHealth label space."""
    if label is None:
        raise ValueError("Baseline label cannot be None.")

    cleaned = str(label).strip().lower()

    if cleaned not in BASELINE_LABEL_MAP:
        raise ValueError(f"Unknown baseline verdict: {label}")

    return BASELINE_LABEL_MAP[cleaned]


if __name__ == "__main__":
    print("=== Judge mapping ===")
    for original, normalized in JUDGE_LABEL_MAP.items():
        print(f"{original:20} -> {normalized}")

    print("\n=== Baseline mapping ===")
    for original, normalized in BASELINE_LABEL_MAP.items():
        print(f"{original:20} -> {normalized}")
