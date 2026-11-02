# Deployment preparation (Render + TiDB Cloud)

This package keeps the existing service boundaries, API endpoints, fault-injection behavior, metric queries, feature engineering, Isolation Forest prediction flow, and Streamlit pages. Deployment changes are limited to environment-based configuration, container/build files, and the Prometheus container template.

## What is included

- Three Spring Boot Dockerfiles (Java 21).
- One dashboard Dockerfile that packages Streamlit, a Python Prometheus lifecycle helper, and Prometheus in the same Render web service. Prometheus starts only when a user starts normal-data collection or live monitoring, and stops when collection stops.
- `render.yaml` Blueprint for four Render web services.
- Environment-based DB, inter-service, service-health, and fault-status URLs. Existing localhost defaults remain for local Eclipse use.
- The supplied model is retained unchanged. The deployment requirements pin scikit-learn to 1.9.1, matching the version recorded in the supplied pickle.

## Before deploying

1. Create a **private** GitHub repository and push this project root.
2. Create a TiDB Cloud Starter cluster in a region close to Render's region.
3. In TiDB, create these three schemas:
   - `CREATE DATABASE user_service_db;`
   - `CREATE DATABASE product_db;`
   - `CREATE DATABASE order_db;`
4. Copy the TiDB host, port (normally 4000), username, and password. Do not commit credentials.
5. In Render, create a Blueprint from the GitHub repository and select `render.yaml`.
6. For each Java service, supply `DB_HOST`, `DB_USERNAME`, and `DB_PASSWORD` when Render asks. The Blueprint sets DB port 4000, schema name, and TLS mode.
7. Confirm the service names/hostnames match the names in `render.yaml`. If Render assigns different hostnames, update `USER_SERVICE_URL`, `PRODUCT_SERVICE_URL`, `ORDER_SERVICE_URL`, and the three `*_SERVICE_HOST` values accordingly.

## Local compatibility

- The three `application.properties` files retain local defaults (`localhost`, ports 8082/8083/8084, root/root, SSL disabled).
- Dashboard and collector service URLs default to localhost when the environment variables are not set.
- Prometheus local config at `prometheus/prometheus.yml` remains unchanged. The deployed dashboard container uses `metric-collector/deployment/prometheus.yml.template` instead.

## Important free-tier limitations

- Render free web services can sleep after inactivity and have limited shared free instance hours. Four web services are not guaranteed to remain continuously available all month. Cold starts can make the first request slow or time out.
- Prometheus runs alongside Streamlit in the dashboard container to avoid a fifth Render service. It is available only while that web service is awake.
- Render free filesystems are ephemeral. Live CSVs written under `metric-collector/test` and training CSVs created at runtime can be lost when the service restarts, redeploys, or sleeps. The dashboard download button works for the current running instance, but it is not durable storage. Existing curated training/test CSVs are included in the GitHub/Docker image; newly collected rows are only temporary until exported.
- Persisting every live CSV row and training dataset in TiDB requires a separate storage-code change (database writes/reads); it is intentionally **not** included because this preparation preserves the current CSV-based application behavior.
- The Streamlit dashboard launches Prometheus (on Render only) and the selected collector as child processes when START is clicked. STOP terminates both. They stop if Render restarts/sleeps the service. Stop collection before leaving the demo to avoid keeping the three service instances awake through Prometheus scrapes.
- Render free instance RAM is limited. Java 21 memory is capped in the Dockerfiles, but build/startup may still need tuning if a service exceeds the free limit.
- Free-tier deployment is suitable for a best-effort demo, not guaranteed continuous production monitoring.

## First smoke tests after deployment

1. Open `https://anomaly-userservice.onrender.com/actuator/health`.
2. Open `https://anomaly-productservice.onrender.com/actuator/health`.
3. Open `https://anomaly-orderservice.onrender.com/actuator/health`.
4. Open the dashboard URL shown by Render.
5. Verify service status cards show UP. Open Prometheus locally inside the dashboard container only through collector queries; it is not publicly exposed.
6. Press START, wait for Prometheus readiness, generate requests against the services, inject a fault, and inspect the live prediction table.
7. Test the three inter-service flows (orders reading users/products, user order lookup).

## Not changed

No model retraining, feature changes, metric-query changes, controller/API changes, or anomaly-prediction logic changes were made.


## Build and runtime verification status

- Python source syntax and YAML structure are checked as part of packaging.
- The supplied model file is preserved byte-for-byte; its pickle was saved with scikit-learn 1.9.1, so the Python requirements pin that version.
- Java Maven builds must still run in Render's Docker build environment. A local Maven-wrapper build could not be completed in the preparation environment because Maven Central could not be reached.
- A successful Render deployment and real TiDB connection cannot be claimed until the user connects GitHub, creates the TiDB cluster, and authorizes the Render Blueprint.
