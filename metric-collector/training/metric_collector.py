
import requests
import pandas as pd
import time
import math
import os
import sys

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage import insert_training_observations

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://localhost:9090"
).rstrip("/")

CSV_FILE = HERE / "normal_dataset.csv"

COLLECTION_INTERVAL = int(
    os.getenv("COLLECTION_INTERVAL", "5")
)

IST = ZoneInfo("Asia/Kolkata")


# --------------------------------------------------
# PROMETHEUS FETCHING
# --------------------------------------------------

def query_prometheus(query):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=10
    )

    response.raise_for_status()

    return response.json()["data"]["result"]


def get_metric_values(query):
    results = query_prometheus(query)

    values = {}

    for result in results:

        metric = result["metric"]

        service = metric.get("job")
        if service in [
            "user-service",
            "product-service",
            "order-service"
        ]:
            # Queries are aggregated by job, so each service has one value.
            values[service] = {
                "value": float(result["value"][1])
            }

    return values


# --------------------------------------------------
# REQUEST RATE
# --------------------------------------------------

request_rate_query = """
sum by (job) (
    rate(http_server_requests_seconds_count{
        uri!~"/actuator.*"
    }[1m])
)
or on (job) (
    0 * max by (job) (up)
)
"""


# --------------------------------------------------
# ERROR COUNT
# --------------------------------------------------

error_count_query = """
sum by (job) (
    increase(http_server_requests_seconds_count{
        uri!~"/actuator.*",
        status=~"4..|5.."
    }[1m])
)
or on (job) (
    0 * max by (job) (up)
)
"""


# --------------------------------------------------
# LIVE THREADS
# --------------------------------------------------

threads_query = """
sum by (job) (
    jvm_threads_live_threads
)
"""


# --------------------------------------------------
# CPU USAGE
# --------------------------------------------------

cpu_query = """
avg by (job) (
    process_cpu_usage
) * 100
"""


# --------------------------------------------------
# AVERAGE RESPONSE TIME
# --------------------------------------------------

response_time_query = """
sum by (job) (
    rate(http_server_requests_seconds_sum{
        uri!~"/actuator.*"
    }[1m])
)
/
sum by (job) (
    rate(http_server_requests_seconds_count{
        uri!~"/actuator.*"
    }[1m])
)
"""


# --------------------------------------------------
# CSV APPENDING
# --------------------------------------------------

def save_to_csv(rows):

    dataframe = pd.DataFrame(rows)

    file_exists = (
        CSV_FILE.exists()
        and CSV_FILE.stat().st_size > 0
    )

    dataframe.to_csv(
        CSV_FILE,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False
    )


# --------------------------------------------------
# START COLLECTOR
# --------------------------------------------------

print("Starting metric collector...")
print("Timezone: Asia/Kolkata (IST)")
print(
    f"Collecting data every {COLLECTION_INTERVAL} seconds..."
)
print("Saving observations to CSV and TiDB.")
print("Press CTRL+C to stop.\n")


while True:

    timestamp = datetime.now(IST).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]

    try:

        request_rates = get_metric_values(
            request_rate_query
        )

        error_counts = get_metric_values(
            error_count_query
        )

        threads = get_metric_values(
            threads_query
        )

        cpu_usage = get_metric_values(
            cpu_query
        )

        response_times = get_metric_values(
            response_time_query
        )

        rows = []

        for service in [
            "user-service",
            "product-service",
            "order-service"
        ]:

            # Do not silently replace missing JVM/CPU scrapes with zero.
            if service not in threads or service not in cpu_usage:
                print(
                    f"Skipping {service}; JVM thread or CPU metric unavailable."
                )
                continue

            request_rate = request_rates.get(service, {}).get("value", 0.0)
            error_count = error_counts.get(service, {}).get("value", 0.0)
            thread_count = threads[service]["value"]
            cpu_value = cpu_usage[service]["value"]
            response_result = response_times.get(service)

            if response_result is None:
                if request_rate == 0:
                    response_time = 0.0
                else:
                    print(
                        f"Skipping {service}; response-time metric unavailable "
                        "while requests are active."
                    )
                    continue
            else:
                response_time = response_result["value"]

            metric_values = [
                request_rate, error_count, thread_count,
                cpu_value, response_time
            ]
            if not all(math.isfinite(value) for value in metric_values):
                print(f"Skipping {service}; one or more metrics are not finite.")
                continue

            row = {
                "timestamp": timestamp,
                "service": service,
                "request_rate": round(request_rate, 4),
                "error_count": round(error_count, 4),
                "thread_count": round(thread_count, 2),
                "cpu_usage": round(cpu_value, 4),
                "response_time": round(response_time, 6)
            }

            rows.append(row)

            print(
                timestamp,
                "|",
                service,
                "| Requests:",
                round(request_rate, 2),
                "| Errors:",
                round(error_count, 2),
                "| Threads:",
                round(thread_count, 2),
                "| CPU:",
                round(cpu_value, 2),
                "%",
                "| Response:",
                round(response_time, 4),
                "sec"
            )

        # --------------------------------------------------
        # SAVE OBSERVATIONS TO TIDB
        # --------------------------------------------------

        # TiDB is the persistent source of truth.
        # If the database write fails, do not append
        # these rows to the local CSV.

        saved_count = insert_training_observations(rows)

        print(
            f"Saved {saved_count} observations to TiDB."
        )

        # --------------------------------------------------
        # SAVE DATA TO CSV
        # --------------------------------------------------

        save_to_csv(rows)

        print(
            f"Saved {len(rows)} observations to CSV: {CSV_FILE}"
        )

        print("-" * 100)

    except Exception as e:

        print(
            "Error while collecting or saving metrics:",
            e
        )

    time.sleep(COLLECTION_INTERVAL)
