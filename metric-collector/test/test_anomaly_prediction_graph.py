import sys
import unittest
from pathlib import Path

import pandas as pd

DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))

from anomaly_prediction_graph import build_anomaly_prediction_figure


def normal_training_data():
    rows = []
    for service_index, service in enumerate(
        ["user-service", "product-service", "order-service"]
    ):
        for index in range(8):
            rows.append({
                "service": service,
                "request_rate": 1.0 + index * 0.2 + service_index * 0.5,
                "error_count": 0.0,
                "thread_count": 20 + index + service_index * 2,
                "cpu_usage": 8.0 + index * 1.5 + service_index,
                "response_time": 0.2 + index * 0.04 + service_index * 0.1,
            })
    return pd.DataFrame(rows)


class AnomalyPredictionGraphTests(unittest.TestCase):
    def test_returns_none_without_normal_training_reference(self):
        test_data = pd.DataFrame({
            "timestamp": ["2026-11-24T10:00:05+00:00"],
            "service": ["user-service"],
            "request_rate": [2.0],
            "error_count": [0.0],
            "thread_count": [25],
            "cpu_usage": [15.0],
            "response_time": [0.5],
            "prediction": ["NORMAL"],
        })
        self.assertIsNone(
            build_anomaly_prediction_figure(pd.DataFrame(), test_data)
        )

    def test_plots_normal_training_cluster_and_test_predictions(self):
        test_data = pd.DataFrame({
            "timestamp": [
                "2026-11-24T10:00:05+00:00",
                "2026-11-24T10:00:10+00:00",
                "2026-11-24T10:00:15+00:00",
            ],
            "service": ["user-service", "product-service", "order-service"],
            "request_rate": [2.0, 3.0, 5.0],
            "error_count": [0.0, 0.0, 15.0],
            "thread_count": [25, 27, 35],
            "cpu_usage": [15.0, 18.0, 75.0],
            "response_time": [0.5, 0.6, 4.5],
            "prediction": ["NORMAL", "NORMAL", "ANOMALY"],
            "anomaly_score": [0.1, 0.05, -0.08],
        })

        figure = build_anomaly_prediction_figure(
            normal_training_data(),
            test_data,
        )

        self.assertIsNotNone(figure)
        trace_names = [trace.name for trace in figure.data]
        self.assertEqual(
            trace_names,
            ["Normal training data", "Test NORMAL", "Test ANOMALY"],
        )
        self.assertEqual(len(figure.data[0].x), 24)
        self.assertEqual(len(figure.data[1].x), 2)
        self.assertEqual(len(figure.data[2].x), 1)
        self.assertEqual(
            list(figure.data[2].marker.color),
            ["#DC2626"],
        )
        self.assertIn("Principal Component 1", figure.layout.xaxis.title.text)
        self.assertIn("Principal Component 2", figure.layout.yaxis.title.text)

    def test_only_latest_test_points_are_plotted(self):
        test_data = pd.DataFrame({
            "timestamp": [
                "2026-11-24T10:00:05+00:00",
                "2026-11-24T10:00:10+00:00",
                "2026-11-24T10:00:15+00:00",
            ],
            "service": ["user-service"] * 3,
            "request_rate": [2.0, 2.2, 2.4],
            "error_count": [0.0, 0.0, 0.0],
            "thread_count": [25, 25, 25],
            "cpu_usage": [15.0, 16.0, 17.0],
            "response_time": [0.5, 0.6, 0.7],
            "prediction": ["NORMAL", "ANOMALY", "NORMAL"],
        })

        figure = build_anomaly_prediction_figure(
            normal_training_data(),
            test_data,
            max_points=2,
        )
        plotted_test_points = sum(len(trace.x) for trace in figure.data[1:])
        self.assertEqual(plotted_test_points, 2)

    def test_raises_for_invalid_max_points(self):
        with self.assertRaises(ValueError):
            build_anomaly_prediction_figure(
                normal_training_data(),
                pd.DataFrame(),
                max_points=0,
            )


if __name__ == "__main__":
    unittest.main()
