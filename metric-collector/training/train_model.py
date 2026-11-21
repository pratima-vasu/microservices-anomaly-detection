
"""Train Isolation Forest from the prepared normal-workload dataset."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import sys
import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

# Make project-level modules, including storage.py, importable.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage import save_trained_model
from data_preprocessing.feature_engineering import calculate_response_time_medians

DATA_FILE = HERE / "normal_dataset_ml_ready.csv"
RAW_DATA_FILE = HERE / "normal_dataset.csv"
MODEL_FILE = PROJECT_ROOT / "isolation_forest_model.pkl"
BACKUP_FILE = PROJECT_ROOT / "isolation_forest_model.previous.pkl"

EXPECTED_FEATURES = [
    "request_rate",
    "error_count",
    "thread_count",
    "cpu_usage",
    "response_time",
    "service_order-service",
    "service_product-service",
    "service_user-service",
]


def calculate_metric_thresholds(raw: pd.DataFrame) -> dict:
    """Derive service-specific anomaly limits from the fixed normal dataset."""
    required = [
        "service", "request_rate", "error_count",
        "thread_count", "cpu_usage", "response_time",
    ]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"Raw training dataset is missing columns: {missing}")

    frame = raw.copy()
    frame["service"] = frame["service"].astype(str).str.strip()
    for column in required[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    thresholds = {}
    for service in ("order-service", "product-service", "user-service"):
        service_rows = frame.loc[frame["service"] == service]
        if service_rows.empty:
            raise ValueError(f"No normal training observations for {service}")

        active_response = service_rows.loc[
            (service_rows["request_rate"] > 0)
            & (service_rows["response_time"] > 0),
            "response_time",
        ]
        if active_response.empty:
            raise ValueError(
                f"No active response-time samples available for {service}"
            )

        thresholds[service] = {
            "thread_count_max": float(service_rows["thread_count"].max()),
            "cpu_usage_max": float(service_rows["cpu_usage"].max()),
            "cpu_usage_q99": float(service_rows["cpu_usage"].quantile(0.99)),
            "error_count_max": float(service_rows["error_count"].max()),
            "response_time_max": float(active_response.max()),
            "response_time_median": float(active_response.median()),
        }

    return thresholds


def train_model():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Prepared dataset not found: {DATA_FILE}"
        )

    X = pd.read_csv(DATA_FILE)

    if X.empty:
        raise ValueError("Training dataset is empty.")

    if X.isna().any().any():
        raise ValueError("Training dataset contains missing values.")

    if not all(
        pd.api.types.is_numeric_dtype(X[column])
        for column in X.columns
    ):
        raise ValueError("All model features must be numeric.")

    if X.columns.tolist() != EXPECTED_FEATURES:
        raise ValueError(
            f"Feature columns/order mismatch. "
            f"Expected {EXPECTED_FEATURES}; "
            f"found {X.columns.tolist()}"
        )

    if not RAW_DATA_FILE.exists():
        raise FileNotFoundError(f"Raw training dataset not found: {RAW_DATA_FILE}")
    response_time_medians = calculate_response_time_medians(pd.read_csv(RAW_DATA_FILE))
    metric_thresholds = calculate_metric_thresholds(pd.read_csv(RAW_DATA_FILE))

    # Isolation Forest configuration for the 0.025 contamination experiment.
    model = IsolationForest(
        n_estimators=100,
        contamination=0.025,
        random_state=42
    )

    model.fit(X)

    # Save the newly trained model to a temporary file first.
    temp_file = MODEL_FILE.with_suffix(".tmp")

    # Keep one shared Isolation Forest; store reproducibility metadata
    # alongside it so the exact training artifact can be audited.
    metadata = {
        "training_rows": int(len(X)),
        "feature_names": X.columns.tolist(),
        "training_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(DATA_FILE.read_bytes()).hexdigest(),
        "contamination": model.contamination,
        "offset": float(model.offset_),
        "sklearn_version": sklearn.__version__,
        "response_time_medians": response_time_medians,
        "metric_thresholds": metric_thresholds,
    }

    joblib.dump(
        {
            "model": model,
            "features": X.columns.tolist(),
            "metadata": metadata,
        },
        temp_file
    )

    # Preserve the previous local model as a backup.
    if MODEL_FILE.exists():
        try:
            BACKUP_FILE.write_bytes(MODEL_FILE.read_bytes())
        except OSError:
            pass

    # Replace the local model atomically.
    os.replace(temp_file, MODEL_FILE)

    # Persist the newly trained model in TiDB.
    # This replaces the previous current model in the database.
    save_trained_model(MODEL_FILE)

    return len(X), X.columns.tolist(), MODEL_FILE


if __name__ == "__main__":
    rows, features, path = train_model()

    print("Training completed successfully")
    print(f"Training observations: {rows}")
    print(f"Features ({len(features)}): {features}")
    print(f"Model saved locally: {path}")
    print("Latest trained model saved in TiDB.")
