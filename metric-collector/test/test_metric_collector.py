
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data_preprocessing.feature_engineering import build_model_input
from storage import (
    clear_test_observations,
    insert_test_observations,
    restore_trained_model,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://localhost:9090"
).rstrip("/")

HERE = Path(__file__).resolve().parent
MODEL_FILE = PROJECT_ROOT / "isolation_forest_model.pkl"
MODEL_INFO_FILE = PROJECT_ROOT / "loaded_model_info.json"
CSV_FILE = HERE / "test_dataset.csv"

COLLECTION_INTERVAL = 5

SERVICES = [
    "user-service",
    "product-service",
    "order-service",
]

FAULT_STATUS_URLS = {
    "user-service": os.getenv(
        "USER_SERVICE_URL",
        "http://localhost:8082"
    ).rstrip("/") + "/faults/status",

    "product-service": os.getenv(
        "PRODUCT_SERVICE_URL",
        "http://localhost:8083"
    ).rstrip("/") + "/faults/status",

    "order-service": os.getenv(
        "ORDER_SERVICE_URL",
        "http://localhost:8084"
    ).rstrip("/") + "/faults/status",
}

SUPPORTED_FAULTS = {
    "RESPONSE_TIME",
    "ERROR_RATE",
    "CPU",
    "THREAD_COUNT",
}

METRIC_COLUMNS = [
    "request_rate",
    "error_count",
    "thread_count",
    "cpu_usage",
    "response_time",
]

OUTPUT_COLUMNS = [
    "timestamp",
    "service",
    *METRIC_COLUMNS,
    "actual_label",
    "fault_type",
    "prediction",
    "anomaly_score",
]


# --------------------------------------------------
# PROMETHEUS QUERIES
# --------------------------------------------------

QUERIES = {
 "request_rate": """sum by (job) (rate(http_server_requests_seconds_count{uri!~"/actuator.*"}[15s])) or on (job) (0 * max by (job) (up))""",
 "error_count": """sum by (job) (increase(http_server_requests_seconds_count{uri!~"/actuator.*", status=~"4..|5.."}[15s])) or on (job) (0 * max by (job) (up))""",
 "thread_count": """sum by (job) (jvm_threads_live_threads)""",
 "cpu_usage": """avg by (job) (process_cpu_usage) * 100""",
 "response_time": """sum by (job) (rate(http_server_requests_seconds_sum{uri!~"/actuator.*"}[15s])) / sum by (job) (rate(http_server_requests_seconds_count{uri!~"/actuator.*"}[15s]))""",
}


# --------------------------------------------------
# PROMETHEUS FETCHING
# --------------------------------------------------

def query_prometheus(query):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=10,
    )

    response.raise_for_status()
    result = response.json()

    if result.get("status") != "success":
        raise RuntimeError(
            f"Prometheus query failed: {result}"
        )

    return result["data"]["result"]


