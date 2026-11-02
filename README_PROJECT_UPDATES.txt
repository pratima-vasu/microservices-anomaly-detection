MTECH ANOMALY DETECTION - UPDATED PROJECT

Main change: a separate Streamlit Model Training page has been added without removing the existing Live Prediction or Model Evaluation pages.

Open metric-collector/README_TRAINING_DASHBOARD.md for the exact run order and training instructions.

The project source package excludes Eclipse workspace metadata, Python cache files, Maven target/build output, and bundled JMeter/Prometheus executable distributions to keep the ZIP manageable. The JMeter test plans and Prometheus configuration are included. Use your existing JMeter/Prometheus installations or install those tools separately.

JVM memory metric removal: the active training and live-prediction pipeline now uses five numeric metrics (request_rate, error_count, thread_count, cpu_usage, response_time) plus three service indicator columns. Existing 300 normal observations were retained after dropping jvm_memory. The model was retrained with eight features. The old test predictions were reset because they were generated with the previous feature set; collect a fresh evaluation run. thread_count remains enabled.
