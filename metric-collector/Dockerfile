FROM python:3.13-slim

ARG PROMETHEUS_VERSION=3.5.0
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gettext-base tar \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /prometheus \
    && curl -fsSL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" -o /tmp/prometheus.tar.gz \
    && tar -xzf /tmp/prometheus.tar.gz -C /tmp \
    && cp "/tmp/prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus" /prometheus/prometheus \
    && chmod +x /prometheus/prometheus \
    && rm -rf /tmp/prometheus* \
    && apt-get purge -y --auto-remove curl tar

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY dashboard/ /app/dashboard/
COPY test/ /app/test/
COPY training/ /app/training/
COPY data_preprocessing/ /app/data_preprocessing/
COPY isolation_forest_model.pkl /app/isolation_forest_model.pkl
COPY isolation_forest_model.previous.pkl /app/isolation_forest_model.previous.pkl
COPY deployment/ /app/deployment/
COPY deployment/ /opt/deployment/
RUN chmod +x /opt/deployment/start.sh

EXPOSE 10000
CMD ["/opt/deployment/start.sh"]
