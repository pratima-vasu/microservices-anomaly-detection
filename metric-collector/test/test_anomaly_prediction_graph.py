import sys
import unittest
from pathlib import Path

import pandas as pd

DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))

from anomaly_prediction_graph import build_anomaly_prediction_figure


class AnomalyPredictionGraphTests(unittest.TestCase):
    def test_returns_none_for_empty_data(self):
        self.assertIsNone(build_anomaly_prediction_figure(pd.DataFrame()))

    def test_requires_prediction_columns(self):
        with self.assertRaises(ValueError):
            build_anomaly_prediction_figure(
                pd.DataFrame({"timestamp": [], "prediction": []})
            )

    def test_uses_normal_and_anomaly_values_from_prediction_column(self):
        data = pd.DataFrame({
            "timestamp": [
                "2026-11-24T10:00:05+00:00",
                "2026-11-24T10:00:10+00:00",
                "2026-11-24T10:00:15+00:00",
            ],
            "service": ["user-service", "product-service", "order-service"],
            "prediction": ["NORMAL", "ANOMALY", "NORMAL"],
            "anomaly_score": [0.1, -0.02, 0.04],
        })

        figure = build_anomaly_prediction_figure(data)
        observations = figure.data[0]

        self.assertEqual(list(observations.y), [0, 1, 0])
        self.assertEqual(
            list(observations.marker.color),
            ["#16A34A", "#DC2626", "#16A34A"],
        )
        self.assertEqual(
            list(observations.marker.symbol),
            ["circle", "square", "diamond"],
        )
        self.assertEqual(len(observations.x), 3)

    def test_sorts_by_timestamp_and_limits_to_latest_points(self):
        data = pd.DataFrame({
            "timestamp": [
                "2026-11-24T10:00:15+00:00",
                "2026-11-24T10:00:05+00:00",
                "2026-11-24T10:00:10+00:00",
            ],
            "service": ["user-service"] * 3,
            "prediction": ["ANOMALY", "NORMAL", "NORMAL"],
        })

        figure = build_anomaly_prediction_figure(data, max_points=2)
        observations = figure.data[0]

        self.assertEqual(len(observations.x), 2)
        self.assertLess(observations.x[0], observations.x[1])
        self.assertEqual(list(observations.y), [0, 1])

    def test_ignores_invalid_prediction_and_timestamp(self):
        data = pd.DataFrame({
            "timestamp": [
                "2026-11-24T10:00:05+00:00",
                "not-a-time",
                "2026-11-24T10:00:15+00:00",
            ],
            "service": ["user-service"] * 3,
            "prediction": ["NORMAL", "ANOMALY", "PENDING"],
        })

        figure = build_anomaly_prediction_figure(data)
        self.assertEqual(len(figure.data[0].x), 1)


if __name__ == "__main__":
    unittest.main()
