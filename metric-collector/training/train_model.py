"""Train Isolation Forest from the prepared normal-workload dataset."""
from pathlib import Path
import os
import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DATA_FILE = HERE / "normal_dataset_ml_ready.csv"
MODEL_FILE = PROJECT_ROOT / "isolation_forest_model.pkl"
BACKUP_FILE = PROJECT_ROOT / "isolation_forest_model.previous.pkl"
EXPECTED_FEATURES = [
    "request_rate", "error_count", "thread_count",
    "cpu_usage", "response_time", "service_order-service",
    "service_product-service", "service_user-service",
]

def train_model():
    if not DATA_FILE.exists(): raise FileNotFoundError(f"Prepared dataset not found: {DATA_FILE}")
    X = pd.read_csv(DATA_FILE)
    if X.empty: raise ValueError("Training dataset is empty.")
    if X.isna().any().any(): raise ValueError("Training dataset contains missing values.")
    if not all(pd.api.types.is_numeric_dtype(X[c]) for c in X.columns): raise ValueError("All model features must be numeric.")
    if X.columns.tolist() != EXPECTED_FEATURES:
        raise ValueError(f"Feature columns/order mismatch. Expected {EXPECTED_FEATURES}; found {X.columns.tolist()}")
    model = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
    model.fit(X)
    temp_file = MODEL_FILE.with_suffix(".tmp")
    joblib.dump({"model": model, "features": X.columns.tolist()}, temp_file)
    if MODEL_FILE.exists():
        try: BACKUP_FILE.write_bytes(MODEL_FILE.read_bytes())
        except OSError: pass
    os.replace(temp_file, MODEL_FILE)
    return len(X), X.columns.tolist(), MODEL_FILE

if __name__ == "__main__":
    rows, features, path = train_model()
    print("Training completed successfully")
    print(f"Training observations: {rows}")
    print(f"Features ({len(features)}): {features}")
    print(f"Model saved: {path}")
