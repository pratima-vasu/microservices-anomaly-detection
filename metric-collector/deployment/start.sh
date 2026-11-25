#!/bin/sh
set -eu

: "${USER_SERVICE_HOST:?Set USER_SERVICE_HOST to the Render hostname without https://}"
: "${PRODUCT_SERVICE_HOST:?Set PRODUCT_SERVICE_HOST to the Render hostname without https://}"
: "${ORDER_SERVICE_HOST:?Set ORDER_SERVICE_HOST to the Render hostname without https://}"

envsubst '${USER_SERVICE_HOST} ${PRODUCT_SERVICE_HOST} ${ORDER_SERVICE_HOST}' \
  < /opt/deployment/prometheus.yml.template \
  > /tmp/prometheus.yml

export PROMETHEUS_CONFIG=/tmp/prometheus.yml
export PROMETHEUS_BIN=/prometheus/prometheus
export PROMETHEUS_URL=http://127.0.0.1:9090

echo "======================================"
echo "Testing TiDB database connection..."
echo "======================================"

python -c "
from storage import test_connection

result = test_connection()

print('TiDB connection successful!')
print('Connected database:', result['db_name'])
"

echo "======================================"
echo "Restoring latest application data..."
echo "======================================"

python -c "
from pathlib import Path

from storage import (
    restore_training_csv,
    restore_test_csv,
    restore_trained_model,
)

from data_preprocessing.feature_engineering import (
    prepare_training_dataset,
)

project_root = Path('/app')
training_dir = project_root / 'training'

raw_training_csv = training_dir / 'normal_dataset.csv'
prepared_training_csv = training_dir / 'normal_dataset_ml_ready.csv'

print('Restoring training dataset...')
restore_training_csv()

if raw_training_csv.exists() and raw_training_csv.stat().st_size > 0:
    print('Regenerating prepared training dataset...')
    prepare_training_dataset(
        str(raw_training_csv),
        str(prepared_training_csv)
    )
else:
    prepared_training_csv.unlink(missing_ok=True)
    print('No training observations found in TiDB.')

print('Restoring test dataset...')
restore_test_csv()

print('Restoring latest trained model...')
model_restored = restore_trained_model()

if model_restored:
    print('Latest trained model restored successfully.')
else:
    print('No trained model found in TiDB yet.')

print('Application data restoration completed.')
"

echo "======================================"
echo "Starting Streamlit dashboard..."
echo "======================================"

exec streamlit run /app/dashboard/Prediction.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-10000}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
