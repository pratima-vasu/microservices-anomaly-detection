
from pathlib import Path

import pandas as pd
import streamlit as st
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_FILE = PROJECT_ROOT / "test" / "test_dataset.csv"

st.set_page_config(
    page_title="Model Evaluation",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Model Evaluation")
st.caption(
    "Evaluation is calculated from the observations "
    "stored in test_dataset.csv."
)


# --------------------------------------------------
# LOAD DATASET
# --------------------------------------------------

if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
    st.warning(
        "No test dataset found. Go to Live Prediction, "
        "press START, collect observations, then press STOP."
    )
    st.page_link(
        "Prediction.py",
        label="← Back to Live Prediction",
        icon="🔴",
    )
    st.stop()

try:
    df = pd.read_csv(CSV_FILE)
except Exception as error:
    st.error(f"Could not read test dataset: {error}")
    st.stop()

if df.empty:
    st.warning(
        "The test dataset is empty. Start the Live Prediction pipeline, "
        "collect normal and supported fault-injection observations, then return here."
    )
    st.page_link("Prediction.py", label="← Back to Live Prediction", icon="🔴")
    st.stop()

required = {"actual_label", "prediction"}

if not required.issubset(df.columns):
    st.error(
        "CSV must contain actual_label and prediction columns."
    )
    st.stop()


# --------------------------------------------------
# NORMALIZE LABELS
# NORMAL = 0, ANOMALY = 1
# --------------------------------------------------

def normalize_label(series):
    values = series.astype("string").str.strip().str.upper()

    mapping = {
        "NORMAL": 0,
        "ANOMALY": 1,
        "0": 0,
        "1": 1,
        "0.0": 0,
        "1.0": 1,
    }

    return values.map(mapping)


df["actual_numeric"] = normalize_label(df["actual_label"])
df["predicted_numeric"] = normalize_label(df["prediction"])


# --------------------------------------------------
# SUMMARY COUNTS
# --------------------------------------------------

total = len(df)
transition_mask = df["actual_label"].astype("string").str.strip().str.upper().eq("TRANSITION")
transition_count = int(transition_mask.sum())

valid_actual = df["actual_numeric"].notna()

normal_count = int(
    (df["actual_numeric"] == 0).sum()
)

anomaly_count = int(
    (df["actual_numeric"] == 1).sum()
)

a, b, c, d = st.columns(4)

a.metric("Total Observations", total)
b.metric("Labeled Observations", int(valid_actual.sum()))
c.metric("Actual Normal", normal_count)
d.metric("Actual Anomaly", anomaly_count)
st.metric("Transition Observations (Excluded)", transition_count)

st.caption(
    "NORMAL = 0 and ANOMALY = 1 for evaluation. "
    "Unknown or missing labels are excluded."
)

st.write("")


# --------------------------------------------------
# CALCULATE MODEL PERFORMANCE
# --------------------------------------------------

if st.button(
    "📈 CALCULATE MODEL PERFORMANCE",
    type="primary",
    use_container_width=True,
):
    with st.spinner("Calculating model performance..."):

        # Exclude TRANSITION rows from performance calculations.
        ev = df.loc[
            ~transition_mask
            & df["actual_numeric"].notna()
            & df["predicted_numeric"].notna()
        ].copy()

        if ev.empty:
            st.error(
                "No valid labeled observations available. "
                "Check actual_label and prediction in the CSV."
            )
            st.stop()

        y_true = ev["actual_numeric"].astype(int)
        y_pred = ev["predicted_numeric"].astype(int)

        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(
            y_true, y_pred, zero_division=0
        )
        rec = recall_score(
            y_true, y_pred, zero_division=0
        )
        f1 = f1_score(
            y_true, y_pred, zero_division=0
        )

        matrix = confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        )

        actual_classes = set(y_true.unique())

    st.subheader("Model Performance")

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Accuracy", f"{acc * 100:.2f}%")
    m2.metric("Precision", f"{prec * 100:.2f}%")
    m3.metric("Recall", f"{rec * 100:.2f}%")
    m4.metric("F1 Score", f"{f1 * 100:.2f}%")

    st.subheader("Confusion Matrix")

    cm = pd.DataFrame(
        matrix,
        index=["Actual NORMAL", "Actual ANOMALY"],
        columns=[
            "Predicted NORMAL",
            "Predicted ANOMALY",
        ],
    )

    st.dataframe(cm, use_container_width=True)

    st.caption(
        f"Metrics calculated from {len(ev)} observations; "
        f"{transition_count} TRANSITION observations excluded."
    )

    if actual_classes != {0, 1}:
        st.warning(
            "The evaluation dataset does not contain both "
            "actual NORMAL and actual ANOMALY examples. "
            "Collect observations with fault injection enabled "
            "and disabled before drawing conclusions about "
            "fault-detection performance."
        )


# --------------------------------------------------
# DATASET DOWNLOAD
# --------------------------------------------------

st.divider()
st.subheader("Test Dataset")

st.write(
    "Download the complete test dataset to inspect "
    "the collected metrics, labels, predictions and scores."
)

st.download_button(
    "⬇️ DOWNLOAD TEST DATASET CSV",
    data=CSV_FILE.read_bytes(),
    file_name="test_dataset.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(f"Stored observations: {len(df)}")

st.divider()

st.page_link(
    "Prediction.py",
    label="← Back to Live Prediction",
    icon="🔴",
)
