
import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor


# --------------------------------------------------
# PATHS AND COLUMN DEFINITIONS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

TRAINING_CSV = PROJECT_ROOT / "training" / "normal_dataset.csv"
TEST_CSV = PROJECT_ROOT / "test" / "test_dataset.csv"

TRAINING_COLUMNS = [
    "timestamp",
    "service",
    "request_rate",
    "error_count",
    "thread_count",
    "cpu_usage",
    "response_time",
]

TEST_COLUMNS = [
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
    "anomaly_score",
]


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "4000")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "anomaly_detection_db"),
        ssl={
            "ca": os.getenv("DB_SSL_CA", "/etc/secrets/ca.pem"),
            "check_hostname": True,
        },
        cursorclass=DictCursor,
        autocommit=False,
    )


def test_connection():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db_name")
            return cursor.fetchone()
    finally:
        connection.close()


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def _safe_value(value):
    """Convert pandas/numpy missing values to SQL NULL."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    return value


def _write_csv(rows, csv_path, columns):
    """Restore database rows into the existing CSV workflow."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        csv_path.unlink(missing_ok=True)
        return 0

    dataframe = pd.DataFrame(rows, columns=columns)
    dataframe.to_csv(csv_path, index=False)

    return len(dataframe)


# --------------------------------------------------
# TRAINING OBSERVATIONS
# --------------------------------------------------

def insert_training_observations(rows):
    if not rows:
        return 0

    query = """
        INSERT INTO training_observations (
            `timestamp`,
            service,
            request_rate,
            error_count,
            thread_count,
            cpu_usage,
            response_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = [
        (
            _safe_value(row.get("timestamp")),
            _safe_value(row.get("service")),
            _safe_value(row.get("request_rate")),
            _safe_value(row.get("error_count")),
            _safe_value(row.get("thread_count")),
            _safe_value(row.get("cpu_usage")),
            _safe_value(row.get("response_time")),
        )
        for row in rows
    ]

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.executemany(query, values)

        connection.commit()
        return len(values)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_training_observations():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    `timestamp`,
                    service,
                    request_rate,
                    error_count,
                    thread_count,
                    cpu_usage,
                    response_time
                FROM training_observations
                ORDER BY id ASC
            """)

            return cursor.fetchall()

    finally:
        connection.close()


def count_training_observations():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM training_observations
            """)

            return int(cursor.fetchone()["total"])

    finally:
        connection.close()


def clear_training_observations():
    """Delete training rows only. Never delete the trained model."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM training_observations")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def restore_training_csv():
    rows = get_training_observations()

    return _write_csv(
        rows,
        TRAINING_CSV,
        TRAINING_COLUMNS,
    )


# --------------------------------------------------
# TEST OBSERVATIONS AND PREDICTIONS
# --------------------------------------------------

def insert_test_observations(rows):
    if not rows:
        return 0

    query = """
        INSERT INTO test_observations (
            `timestamp`,
            service,
            request_rate,
            error_count,
            thread_count,
            cpu_usage,
            response_time,
            actual_label,
            fault_type,
            prediction,
            anomaly_score
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """

    values = [
        (
            _safe_value(row.get("timestamp")),
            _safe_value(row.get("service")),
            _safe_value(row.get("request_rate")),
            _safe_value(row.get("error_count")),
            _safe_value(row.get("thread_count")),
            _safe_value(row.get("cpu_usage")),
            _safe_value(row.get("response_time")),
            _safe_value(row.get("actual_label")),
            _safe_value(row.get("fault_type")),
            _safe_value(row.get("prediction")),
            _safe_value(row.get("anomaly_score")),
        )
        for row in rows
    ]

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.executemany(query, values)

        connection.commit()
        return len(values)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_test_observations():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    `timestamp`,
                    service,
                    request_rate,
                    error_count,
                    thread_count,
                    cpu_usage,
                    response_time,
                    actual_label,
                    fault_type,
                    prediction,
                    anomaly_score
                FROM test_observations
                ORDER BY id ASC
            """)

            return cursor.fetchall()

    finally:
        connection.close()


def clear_test_observations():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM test_observations")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def restore_test_csv():
    rows = get_test_observations()

    return _write_csv(
        rows,
        TEST_CSV,
        TEST_COLUMNS,
    )


# --------------------------------------------------
# LATEST TRAINED MODEL
# --------------------------------------------------

def save_trained_model(model_file):
    """
    Replace the current database model with the newly trained PKL.
    Only one current model is retained in the database.
    """

    model_path = Path(model_file)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model file not found: {model_path}"
        )

    model_data = model_path.read_bytes()

    if not model_data:
        raise ValueError("Trained model file is empty.")

    model_version = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d%H%M%S")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM trained_model")

            cursor.execute("""
                INSERT INTO trained_model (
                    model_data,
                    model_version
                )
                VALUES (%s, %s)
            """, (model_data, model_version))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def restore_trained_model():
    """Restore the latest trained model from TiDB."""

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT model_data
                FROM trained_model
                ORDER BY id DESC
                LIMIT 1
            """)

            result = cursor.fetchone()

    finally:
        connection.close()

    if not result or not result.get("model_data"):
        return False

    model_path = PROJECT_ROOT / "isolation_forest_model.pkl"
    temp_path = model_path.with_suffix(".restore.tmp")

    model_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(temp_path, "wb") as file:
            file.write(result["model_data"])

        os.replace(temp_path, model_path)

    finally:
        temp_path.unlink(missing_ok=True)

    return True
