"""Reusable validation for raw normal-training and labelled test datasets."""
from pathlib import Path
import pandas as pd
EXPECTED_SERVICES = {"user-service", "product-service", "order-service"}
REQUIRED_METRICS = ["request_rate", "error_count", "thread_count", "cpu_usage", "response_time"]


def validate_dataset(csv_path: str | Path, require_labels: bool = False) -> tuple[bool, list[str], dict]:
    errors = []
    path = Path(csv_path)
    if not path.exists(): return False, [f"File not found: {path}"], {}
    try: df = pd.read_csv(path)
    except Exception as exc: return False, [f"Could not read CSV: {exc}"], {}
    if df.empty: errors.append("Dataset has no rows.")
    required = {"timestamp", "service", *REQUIRED_METRICS}
    missing = sorted(required - set(df.columns))
    if missing: errors.append(f"Missing required columns: {missing}")
    if require_labels:
        label_missing = sorted({"actual_label", "prediction"} - set(df.columns))
        if label_missing: errors.append(f"Missing evaluation columns: {label_missing}")
    if not missing:
        services = set(df["service"].dropna().astype(str))
        if services - EXPECTED_SERVICES: errors.append(f"Unexpected service names: {sorted(services - EXPECTED_SERVICES)}")
        if services != EXPECTED_SERVICES: errors.append(f"Expected all three services; found: {sorted(services)}")
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        if ts.isna().any(): errors.append(f"Invalid timestamps: {int(ts.isna().sum())}")
        for col in REQUIRED_METRICS:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.isna().any(): errors.append(f"{col}: {int(values.isna().sum())} missing/non-numeric value(s)")
            elif (values < 0).any(): errors.append(f"{col}: negative values found")
    report = {"rows": int(len(df)), "columns": int(len(df.columns)), "duplicate_rows": int(df.duplicated().sum()), "services": sorted(set(df.get("service", pd.Series(dtype=str)).dropna().astype(str))), "missing_cells": int(df.isna().sum().sum())}
    return not errors, errors, report
