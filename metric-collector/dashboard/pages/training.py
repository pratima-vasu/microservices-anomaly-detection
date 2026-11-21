
from pathlib import Path
import subprocess
import joblib
import sys

import pandas as pd
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DASHBOARD_DIR.parent
TRAIN_DIR = PROJECT_ROOT / "training"
PREPROCESS_DIR = PROJECT_ROOT / "data_preprocessing"

NORMAL_CSV = TRAIN_DIR / "normal_dataset.csv"
ML_READY_CSV = TRAIN_DIR / "normal_dataset_ml_ready.csv"
COLLECTOR_SCRIPT = TRAIN_DIR / "metric_collector.py"
MODEL_FILE = PROJECT_ROOT / "isolation_forest_model.pkl"

sys.path.insert(0, str(PROJECT_ROOT))

from deployment.prometheus_manager import start_prometheus, stop_prometheus
from storage import clear_training_observations, restore_training_csv

LOG_FILE = TRAIN_DIR / "training_collector.log"

st.set_page_config(
    page_title="Model Training",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Model Training")

st.caption(
    "Collect confirmed normal workload → validate → preprocess → train Isolation Forest"
)

# RESTORE THE EXISTING TRAINING DATASET FROM TIDB AFTER A FRESH DEPLOY
if not NORMAL_CSV.exists():
    try:
        restored_rows = restore_training_csv()
        if restored_rows:
            st.info(
                f"Restored {restored_rows:,} existing training observations from TiDB. "
                "Prepare the training dataset before retraining."
            )
    except Exception as exc:
        st.error(f"Could not restore the existing training dataset from TiDB: {exc}")



# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "training_process" not in st.session_state:
    st.session_state.training_process = None

if "validation_ok" not in st.session_state:
    st.session_state.validation_ok = None


# --------------------------------------------------
# COLLECTION CONTROL
# --------------------------------------------------

def is_running():
    process = st.session_state.training_process

    return (
        process is not None
        and process.poll() is None
    )


def start_collection():
    if is_running():
        return

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    log_handle = open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    )

    try:
        start_prometheus()

        process = subprocess.Popen(
            [sys.executable, "-u", str(COLLECTOR_SCRIPT)],
            cwd=str(TRAIN_DIR),
            stdout=log_handle,
            stderr=subprocess.STDOUT
        )

        st.session_state.training_process = process
        st.session_state.training_log_handle = log_handle

    except Exception:
        stop_prometheus()
        log_handle.close()
        raise


def stop_collection():
    process = st.session_state.training_process

    if process is not None and process.poll() is None:
        process.terminate()

        try:
            process.wait(timeout=5)

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    handle = st.session_state.get(
        "training_log_handle"
    )

    if handle:
        handle.close()
        st.session_state.training_log_handle = None

    st.session_state.training_process = None
    stop_prometheus()


# --------------------------------------------------
# FEATURE ENGINEERING
# --------------------------------------------------

def run_preparation():
    from data_preprocessing.feature_engineering import (
        prepare_training_dataset
    )

    return prepare_training_dataset(
        NORMAL_CSV,
        ML_READY_CSV
    )


# --------------------------------------------------
# STEP 1 — COLLECT NORMAL DATASET
# --------------------------------------------------

st.subheader("Step 1 — Collect Normal Dataset")

left, right = st.columns([1, 2])

with left:

    st.metric(
        "Collection interval",
        "5 seconds"
    )

    if st.button(
        "▶ Start Normal Collection",
        type="primary",
        use_container_width=True,
        disabled=is_running()
    ):
        try:
            start_collection()
            st.success("Normal metric collection started.")

        except Exception as exc:
            st.error(
                f"Could not start collector: {exc}"
            )

    if st.button(
        "⏹ Stop Collection",
        use_container_width=True,
        disabled=not is_running()
    ):
        try:
            stop_collection()
            st.success("Collection stopped.")

        except Exception as exc:
            st.error(
                f"Could not stop collection: {exc}"
            )

    if st.button(
        "🗑 Clear Normal Dataset",
        use_container_width=True,
        disabled=is_running()
    ):

        try:
            # Delete persisted training observations.
            # This does NOT delete the trained model.
            clear_training_observations()

            # Delete both local training CSV files.
            NORMAL_CSV.unlink(missing_ok=True)
            ML_READY_CSV.unlink(missing_ok=True)

            # Clear old validation/preparation status.
            st.session_state.validation_ok = None
            st.session_state.pop(
                "validation_report",
                None
            )
            st.session_state.pop(
                "validation_errors",
                None
            )
            st.session_state.pop(
                "prepared_rows",
                None
            )

            st.success(
                "Training dataset and prepared dataset cleared "
                "from CSV and TiDB. Existing trained model is retained."
            )

        except Exception as exc:
            st.error(
                f"Could not clear training dataset: {exc}"
            )


with right:

    if is_running():
        st.success("● NORMAL COLLECTION RUNNING")
    else:
        st.info("● NORMAL COLLECTION STOPPED")

    if NORMAL_CSV.exists():

        try:
            raw = pd.read_csv(NORMAL_CSV)

            st.write(
                f"Collected observations: **{len(raw):,}**"
            )

            if "service" in raw.columns:
                st.dataframe(
                    raw.groupby("service")
                    .size()
                    .rename("Rows")
                    .to_frame(),
                    use_container_width=True
                )

            st.caption(
                f"Dataset: {NORMAL_CSV}"
            )

            st.download_button(
                label="⬇ Download Normal Dataset CSV",
                data=raw.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="normal_dataset.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_normal_dataset"
            )

        except Exception as exc:
            st.error(
                f"Unable to read normal dataset: {exc}"
            )

    else:
        st.caption(
            "No normal dataset yet. Start collection after starting "
            "all three services and Prometheus."
        )