def get_metric_values(query):
    values = {}

    for result in query_prometheus(query):
        service = result.get("metric", {}).get("job")

        if service not in SERVICES:
            continue

        try:
            value = float(result["value"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue

        if math.isfinite(value):
            values[service] = value

    return values


# --------------------------------------------------
# FAULT STATUS AND ACTUAL LABEL
# --------------------------------------------------

def get_fault_status(service):
    try:
        response = requests.get(FAULT_STATUS_URLS[service], timeout=5)
        response.raise_for_status()
        status = response.text.strip().upper()
        for fault in SUPPORTED_FAULTS:
            if fault in status: return fault, True
        if status in {"NONE","NORMAL","DISABLED","FALSE","INACTIVE","0",""}: return "NONE", False
        if status in {"ACTIVE","ENABLED","FAULT","TRUE","1"}: return "ACTIVE", True
        print(f"WARNING: Unknown fault status for {service}: {status!r}")
        return "UNKNOWN", None
    except requests.RequestException as error:
        print(f"WARNING: Cannot read fault status for {service}: {error}")
        return "UNKNOWN", None


TRANSITION_SECONDS = 20
FAULT_STATES = {s: {"active": False, "fault_type": "NONE", "changed_at": None, "recovering": False, "known": False} for s in SERVICES}


def classify_actual_state(service, fault_type, active, now):
    state = FAULT_STATES[service]
    if active is None:
        if not state["known"]:
            return "UNKNOWN", None
        if state["active"]:
            elapsed = (now - state["changed_at"]).total_seconds()
            return state["fault_type"], "TRANSITION" if elapsed < TRANSITION_SECONDS else "ANOMALY"
        if state["recovering"]:
            elapsed = (now - state["changed_at"]).total_seconds()
            if elapsed < TRANSITION_SECONDS: return state["fault_type"], "TRANSITION"
            state.update(recovering=False, fault_type="NONE", changed_at=None)
        return "NONE", "NORMAL"
    if active:
        state["known"] = True
        if not state["active"]:
            state.update(active=True, fault_type=fault_type if fault_type != "ACTIVE" else "UNKNOWN", changed_at=now, recovering=False)
        elif fault_type not in {"ACTIVE", "UNKNOWN"}:
            state["fault_type"] = fault_type
        elapsed = (now - state["changed_at"]).total_seconds()
        return state["fault_type"], "TRANSITION" if elapsed < TRANSITION_SECONDS else "ANOMALY"
    state["known"] = True
    if state["active"]:
        state.update(active=False, changed_at=now, recovering=True)
        return state["fault_type"], "TRANSITION"
    if state["recovering"]:
        elapsed = (now - state["changed_at"]).total_seconds()
        if elapsed < TRANSITION_SECONDS: return state["fault_type"], "TRANSITION"
        state.update(recovering=False, fault_type="NONE", changed_at=None)
    return "NONE", "NORMAL"



# --------------------------------------------------
# LOAD SAVED MODEL
# --------------------------------------------------

def load_model():
    # Restore the latest trained model from TiDB first.
    restore_trained_model()

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_FILE}\n"
            "Train the model before starting test collection."
        )

    saved = joblib.load(MODEL_FILE)

    if (
        not isinstance(saved, dict)
        or "model" not in saved
        or "features" not in saved
    ):
        raise ValueError(
            "Unexpected model format. Expected a dictionary "
            "containing 'model' and 'features'."
        )

    model = saved["model"]
    expected_features = list(saved["features"])
    response_time_medians = saved.get("metadata", {}).get("response_time_medians")
    if not response_time_medians:
        raise ValueError("Saved model has no response-time medians. Prepare and retrain before testing.")

    metadata = saved.get("metadata", {})
    runtime_info = {
        "training_timestamp_utc": metadata.get("training_timestamp_utc"),
        "dataset_sha256": metadata.get("dataset_sha256"),
        "training_rows": metadata.get("training_rows"),
        "contamination": float(model.contamination),
        "features": expected_features,
        "sklearn_version": metadata.get("sklearn_version"),
        "loaded_at_utc": datetime.now().astimezone().isoformat(),
    }
    MODEL_INFO_FILE.write_text(
        json.dumps(runtime_info, indent=2),
        encoding="utf-8",
    )

    print("Model loaded successfully.")
    print("Loaded model metadata:", runtime_info)
    print("Expected features:", expected_features)

    return model, expected_features, response_time_medians


# --------------------------------------------------
# COLLECT METRICS AND PREDICT
# --------------------------------------------------

