import requests
import pandas as pd
import time
import math
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
CSV_FILE = HERE / "normal_dataset.csv"
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "5"))


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
        instance = metric.get("instance")

        if service in ["user-service", "product-service", "order-service"]:

            values[service] = {
                "instance": instance,
                "value": float(result["value"][1])
            }

    return values


# --------------------------------------------------
# Request Rate
# Average requests per second over the last 1 minute
# --------------------------------------------------

request_rate_query = """
sum by (job, instance) (
    rate(
        http_server_requests_seconds_count{
            uri!~"/actuator.*"
        }[1m]
    )
)
"""

# --------------------------------------------------
# Error Count
# Estimated 4xx/5xx errors over the last 1 minute
# --------------------------------------------------

error_count_query = """
sum by (job, instance) (
    increase(
        http_server_requests_seconds_count{
            uri!~"/actuator.*",
            status=~"4..|5.."
        }[1m]
    )
)
"""

# --------------------------------------------------
# Live Threads
# --------------------------------------------------

threads_query = """
jvm_threads_live_threads
"""


# --------------------------------------------------
# CPU Usage
# --------------------------------------------------

cpu_query = """
process_cpu_usage * 100
"""


# --------------------------------------------------
# Average Response Time
# --------------------------------------------------

response_time_query = """
sum by (job, instance) (
    rate(
        http_server_requests_seconds_sum{
            uri!~"/actuator.*"
        }[1m]
    )
)
/
sum by (job, instance) (
    rate(
        http_server_requests_seconds_count{
            uri!~"/actuator.*"
        }[1m]
    )
)
"""


# --------------------------------------------------
# Start Collector
# --------------------------------------------------

print("Starting metric collector...")
print("Collecting data every 5 seconds...")
print("Press CTRL+C to stop.\n")


while True:

    timestamp = datetime.now().strftime(
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

            # Request count in last 5 seconds
            request_rate = (
                request_rates
                .get(service, {})
                .get("value", 0)
            )

            # Error count in last 5 seconds
            error_count = (
                error_counts
                .get(service, {})
                .get("value", 0)
            )

            # Live threads
            thread_count = (
                threads
                .get(service, {})
                .get("value", 0)
            )

            # CPU percentage
            cpu_value = (
                cpu_usage
                .get(service, {})
                .get("value", 0)
            )

            # Average response time in seconds
            response_time = (
                response_times
                .get(service, {})
                .get("value", 0)
            )
            # If no requests occurred, response time is not applicable.
            # Store it as 0 for the dataset.
            if not math.isfinite(response_time):
                response_time = 0

            row = {
                "timestamp": timestamp,
                "service": service,
                "request_rate": round(
                    request_rate, 2
                ),
                "error_count": round(
                    error_count, 2
                ),
                "thread_count": round(
                    thread_count, 2
                ),
                "cpu_usage": round(
                    cpu_value, 2
                ),
                "response_time": round(
                    response_time, 4
                )
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

        df = pd.DataFrame(rows)

        # --------------------------------------------------
        # Save data to CSV
        # --------------------------------------------------

        try:

            pd.read_csv(CSV_FILE)

            # Existing file -> append without header

            df.to_csv(
                CSV_FILE,
                mode="a",
                header=False,
                index=False
            )

        except FileNotFoundError:

            # File does not exist -> create with header

            df.to_csv(
                CSV_FILE,
                mode="w",
                header=True,
                index=False
            )

        print("-" * 100)

    except Exception as e:

        print(
            "Error while collecting metrics:",
            e
        )

    time.sleep(COLLECTION_INTERVAL)
