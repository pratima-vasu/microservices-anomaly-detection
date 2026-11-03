
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

echo "Starting Streamlit dashboard..."

exec streamlit run /app/dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-10000}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
