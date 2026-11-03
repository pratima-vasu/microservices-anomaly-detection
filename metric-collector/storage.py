
import os
import pymysql
from pymysql.cursors import DictCursor


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "4000")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "anomaly_detection_db"),
        ssl={
            "ca": os.getenv("DB_SSL_CA", "/etc/secrets/ca.pem"),
            "check_hostname": True
        },
        cursorclass=DictCursor,
        autocommit=False
    )


def test_connection():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db_name")
            return cursor.fetchone()
    finally:
        connection.close()
