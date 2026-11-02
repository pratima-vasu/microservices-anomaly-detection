# Model Training + Live Anomaly Detection

## Dashboard pages

- **Live Prediction** (`dashboard/app.py`): existing live inference, fault injection and prediction table.
- **Model Training** (`dashboard/pages/training.py`): collect normal workload, validate it, prepare the ML dataset and train/retrain Isolation Forest.
- **Model Evaluation** (`dashboard/pages/evaluation.py`): evaluate predictions from `test/test_dataset.csv`.

## Recommended run order

1. Start MySQL and all three Spring Boot services (User 8082, Product 8083, Order 8084).
2. Start Prometheus (9090) and confirm it can scrape the three services.
3. From `metric-collector`, install Python dependencies: `pip install -r dashboard/requirements.txt`.
4. Start the dashboard: `streamlit run dashboard/app.py`.
5. Open **Model Training**. Keep fault injection disabled while collecting normal workload. Run normal JMeter traffic across low/medium/peak patterns so the baseline represents normal operating conditions.
6. Stop collection, validate the dataset, prepare the training dataset, then train/retrain the model.
7. Open **Live Prediction**. If the collector was already running during retraining, stop and start it again so it reloads the newly trained model.
8. For evaluation, collect a separate test run with both normal and injected-fault observations, then open **Model Evaluation**.

## Dataset and model paths

- Raw normal data: `training/normal_dataset.csv`
- Prepared normal data: `training/normal_dataset_ml_ready.csv`
- Live test data: `test/test_dataset.csv`
- Canonical model used by live inference: `isolation_forest_model.pkl` (inside `metric-collector/`)
- Previous model backup after retraining: `isolation_forest_model.previous.pkl`
- Shared preprocessing: `data_preprocessing/`

Training and live inference use the same shared one-hot encoding and fixed feature order. The training page does not automatically retrain while live inference is running. The previous model is backed up before the new model is atomically installed.

## Configuration for deployment

Prometheus URL can be configured with `PROMETHEUS_URL`; default is `http://localhost:9090`. The Spring services and dashboard still use local service URLs in this version, so deployment networking/environment configuration remains a separate deployment step.

## Important notes

- Only collect data with faults disabled for the normal training baseline.
- A fault being active is the experiment's `actual_label`; it does not guarantee every sampled row is anomalous, and downstream effects may continue after the fault endpoint reports inactive.
- Keep the test dataset separate from training. Do not train on the evaluation test set.
- The model file is a Python/scikit-learn pickle. Use a consistent scikit-learn version between training and inference; retraining from the dashboard with the environment's installed version is recommended if an old model reports a version warning.


## Metric feature set (JVM memory removed)

The model uses five numeric metrics: `request_rate`, `error_count`, `thread_count`, `cpu_usage`, and `response_time`, plus three one-hot service columns. The `jvm_memory` metric is not collected, validated, preprocessed, displayed, or used for prediction. `thread_count` is retained as a separate feature.

The active normal training CSVs have been migrated by dropping only the `jvm_memory` column; all 300 existing normal observations are retained. The active `test/test_dataset.csv` contains the new schema header but no old prediction rows, because those predictions were produced by the previous nine-feature model and should not be mixed with results from the new eight-feature model. Collect a fresh test run. The existing JVM-memory fault-injection implementation in the Order Service is retained in source, but JVM_MEMORY is no longer offered in the dashboard fault selector or treated as a supported model-evaluation fault type.
