"""Shared preprocessing for training and live inference."""
from pathlib import Path
from typing import Iterable
import pandas as pd

NUMERIC_FEATURES = ["request_rate", "error_count", "thread_count", "cpu_usage", "response_time"]
SERVICES = ["order-service", "product-service", "user-service"]
SERVICE_FEATURES = [f"service_{name}" for name in SERVICES]
MODEL_FEATURES = NUMERIC_FEATURES + SERVICE_FEATURES
RAW_REQUIRED_COLUMNS = ["timestamp", "service", *NUMERIC_FEATURES]


def _validate_raw(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in RAW_REQUIRED_COLUMNS if c not in df.columns]
    if missing: raise ValueError(f"Dataset is missing required columns: {missing}")
    frame = df.copy()
    frame["service"] = frame["service"].astype(str).str.strip()
    unknown = sorted(set(frame["service"].dropna()) - set(SERVICES))
    if unknown: raise ValueError(f"Unknown service name(s): {unknown}")
    for col in NUMERIC_FEATURES: frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if frame[NUMERIC_FEATURES].isna().any().any():
        bad = frame[NUMERIC_FEATURES].columns[frame[NUMERIC_FEATURES].isna().any()].tolist()
        raise ValueError(f"Missing or non-numeric metric values in: {bad}")
    if not (frame[NUMERIC_FEATURES] >= 0).all().all(): raise ValueError("Metric values cannot be negative.")
    return frame


def prepare_training_dataset(input_csv: str | Path, output_csv: str | Path) -> pd.DataFrame:
    raw = pd.read_csv(input_csv)
    frame = _validate_raw(raw)
    encoded = pd.get_dummies(frame[NUMERIC_FEATURES + ["service"]], columns=["service"], prefix="service", dtype=int)
    encoded = encoded.reindex(columns=MODEL_FEATURES, fill_value=0)
    if encoded.empty: raise ValueError("Training dataset is empty.")
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    encoded.to_csv(output_csv, index=False)
    return encoded


def build_model_input(observation: dict, expected_features: Iterable[str]) -> pd.DataFrame:
    frame = _validate_raw(pd.DataFrame([observation]))
    encoded = pd.get_dummies(frame[NUMERIC_FEATURES + ["service"]], columns=["service"], prefix="service", dtype=int)
    return encoded.reindex(columns=list(expected_features), fill_value=0)
