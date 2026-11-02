TEST FOLDER FILES — READ BEFORE RUNNING

Files in this package:
1. test_metric_collector.py — fetches Prometheus metrics for all 3 services, predicts with the existing Isolation Forest model, and appends rows to test_dataset.csv.
2. feature_engineering.py — converts each complete observation into the exact feature columns saved in the model.
3. validate_dataset.py — checks the output CSV.

IMPORTANT:
- These files are for the test folder only. Do NOT overwrite train_model.py, normal_dataset.csv, normal_dataset_ml_ready.csv, or isolation_forest_model.pkl.
- The collector expects the trained model at:
  ..\isolation_forest_model.pkl
  relative to this test folder, i.e. metric-collector\isolation_forest_model.pkl.
- Keep the existing project structure:
  metric-collector\
    isolation_forest_model.pkl
    test\
      test_metric_collector.py
      feature_engineering.py
      validate_dataset.py
- Install dependencies if needed:
  python -m pip install pandas requests joblib scikit-learn
- Open CMD and move to:
  cd /d C:\MTech_Anomaly_Detection\metric-collector\test
- First test for 30 seconds and clear only the test CSV:
  python test_metric_collector.py --duration 30 --reset
- If that runs successfully, continuous run:
  python test_metric_collector.py
  Stop with Ctrl+C.
- Validate the generated data in a second CMD window:
  python validate_dataset.py

CSV output:
test\test_dataset.csv

Prediction mapping:
IsolationForest predict() returns -1 for anomaly and +1 for normal.
The CSV contains:
- prediction: model output (NORMAL / ANOMALY)
- anomaly_score: decision_function score (lower values are more unusual)
- actual_label: fault API status, where 0 means API reported no fault, 1 means API reported fault, blank means status could not be read/understood.

IMPORTANT INTERPRETATION:
A fault being enabled does not guarantee every observation will be predicted as ANOMALY. Isolation Forest detects observations relative to learned patterns. Check the observed metrics and prediction output during the demo.
