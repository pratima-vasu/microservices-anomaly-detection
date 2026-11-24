"""Live anomaly-prediction timeline for the Streamlit dashboard."""

import pandas as pd
import plotly.graph_objects as go


PREDICTION_COLORS = {
    "NORMAL": "#16A34A",
    "ANOMALY": "#DC2626",
}

SERVICE_SYMBOLS = {
    "user-service": "circle",
    "product-service": "square",
    "order-service": "diamond",
}


def build_anomaly_prediction_figure(dataframe, max_points=90):
    """Build a timeline from the latest stored predictions.

    The chart reads the existing prediction field and does not modify model
    predictions. Whatever final prediction is stored by the collector is
    what the dashboard displays.
    """
    if max_points < 1:
        raise ValueError("max_points must be at least 1")

    if dataframe is None or dataframe.empty:
        return None

    required_columns = {"timestamp", "service", "prediction"}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            "Prediction graph requires columns: "
            + ", ".join(sorted(missing_columns))
        )

    graph_data = dataframe.copy()
    graph_data["prediction"] = (
        graph_data["prediction"]
        .astype("string")
        .str.strip()
        .str.upper()
    )
    graph_data["_timestamp"] = pd.to_datetime(
        graph_data["timestamp"],
        errors="coerce",
        utc=True,
    )

    graph_data = graph_data.loc[
        graph_data["prediction"].isin(PREDICTION_COLORS)
        & graph_data["_timestamp"].notna()
    ].copy()

    if graph_data.empty:
        return None

    graph_data["service"] = (
        graph_data["service"]
        .astype("string")
        .fillna("unknown-service")
    )
    graph_data = (
        graph_data.sort_values("_timestamp", kind="stable")
        .tail(max_points)
        .reset_index(drop=True)
    )

    y_values = graph_data["prediction"].map(
        {"NORMAL": 0, "ANOMALY": 1}
    )
    marker_colors = graph_data["prediction"].map(
        PREDICTION_COLORS
    ).tolist()
    marker_symbols = (
        graph_data["service"]
        .map(SERVICE_SYMBOLS)
        .fillna("circle")
        .tolist()
    )

    if "anomaly_score" in graph_data.columns:
        scores = graph_data["anomaly_score"].where(
            graph_data["anomaly_score"].notna(), ""
        )
    else:
        scores = pd.Series([""] * len(graph_data), index=graph_data.index)

    custom_data = list(
        zip(
            graph_data["service"].astype(str),
            graph_data["prediction"].astype(str),
            scores.astype(str),
        )
    )

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=graph_data["_timestamp"],
            y=y_values,
            mode="markers",
            name="Observations",
            showlegend=False,
            marker={
                "size": 11,
                "color": marker_colors,
                "symbol": marker_symbols,
                "line": {"width": 0.7, "color": "#FFFFFF"},
                "opacity": 0.9,
            },
            customdata=custom_data,
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Time: %{x|%Y-%m-%d %H:%M:%S}<br>"
                "Service: %{customdata[0]}<br>"
                "Anomaly score: %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )

    for label, color in PREDICTION_COLORS.items():
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=label,
                marker={"size": 10, "color": color, "symbol": "circle"},
                hoverinfo="skip",
            )
        )

    figure.update_layout(
        title={
            "text": "Anomaly Prediction Graph",
            "x": 0,
            "xanchor": "left",
        },
        height=320,
        margin={"l": 12, "r": 12, "t": 52, "b": 12},
        template="plotly_white",
        hovermode="closest",
        legend={
            "title": {"text": "Prediction"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={
            "title": "Time",
            "showgrid": True,
            "gridcolor": "rgba(120, 120, 120, 0.16)",
        },
        yaxis={
            "title": "Prediction",
            "tickmode": "array",
            "tickvals": [0, 1],
            "ticktext": ["NORMAL", "ANOMALY"],
            "range": [-0.28, 1.28],
            "showgrid": True,
            "gridcolor": "rgba(120, 120, 120, 0.16)",
            "zeroline": False,
        },
    )

    return figure