def collect_once(model, expected_features, response_time_medians):
    timestamp_dt = datetime.now().astimezone()
    timestamp = timestamp_dt.isoformat(timespec="milliseconds")

    metrics = {
        name: get_metric_values(query)
        for name, query in QUERIES.items()
    }

    rows = []

    for service in SERVICES:

        request_rate = metrics["request_rate"].get(service)

        if request_rate is None:
            print(
                f"WARNING: Skipping {service}; "
                "request_rate unavailable."
            )
            continue

        error_count = metrics["error_count"].get(service)
        response_time = metrics["response_time"].get(service)

        if error_count is None and request_rate == 0:
            error_count = 0.0

        # Preserve missing/zero response times for shared median imputation.
        if response_time is None or not math.isfinite(response_time) or response_time <= 0:
            response_time = 0.0

        missing = []

        if error_count is None:
            missing.append("error_count")

        for metric_name in (
            "thread_count",
            "cpu_usage",
        ):
            if service not in metrics[metric_name]:
                missing.append(metric_name)

        if missing:
            print(
                f"WARNING: Skipping {service}; "
                f"metrics unavailable: {', '.join(missing)}"
            )
            continue

        observation = {
            "timestamp": timestamp,
            "service": service,
            "request_rate": round(request_rate, 4),
            "error_count": round(error_count, 4),
            "thread_count": round(
                metrics["thread_count"][service], 2
            ),
            # Prometheus query already converts CPU usage to percent.
            "cpu_usage": round(
                metrics["cpu_usage"][service], 4
            ),
            "response_time": round(response_time, 6),
        }

        try:
            model_input = build_model_input(
                observation,
                expected_features,
                response_time_medians,
            )

            raw_prediction = int(
                model.predict(model_input)[0]
            )

            prediction = (
                "ANOMALY"
                if raw_prediction == -1
                else "NORMAL"
            )

            anomaly_score = float(
                model.decision_function(model_input)[0]
            )

        except Exception as error:
            print(
                f"ERROR: Prediction failed for "
                f"{service}: {error}"
            )
            continue

        fault_type_now, active_now = get_fault_status(service)
        fault_type, actual_label = classify_actual_state(service, fault_type_now, active_now, timestamp_dt)

        output_row = {
            **observation,
            "actual_label": actual_label,
            "fault_type": fault_type,
            "prediction": prediction,
            "anomaly_score": round(anomaly_score, 6),
        }

        rows.append(output_row)

        print(
            f"{timestamp} | {service} | "
            f"Actual: {actual_label or 'UNKNOWN'} | "
            f"Fault: {fault_type} | "
            f"Prediction: {prediction} | "
            f"Anomaly score: {output_row['anomaly_score']} | "
            f"Request rate: {observation['request_rate']} | "
            f"Errors: {observation['error_count']} | "
            f"CPU: {observation['cpu_usage']}% | "
            f"Response time: {observation['response_time']} sec"
        )

    if rows:
        dataframe = pd.DataFrame(
            rows,
            columns=OUTPUT_COLUMNS,
        )

        file_exists = (
            CSV_FILE.exists()
            and CSV_FILE.stat().st_size > 0
        )

        # Preserve the existing CSV workflow.
        dataframe.to_csv(
            CSV_FILE,
            mode="a" if file_exists else "w",
            header=not file_exists,
            index=False,
        )

        # Persist the same prediction observations in TiDB.
        insert_test_observations(rows)

        print(
            f"Saved {len(rows)} prediction rows to: "
            f"{CSV_FILE}"
        )
        print("Prediction rows also saved in TiDB.")

    else:
        print("No complete observation rows to save.")

    print("-" * 100)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Collect Prometheus metrics and predict "
            "microservice anomalies."
        )
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help=(
            "Run for this many seconds. "
            "0 means run until Ctrl+C."
        ),
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previous test dataset from CSV and TiDB.",
    )

    args = parser.parse_args()

    if args.duration < 0:
        parser.error(
            "--duration must be zero or a positive number."
        )

    if args.reset:
        CSV_FILE.unlink(missing_ok=True)
        clear_test_observations()
        print("Previous test dataset cleared from CSV and TiDB.")

    model, expected_features, response_time_medians = load_model()

    print("=" * 76)
    print("LIVE METRIC COLLECTION + ANOMALY PREDICTION")
    print("Prometheus:", PROMETHEUS_URL)
    print("Model:", MODEL_FILE)
    print("Output CSV:", CSV_FILE)
    print("Collection interval:", COLLECTION_INTERVAL, "seconds")
    print(
        "Duration:",
        f"{args.duration} seconds"
        if args.duration
        else "until Ctrl+C",
    )
    print("Prediction mapping: -1 = ANOMALY; +1 = NORMAL")
    print("Actual label: fault active = ANOMALY; inactive = NORMAL")
    print("=" * 76)

    start = time.monotonic()

    try:
        while True:
            if (
                args.duration
                and time.monotonic() - start >= args.duration
            ):
                break

            cycle_start = time.monotonic()

            try:
                collect_once(model, expected_features, response_time_medians)

            except (
                requests.RequestException,
                RuntimeError,
            ) as error:
                print("Collection error:", error)

            elapsed = time.monotonic() - cycle_start
            remaining = COLLECTION_INTERVAL - elapsed

            if args.duration:
                remaining = min(
                    remaining,
                    max(
                        0,
                        args.duration
                        - (time.monotonic() - start),
                    ),
                )

            if remaining > 0:
                time.sleep(remaining)

            if (
                args.duration
                and time.monotonic() - start >= args.duration
            ):
                break

    except KeyboardInterrupt:
        print("\nCollection stopped by user.")

    print("\nCollection finished.")

    if CSV_FILE.exists():
        try:
            dataframe = pd.read_csv(CSV_FILE)
            print("Dataset:", CSV_FILE)
            print("Total rows:", len(dataframe))

            if "actual_label" in dataframe.columns:
                print(
                    "Actual label counts:\n",
                    dataframe["actual_label"].value_counts(
                        dropna=False
                    ),
                )

            if "fault_type" in dataframe.columns:
                print(
                    "Fault type counts:\n",
                    dataframe["fault_type"].value_counts(
                        dropna=False
                    ),
                )

        except Exception as error:
            print("Could not read output CSV:", error)


if __name__ == "__main__":
    main()
