from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parent / "data" / "PUBHEALTH"


def load_pubhealth():
    """Load the original PubHealth train, dev, and test TSV files."""

    splits = {}

    for split_name, filename in {
        "train": "train.tsv",
        "dev": "dev.tsv",
        "test": "test.tsv",
    }.items():
        file_path = DATA_DIR / filename

        df = pd.read_csv(file_path, sep="\t")

        splits[split_name] = df

    return splits


def inspect_pubhealth():
    print("Loading PubHealth dataset...")

    splits = load_pubhealth()

    for split_name, df in splits.items():
        print(f"\n=== {split_name.upper()} ===")
        print(f"Number of rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")

        print("\nLabel distribution:")
        print(df["label"].value_counts(dropna=False))

        print("\nFirst example:")
        print(df.iloc[0])


if __name__ == "__main__":
    inspect_pubhealth()
