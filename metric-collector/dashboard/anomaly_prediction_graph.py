"""2D feature-space scatter plot for normal observations and anomalies."""

import pandas as pd
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


METRIC_FEATURES = [
    "request_rate",
    "error_count",
    "thread_count",
    "cpu_usage",
    "response_time",
]

SERVICE_SYMBOLS = {
    "user-service": "circle",
    "product-service": "square",
    "order-service": "diamond",
}

MODEL_FEATURES = METRIC_FEATURES + [
    "service_order-service",
    "service_product-service",
    "service_user-service",
]

NORMAL_COLOR = "#16A34A"
ANOMALY_COLOR = "#DC2626"


def _prepare_metrics(dataframe, response_time_medians=None):
    if dataframe is None or dataframe.empty:
        return pd.DataFrame()

    required = {"service", *METRIC_FEATURES}
    if not required.issubset(dataframe.columns):
        return pd.DataFrame()

    frame = dataframe.copy()
    frame["service"] = frame["service"].astype("string").str.strip()

    for column in METRIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Match the project's preprocessing behaviour for idle/missing response time.
    if response_time_medians:
        for service, median_value in response_time_medians.items():
            mask = (
                frame["service"].eq(service)
                & (frame["response_time"].isna() | frame["response_time"].le(0))
            )
            frame.loc[mask, "response_time"] = float(median_value)

    return frame.dropna(subset=METRIC_FEATURES).loc[
        (frame[METRIC_FEATURES] >= 0).all(axis=1)
    ].copy()


def _model_feature_matrix(frame):
    """Create the same five numeric and three service one-hot features."""
    encoded = frame[METRIC_FEATURES].copy()
    encoded["service_order-service"] = frame["service"].eq("order-service").astype(int)
    encoded["service_product-service"] = frame["service"].eq("product-service").astype(int)
    encoded["service_user-service"] = frame["service"].eq("user-service").astype(int)
    return encoded[MODEL_FEATURES]


