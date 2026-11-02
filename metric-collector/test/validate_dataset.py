import argparse
from pathlib import Path

import pandas as pd


REQUIRED = [
    "timestamp", "service", "request_rate", "error_count",
    "thread_count", "cpu_usage", "response_time",
    "actual_label", "prediction", "anomaly_score",
]


def main():
    parser = argparse.ArgumentParser(description="Validate the collected test prediction CSV.")
    parser.add_argument(
        "csv_file", nargs="?",
        default=str(Path(__file__).resolve().parent / "test_dataset.csv"),
        help="CSV file to validate (default: test_dataset.csv beside this script).",
    )
    args = parser.parse_args()
    path = Path(args.csv_file)

    if not path.exists():
        raise SystemExit(f"ERROR: File not found: {path}")

    df = pd.read_csv(path)
    print("File:", path)
    print("Rows:", len(df))
    print("Columns:", list(df.columns))

    missing_columns = [column for column in REQUIRED if column not in df.columns]
    if missing_columns:
        print("FAIL: Missing required columns:", missing_columns)
        raise SystemExit(1)

    if df.empty:
        print("FAIL: Dataset is empty.")
        raise SystemExit(1)

    print("\nRows per service:")
    print(df["service"].value_counts(dropna=False).to_string())

    print("\nPrediction counts:")
    print(df["prediction"].value_counts(dropna=False).to_string())

    print("\nFault API label counts (0=reported normal, 1=reported fault, blank=unknown):")
    print(df["actual_label"].value_counts(dropna=False).to_string())

    numeric = [
        "request_rate", "error_count",
        "thread_count", "cpu_usage", "response_time", "anomaly_score",
    ]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    bad_counts = df[numeric].isna().sum()
    if bad_counts.any():
        print("\nWARNING: Missing/non-numeric values:")
        print(bad_counts[bad_counts > 0].to_string())

    allowed_predictions = {"NORMAL", "ANOMALY"}
    unexpected = sorted(set(df["prediction"].dropna().astype(str)) - allowed_predictions)
    if unexpected:
        print("\nWARNING: Unexpected prediction values:", unexpected)

    print("\nValidation completed. Remember: the model prediction and fault API label are different signals.")


if __name__ == "__main__":
    main()
