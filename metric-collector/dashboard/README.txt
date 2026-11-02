DASHBOARD V3

Place this dashboard folder directly under:
C:\MTech_Anomaly_Detection\metric-collector\

Expected:
metric-collector\
  dashboard\app.py
  dashboard\requirements.txt
  dashboard\pages\evaluation.py
  test\test_metric_collector.py
  test\test_dataset.csv

Run:
cd C:\MTech_Anomaly_Detection\metric-collector
pip install -r dashboard\requirements.txt
streamlit run dashboard\app.py

Changes:
- Green visual UP/DOWN service status instead of black status text.
- Live page shows latest 30 collected observations, so NORMAL and ANOMALY rows are both visible.
- No separate detected-anomalies table.
- Only Prediction text is highlighted: ANOMALY red, NORMAL green. Entire row is not coloured.
- START launches the existing test/test_metric_collector.py.
- STOP stops that process without deleting the CSV.
- START after STOP uses the existing collector's append behavior and continues in the same CSV.
- CLEAR stops the collector and deletes test_dataset.csv.
- Evaluation page reads the same CSV and shows Total Observations plus Accuracy, Precision, Recall and F1.
- CSV can be downloaded rather than displaying thousands of rows.


V4 UI FEEDBACK
--------------
START, STOP, CLEAR, ENABLE FAULT and DISABLE FAULT show a normal Streamlit
spinner/status message while the action is running. The spinner disappears
when the action finishes. No custom transparent overlay is added.