def build_anomaly_prediction_figure(
    training_dataframe,
    testing_dataframe,
    max_points=90,
):
    """Project five metrics into 2D PCA space.

    PCA and scaling are fitted ONLY on normal training observations. Test
    observations are projected into that fixed reference space. Training
    normal points form the green reference cloud; test predictions are green
    for NORMAL and red for ANOMALY.
    """
    if max_points < 1:
        raise ValueError("max_points must be at least 1")

    if training_dataframe is None or training_dataframe.empty:
        return None

    training = training_dataframe.copy()
    testing = testing_dataframe.copy() if testing_dataframe is not None else pd.DataFrame()

    # Derive the same per-service response-time medians used for training.
    raw_training = training.copy()
    for column in METRIC_FEATURES:
        if column in raw_training.columns:
            raw_training[column] = pd.to_numeric(raw_training[column], errors="coerce")

    active = raw_training.loc[
        raw_training.get("request_rate", pd.Series(index=raw_training.index, dtype=float)).gt(0)
        & raw_training.get("response_time", pd.Series(index=raw_training.index, dtype=float)).gt(0)
    ]
    fallback = (
        float(active["response_time"].median())
        if not active.empty else 0.0
    )

    response_time_medians = {}
    if {"service", "response_time", "request_rate"}.issubset(raw_training.columns):
        for service in SERVICE_SYMBOLS:
            service_active = active.loc[active["service"].astype(str).str.strip().eq(service), "response_time"]
            response_time_medians[service] = (
                float(service_active.median())
                if not service_active.empty else fallback
            )

    train_clean = _prepare_metrics(training, response_time_medians)
    test_clean = _prepare_metrics(testing, response_time_medians)

    if len(train_clean) < 2:
        return None

    scaler = StandardScaler()
    training_features = _model_feature_matrix(train_clean)
    training_scaled = scaler.fit_transform(training_features)
    pca = PCA(n_components=2)
    training_coordinates = pca.fit_transform(training_scaled)

    figure = go.Figure()

    train_symbols = (
        train_clean["service"].astype(str)
        .map(SERVICE_SYMBOLS).fillna("circle").tolist()
    )
    train_custom = [
        [str(service), "Normal training reference"]
        for service in train_clean["service"]
    ]

    figure.add_trace(
        go.Scatter(
            x=training_coordinates[:, 0],
            y=training_coordinates[:, 1],
            mode="markers",
            name="Normal training data",
            marker={
                "size": 6,
                "color": NORMAL_COLOR,
                "opacity": 0.28,
                "symbol": train_symbols,
            },
            customdata=train_custom,
            hovertemplate=(
                "<b>Normal training reference</b><br>"
                "Service: %{customdata[0]}<extra></extra>"
            ),
        )
    )

    if not test_clean.empty and "prediction" in test_clean.columns:
        test_clean["prediction"] = (
            test_clean["prediction"].astype("string").str.strip().str.upper()
        )
        test_clean["_timestamp"] = pd.to_datetime(
            test_clean.get("timestamp"),
            errors="coerce",
            utc=True,
        )
        test_clean = test_clean.loc[
            test_clean["prediction"].isin(["NORMAL", "ANOMALY"])
        ].copy()

        if "timestamp" in test_clean.columns:
            test_clean = test_clean.sort_values(
                "_timestamp", kind="stable", na_position="last"
            )
        test_clean = test_clean.tail(max_points).reset_index(drop=True)

        if not test_clean.empty:
            test_features = _model_feature_matrix(test_clean)
            test_coordinates = pca.transform(
                scaler.transform(test_features)
            )

            for label, color in (
                ("NORMAL", NORMAL_COLOR),
                ("ANOMALY", ANOMALY_COLOR),
            ):
                mask = test_clean["prediction"].eq(label)
                if not mask.any():
                    continue

                selected = test_clean.loc[mask].copy()
                selected_coordinates = test_coordinates[mask.to_numpy()]
                selected_symbols = (
                    selected["service"].astype(str)
                    .map(SERVICE_SYMBOLS).fillna("circle").tolist()
                )
                selected_times = (
                    selected["_timestamp"].astype("string").fillna("Unknown")
                    if "_timestamp" in selected.columns
                    else pd.Series(["Unknown"] * len(selected), index=selected.index)
                )
                selected_scores = (
                    selected["anomaly_score"].astype("string").fillna("Unavailable")
                    if "anomaly_score" in selected.columns
                    else pd.Series(["Unavailable"] * len(selected), index=selected.index)
                )
                custom = list(zip(
                    selected["service"].astype(str),
                    selected_times.astype(str),
                    selected_scores.astype(str),
                ))

                figure.add_trace(
                    go.Scatter(
                        x=selected_coordinates[:, 0],
                        y=selected_coordinates[:, 1],
                        mode="markers",
                        name=f"Test {label}",
                        marker={
                            "size": 11,
                            "color": color,
                            "opacity": 0.95,
                            "symbol": selected_symbols,
                            "line": {"width": 0.8, "color": "#FFFFFF"},
                        },
                        customdata=custom,
                        hovertemplate=(
                            f"<b>{label}</b><br>"
                            "Service: %{customdata[0]}<br>"
                            "Time: %{customdata[1]}<br>"
                            "Anomaly score: %{customdata[2]}"
                            "<extra></extra>"
                        ),
                    )
                )

    explained = float(
        sum(
            value for value in pca.explained_variance_ratio_
            if pd.notna(value)
        ) * 100
    )
    figure.update_layout(
        title={
            "text": "Normal Cluster vs Anomaly Outliers",
            "x": 0,
            "xanchor": "left",
        },
        height=430,
        margin={"l": 12, "r": 12, "t": 52, "b": 12},
        template="plotly_white",
        hovermode="closest",
        legend={
            "title": {"text": "Observations"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={
            "title": "Principal Component 1",
            "showgrid": True,
            "gridcolor": "rgba(120, 120, 120, 0.16)",
            "zeroline": False,
        },
        yaxis={
            "title": "Principal Component 2",
            "showgrid": True,
            "gridcolor": "rgba(120, 120, 120, 0.16)",
            "zeroline": False,
        },
    )
    figure.add_annotation(
        text=f"2D PCA projection of 5 metrics + service identity · {explained:.1f}% variance shown",
        xref="paper",
        yref="paper",
        x=0,
        y=-0.18,
        showarrow=False,
        font={"size": 10, "color": "#777777"},
    )

    return figure
