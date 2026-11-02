# Real-Time Metric-Based Anomaly Detection in Microservices

The existing application logic and trained Isolation Forest model are retained. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for Render + TiDB deployment preparation and free-tier limitations.

Main folders: `userservice`, `productservice/productservice`, `orderservice`, `prometheus`, and `metric-collector`.

Prometheus is started on demand from the dashboard when collection begins and stopped when collection stops. Local Eclipse workflows continue to use the separately started local Prometheus instance.
