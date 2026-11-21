
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
TEST_SCRIPT = PROJECT_ROOT / "test" / "test_metric_collector.py"
CSV_FILE = PROJECT_ROOT / "test" / "test_dataset.csv"
MODEL_INFO_FILE = PROJECT_ROOT / "loaded_model_info.json"

sys.path.insert(0, str(PROJECT_ROOT))

from deployment.prometheus_manager import start_prometheus, stop_prometheus
from storage import restore_test_csv, clear_test_observations

SERVICES = {
    "user-service": f"https://{os.getenv('USER_SERVICE_HOST', 'localhost:8082')}".rstrip("/"),
    "product-service": f"https://{os.getenv('PRODUCT_SERVICE_HOST', 'localhost:8083')}".rstrip("/"),
    "order-service": f"https://{os.getenv('ORDER_SERVICE_HOST', 'localhost:8084')}".rstrip("/")
}

FAULT_TYPES = ["ERROR_RATE", "CPU", "RESPONSE_TIME", "THREAD_COUNT"]

st.set_page_config(
    page_title="Microservice Anomaly Detection",
    page_icon="🔴",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:1rem;padding-bottom:1rem;}
.service-card {border-radius:12px;padding:14px;text-align:center;}
.service-card-up {border:1px solid #86d6a5;background:#eaf8ef;}
.service-card-down {border:1px solid #f0a0a0;background:#fff0f0;}
.service-name {font-size:16px;font-weight:700;color:#253247;}
.service-up {color:#167545;font-size:17px;font-weight:800;}
.service-down {color:#b42318;font-size:17px;font-weight:800;}
.anomaly-banner {border:1px solid #ff4b4b;border-radius:9px;padding:8px 12px;color:#ff8f8f;background:rgba(255,50,50,.08);font-weight:700;}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# RESTORE LATEST TEST DATA FROM TIDB
# --------------------------------------------------

if "test_csv_restored" not in st.session_state:
    try:
        restore_test_csv()
        st.session_state.test_csv_restored = True
    except Exception as error:
        st.error(f"Could not restore test dataset from TiDB: {error}")


if "collector" not in st.session_state:
    st.session_state.collector = None


# --------------------------------------------------
# PIPELINE CONTROL
# --------------------------------------------------

def collector_running():
    p = st.session_state.collector

    if p is None:
        return False

    if p.poll() is not None:
        st.session_state.collector = None
        stop_prometheus()
        return False

    return True


def start_pipeline():
    if collector_running():
        return

    if not TEST_SCRIPT.exists():
        st.error(f"Testing script not found: {TEST_SCRIPT}")
        return

    try:
        start_prometheus()

        st.session_state.collector = subprocess.Popen(
            [sys.executable, "-u", str(TEST_SCRIPT)],
            cwd=str(PROJECT_ROOT),
        )

    except Exception as error:
        stop_prometheus()
        st.error(f"Could not start testing pipeline: {error}")


def stop_pipeline():
    p = st.session_state.collector

    if p is None:
        stop_prometheus()
        return

    if p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)

        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)

        except Exception:
            pass

    st.session_state.collector = None
    stop_prometheus()


def clear_run():
    stop_pipeline()

    try:
        # Clear local test CSV.
        CSV_FILE.unlink(missing_ok=True)

        # Clear persisted test observations from TiDB.
        clear_test_observations()

        # Prevent the old database data from being restored
        # again during this Streamlit session.
        st.session_state.test_csv_restored = True

    except PermissionError:
        st.error(
            "Cannot clear test_dataset.csv. "
            "Close it in Excel or another program and try again."
        )

    except Exception as error:
        st.error(f"Could not clear test dataset: {error}")


# --------------------------------------------------
# MICROSERVICE AND FAULT STATUS
# --------------------------------------------------

def service_health(base_url):
    try:
        return requests.get(
            f"{base_url}/actuator/health",
            timeout=8
        ).ok

    except requests.RequestException:
        return False


def get_fault_status(service):
    try:
        r = requests.get(
            f"{SERVICES[service]}/faults/status",
            timeout=8
        )
        r.raise_for_status()
        return r.text.strip().upper()

    except requests.RequestException:
        return "UNAVAILABLE"


def enable_fault(
    service,
    fault_type,
    duration,
    error_percent,
    cpu_millis,
    memory_mb,
    thread_count,
    delay_millis
):
    payload = {
        "type": fault_type,
        "durationSeconds": int(duration),
        "delayMillis": int(delay_millis),
        "errorPercent": int(error_percent),
        "cpuMillis": int(cpu_millis),
        "memoryMb": int(memory_mb),
        "threadCount": int(thread_count),
    }

    r = requests.post(
        f"{SERVICES[service]}/faults/enable",
        json=payload,
        timeout=15
    )

    r.raise_for_status()
    return r.text


def disable_fault(service):
    r = requests.post(
        f"{SERVICES[service]}/faults/disable",
        timeout=15
    )
    r.raise_for_status()
    return r.text


def enable_combined_fault(combination, duration, delay_millis, cpu_millis, error_percent, thread_count):
    payload = {
        "combination": combination,
        "durationSeconds": int(duration),
        "delayMillis": int(delay_millis),
        "cpuMillis": int(cpu_millis),
        "errorPercent": int(error_percent),
        "threadCount": int(thread_count),
    }
    r = requests.post(
        f"{SERVICES['user-service']}/faults/combined/enable",
        json=payload,
        timeout=15
    )
    r.raise_for_status()
    return r.text


def get_combined_fault_status():
    try:
        r = requests.get(f"{SERVICES['user-service']}/faults/combined/status", timeout=8)
        r.raise_for_status()
        return r.text.strip().upper()
    except requests.RequestException:
        return "UNAVAILABLE"


def disable_combined_fault():
    r = requests.post(f"{SERVICES['user-service']}/faults/combined/disable", timeout=15)
    r.raise_for_status()
    return r.text


# --------------------------------------------------
# TEST DATASET
# --------------------------------------------------

def read_dataset():
    if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(CSV_FILE)

    except (pd.errors.EmptyDataError, PermissionError):
        return pd.DataFrame()


def format_live_table(df):
    if df.empty:
        return pd.DataFrame()

    columns = [
        "timestamp",
        "service",
        "request_rate",
        "error_count",
        "thread_count",
        "cpu_usage",
        "response_time",
        "actual_label",
        "fault_type",
        "prediction",
        "anomaly_score"
    ]

    columns = [c for c in columns if c in df.columns]

    labels = {
        "timestamp": "Time",
        "service": "Service",
        "request_rate": "Requests/s",
        "error_count": "Errors",
        "thread_count": "Threads",
        "cpu_usage": "CPU %",
        "response_time": "Response s",
        "actual_label": "Actual",
        "fault_type": "Fault Type",
        "prediction": "Prediction",
        "anomaly_score": "Score"
    }

    out = df[columns].copy()
    out.rename(columns=labels, inplace=True)

    return out


def style_live_table(df):
    if df.empty:
        return df

    def prediction_style(v):
        v = str(v).upper()

        return (
            "color:#ff4b4b;font-weight:800;"
            if v == "ANOMALY"
            else (
                "color:#63d995;font-weight:700;"
                if v == "NORMAL"
                else ""
            )
        )

    def fault_style(v):
        return (
            "color:#ffb454;font-weight:700;"
            if str(v).upper() not in {"NONE", "NAN", ""}
            else ""
        )

    styler = df.style

    if "Prediction" in df.columns:
        styler = styler.map(
            prediction_style,
            subset=["Prediction"]
        )

    if "Fault Type" in df.columns:
        styler = styler.map(
            fault_style,
            subset=["Fault Type"]
        )

    return styler


# --------------------------------------------------
# DASHBOARD UI
# --------------------------------------------------

st.title("🔴 Real-Time Microservice Anomaly Detection")

st.caption(
    "Prometheus → Metric Collection → Feature Engineering "
    "→ Isolation Forest → Live Prediction"
)

with st.expander("Loaded model verification", expanded=True):
    if MODEL_INFO_FILE.exists():
        try:
            model_info = json.loads(MODEL_INFO_FILE.read_text(encoding="utf-8"))
            st.success("Model metadata from the model loaded by the testing collector")
            st.write("Training timestamp (UTC):", model_info.get("training_timestamp_utc") or "Unavailable")
            st.write("Dataset SHA-256:", model_info.get("dataset_sha256") or "Unavailable")
            st.write("Training rows:", model_info.get("training_rows") or "Unavailable")
            st.write("Contamination:", model_info.get("contamination", "Unavailable"))
            st.write("Loaded at:", model_info.get("loaded_at_utc") or "Unavailable")
            st.write("Features:", model_info.get("features", []))
        except (OSError, json.JSONDecodeError) as error:
            st.warning(f"Could not read loaded model metadata: {error}")
    else:
        st.info("Start the testing pipeline to display the exact model loaded from TiDB.")

st.subheader("Microservice Status")

cols = st.columns(3)

for col, (service, base_url) in zip(cols, SERVICES.items()):
    up = service_health(base_url)

    with col:
        cls = "service-up" if up else "service-down"
        card_cls = "service-card-up" if up else "service-card-down"
        text = "● UP" if up else "● DOWN"

        st.markdown(
            f'<div class="service-card {card_cls}">'
            f'<div class="service-name">{service.upper()}</div>'
            f'<div class="{cls}">{text}</div></div>',
            unsafe_allow_html=True
        )


st.write("")

c1, c2, c3, c4 = st.columns([1, 1, 1, 2.4])

with c1:
    if st.button(
        "▶ START",
        use_container_width=True,
        disabled=collector_running()
    ):
        with st.spinner("Starting testing pipeline..."):
            start_pipeline()

        st.rerun()


with c2:
    if st.button(
        "⏹ STOP",
        use_container_width=True,
        disabled=not collector_running()
    ):
        with st.spinner("Stopping testing pipeline..."):
            stop_pipeline()

        st.rerun()


with c3:
    if st.button("🗑 CLEAR", use_container_width=True):
        with st.spinner(
            "Stopping pipeline and clearing test dataset..."
        ):
            clear_run()

        st.rerun()


with c4:
    if collector_running():
        st.success("● TESTING PIPELINE RUNNING")
    else:
        st.info("● TESTING PIPELINE STOPPED")


left, right = st.columns([0.85, 2.15], gap="large")


# --------------------------------------------------
# FAULT INJECTION
# --------------------------------------------------

with left:
    st.subheader("⚡ Fault Injection")

    service = st.selectbox(
        "Service",
        list(SERVICES.keys())
    )

    fault_type = st.selectbox(
        "Fault Type",
        FAULT_TYPES
    )

    duration = st.number_input(
        "Duration (seconds)",
        min_value=1,
        max_value=300,
        value=60,
        step=1
    )

    delay_millis = 2000
    error_percent = 50
    cpu_millis = 100
    memory_mb = 50
    thread_count = 5

    if fault_type == "ERROR_RATE":
        error_percent = st.number_input(
            "Error percentage",
            min_value=1,
            max_value=50,
            value=50
        )

    elif fault_type == "CPU":
        cpu_millis = st.number_input(
            "CPU work per request (ms)",
            min_value=1,
            max_value=200,
            value=200
        )

    elif fault_type == "RESPONSE_TIME":
        delay_millis = st.number_input(
            "Delay (ms)",
            min_value=1,
            max_value=6000,
            value=2000
        )

    elif fault_type == "THREAD_COUNT":
        thread_count = st.number_input(
            "Additional threads",
            min_value=1,
            max_value=25,
            value=5
        )

    if st.button(
        "🔴 ENABLE FAULT",
        type="primary",
        use_container_width=True
    ):
        try:
            with st.spinner(
                f"Enabling {fault_type} on {service}..."
            ):
                result = enable_fault(
                    service,
                    fault_type,
                    duration,
                    error_percent,
                    cpu_millis,
                    memory_mb,
                    thread_count,
                    delay_millis
                )

            st.success(result)

        except Exception as error:
            st.error(f"Fault enable failed: {error}")

    if st.button(
        "↩ DISABLE FAULT",
        use_container_width=True
    ):
        try:
            with st.spinner(
                f"Disabling fault on {service}..."
            ):
                result = disable_fault(service)

            st.success(result)

        except Exception as error:
            st.error(f"Fault disable failed: {error}")

    status = get_fault_status(service)

    if status != "NONE" and status != "UNAVAILABLE":
        st.warning(
            f"🔴 ACTIVE FAULT — {service} — {status}"
        )

    elif status == "NONE":
        st.success(f"🟢 {service} — NORMAL")

    else:
        st.info(f"Status: {status}")


# --------------------------------------------------
# LIVE PREDICTIONS
# --------------------------------------------------

with right:
    st.subheader("📡 Live Predictions")

    @st.fragment(run_every=5)
    def live_prediction():
        df = read_dataset()

        if df.empty:
            st.info(
                "No observations yet. Press START to begin "
                "the testing pipeline."
            )
            return

        live_df = df.tail(30).copy()
        display_df = format_live_table(live_df)

        st.caption(
            f"Showing latest {len(display_df)} collected "
            f"observations | Total stored in CSV: {len(df)}"
        )

        if (
            "Prediction" in display_df.columns
            and display_df["Prediction"]
            .astype(str)
            .str.upper()
            .eq("ANOMALY")
            .any()
        ):
            st.markdown(
                '<div class="anomaly-banner">'
                '🔴 ANOMALY DETECTED</div>',
                unsafe_allow_html=True
            )

        st.dataframe(
            style_live_table(display_df),
            use_container_width=True,
            hide_index=True,
            height=570
        )

    live_prediction()


with left:
    st.divider()
    st.subheader("⚡ Combined Faults — User Service")
    combined_type = st.selectbox(
        "Combined fault type",
        ["CPU+RESPONSE_TIME", "THREAD_COUNT+ERROR_RATE", "ERROR_RATE+RESPONSE_TIME"],
        format_func=lambda x: x.replace("+", " + ")
    )
    combined_duration = st.number_input("Combined duration (seconds)", min_value=1, max_value=300, value=60, key="combined_duration")
    combined_delay = 3000
    combined_cpu = 100
    combined_error = 50
    combined_threads = 10
    if combined_type == "CPU+RESPONSE_TIME":
        combined_cpu = st.number_input("CPU work per request (ms)", min_value=1, max_value=200, value=100, key="combined_cpu")
        combined_delay = st.number_input("Response delay (ms)", min_value=1, max_value=6000, value=3000, key="combined_delay_cpu")
    elif combined_type == "THREAD_COUNT+ERROR_RATE":
        combined_threads = st.number_input("Additional threads", min_value=1, max_value=25, value=10, key="combined_threads")
        combined_error = st.number_input("Error percentage", min_value=1, max_value=50, value=50, key="combined_error_threads")
    else:
        combined_error = st.number_input("Error percentage", min_value=1, max_value=50, value=50, key="combined_error_response")
        combined_delay = st.number_input("Response delay (ms)", min_value=1, max_value=6000, value=3000, key="combined_delay_error")
    if st.button("🔴 ENABLE COMBINED FAULT", type="primary", use_container_width=True):
        try:
            with st.spinner(f"Enabling {combined_type} on User Service..."):
                result = enable_combined_fault(combined_type, combined_duration, combined_delay, combined_cpu, combined_error, combined_threads)
            st.success(result)
        except Exception as error:
            st.error(f"Combined fault enable failed: {error}")
    if st.button("↩ DISABLE COMBINED FAULT", use_container_width=True):
        try:
            st.success(disable_combined_fault())
        except Exception as error:
            st.error(f"Combined fault disable failed: {error}")
    combined_status = get_combined_fault_status()
    if combined_status not in {"NONE", "UNAVAILABLE"}:
        st.warning(f"🔴 USER SERVICE — COMBINED FAULT ACTIVE: {combined_status}")
    elif combined_status == "NONE":
        st.success("🟢 USER SERVICE — NO COMBINED FAULT")
    else:
        st.info(f"Combined fault status: {combined_status}")


st.divider()

st.page_link(
    "pages/training.py",
    label="🧠 Open Model Training",
    icon="🧠"
)

st.page_link(
    "pages/evaluation.py",
    label="📊 Open Model Evaluation",
    icon="📊"
)

st.caption(
    "START → inject fault → show red ANOMALY → STOP. "
    "START again continues appending to the same CSV until CLEAR."
)