# --------------------------------------------------
# STEP 2 — VALIDATE NORMAL DATASET
# --------------------------------------------------

st.divider()

st.subheader("Step 2 — Validate Normal Dataset")

if st.button(
    "✓ Validate Dataset",
    use_container_width=False
):

    try:
        from data_preprocessing.validate_dataset import (
            validate_dataset
        )

        ok, errors, report = validate_dataset(
            NORMAL_CSV
        )

        st.session_state.validation_ok = ok
        st.session_state.validation_report = report
        st.session_state.validation_errors = errors

    except Exception as exc:
        st.session_state.validation_ok = False
        st.session_state.validation_errors = [str(exc)]


if st.session_state.validation_ok is not None:

    if st.session_state.validation_ok:
        st.success("Validation passed")

        st.json(
            st.session_state.validation_report
        )

    else:
        st.error("Validation failed")

        for error in st.session_state.validation_errors:
            st.write(f"- {error}")


# --------------------------------------------------
# STEP 3 — PREPARE TRAINING DATASET
# --------------------------------------------------

st.divider()

st.subheader("Step 3 — Prepare Training Dataset")

st.write(
    "The shared preprocessing module applies the same five numeric "
    "metrics and fixed one-hot service columns used by live inference."
)

if st.button(
    "⚙ Prepare Training Dataset",
    use_container_width=False
):

    try:
        from data_preprocessing.validate_dataset import (
            validate_dataset
        )

        ok, errors, report = validate_dataset(
            NORMAL_CSV
        )

        if not ok:
            raise ValueError(
                "Validation failed: " + "; ".join(errors)
            )

        prepared = run_preparation()

        st.session_state.prepared_rows = len(prepared)

        st.success(
            f"Prepared {len(prepared)} observations "
            f"with {len(prepared.columns)} features."
        )

        st.dataframe(
            prepared.head(10),
            use_container_width=True
        )

        st.caption(
            f"Saved: {ML_READY_CSV}"
        )

    except Exception as exc:
        st.error(
            f"Preprocessing failed: {exc}"
        )


# --------------------------------------------------
# STEP 4 — TRAIN ISOLATION FOREST
# --------------------------------------------------

st.divider()

st.subheader("Step 4 — Train Isolation Forest")

if ML_READY_CSV.exists():

    try:
        prepared = pd.read_csv(ML_READY_CSV)

        st.write(
            f"Prepared dataset: **{len(prepared):,} rows × "
            f"{len(prepared.columns)} features**"
        )

    except Exception as exc:
        st.error(
            f"Unable to read prepared dataset: {exc}"
        )

else:
    st.info(
        "Prepare the training dataset before training the model."
    )


if st.button(
    "🧠 Train / Retrain Model",
    type="primary",
    disabled=(
        not ML_READY_CSV.exists()
        or is_running()
    )
):

    try:
        from training.train_model import train_model

        with st.spinner(
            "Training Isolation Forest and saving model..."
        ):

            rows, features, model_path = train_model()

        st.success(
            "Model training completed successfully."
        )

        st.write(
            f"Training observations: **{rows:,}**"
        )

        st.write(
            f"Features: **{len(features)}**"
        )

        st.write(
            f"Model saved to: `{model_path}`"
        )

        st.info(
            "Latest trained model has also been saved in TiDB. "
            "Stop and restart the live prediction collector "
            "after retraining."
        )

    except Exception as exc:
        st.error(
            f"Training failed: {exc}"
        )


# --------------------------------------------------
# CURRENT MODEL
# --------------------------------------------------

st.divider()

st.subheader("Current Model")
# Restore and display the model currently saved in TiDB.
from storage import restore_trained_model

if restore_trained_model():
    saved = joblib.load(MODEL_FILE)
    metadata = saved.get("metadata", {})
    model = saved["model"]

    st.success("Latest trained model restored from TiDB.")
    details_left, details_right = st.columns(2)
    with details_left:
        st.metric("Contamination", f"{model.contamination:.4f}")
        st.metric("Training rows", metadata.get("training_rows", "Not available"))
        st.write("**Training timestamp (UTC)**")
        st.code(metadata.get("training_timestamp_utc", "Not available"))
    with details_right:
        st.write("**Training dataset SHA-256**")
        st.code(metadata.get("dataset_sha256", "Not available"))
        st.write("**Features used by model**")
        st.write(saved.get("features", []))
        st.write("**scikit-learn version**")
        st.write(metadata.get("sklearn_version", "Not available"))
else:
    st.warning("No saved model found in TiDB.")
if MODEL_FILE.exists():

    st.success(
        f"Model file available — "
        f"{MODEL_FILE.stat().st_size:,} bytes"
    )

else:
    st.warning(
        "No model found at the shared model path. "
        "Train a model before starting live prediction."
    )


# --------------------------------------------------
# COLLECTION LOG
# --------------------------------------------------

if LOG_FILE.exists():

    with st.expander("Normal collection log"):

        st.code(
            LOG_FILE.read_text(
                encoding="utf-8",
                errors="replace"
            )[-5000:] or "No log output yet."
        )


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

st.page_link(
    "app.py",
    label="← Back to Live Prediction"
)
