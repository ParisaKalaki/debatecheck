from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


DATA_DIR = Path(__file__).parent / "data" / "PUBHEALTH"
OUTPUT_PATH = Path(__file__).parent / "data" / "pubhealth_eval_150.csv"

VALID_LABELS = ["true", "false", "mixture", "unproven"]
SAMPLE_SIZE = 150
RANDOM_SEED = 42


def create_eval_sample():
    """Create a reproducible stratified sample of 150 PubHealth test claims."""

    test_path = DATA_DIR / "test.tsv"

    print("Loading PubHealth test set...")
    df = pd.read_csv(test_path, sep="\t")

    print(f"Original test rows: {len(df)}")

    # Keep only examples with valid ground-truth labels.
    df = df[df["label"].isin(VALID_LABELS)].copy()

    print(f"Rows with valid labels: {len(df)}")

    # Draw 150 examples while approximately preserving
    # the original class distribution.
    _, sample = train_test_split(
        df,
        test_size=SAMPLE_SIZE,
        stratify=df["label"],
        random_state=RANDOM_SEED,
    )

    # Remove the accidental index column present in test.tsv.
    if "Unnamed: 0" in sample.columns:
        sample = sample.drop(columns=["Unnamed: 0"])

    # Shuffle the selected examples so labels are not grouped.
    sample = sample.sample(
        frac=1,
        random_state=RANDOM_SEED,
    ).reset_index(drop=True)

    # Add a stable evaluation ID.
    sample.insert(
        0,
        "eval_id",
        [f"PH_{i:03d}" for i in range(1, len(sample) + 1)],
    )

    # Save the fixed evaluation set.
    sample.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("\n=== Evaluation Sample ===")
    print(f"Total samples: {len(sample)}")

    print("\nLabel distribution:")
    print(sample["label"].value_counts())

    print("\nLabel proportions:")
    print(sample["label"].value_counts(normalize=True).round(3))

    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    create_eval_sample()
