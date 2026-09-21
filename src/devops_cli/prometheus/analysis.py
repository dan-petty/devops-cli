"""Client-side anomaly detection and trend forecasting over metric series.

Answers "is this metric behaving unusually, and where is it heading" locally, without
server-side subqueries, so an operator can reason about a series already fetched instead
of issuing another round of increasingly baroque PromQL.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from devops_cli.config.defaults import (
    DEFAULT_ANOMALY_MIN_SAMPLES,
    DEFAULT_ANOMALY_Z_THRESHOLD,
    DEFAULT_EWMA_ALPHA,
    DEFAULT_FORECAST_HORIZON_SAMPLES,
)
from devops_cli.models.prometheus import (
    MetricAnomaly,
    SeriesAnalysis,
    TrendDirection,
)


def _z_scores(values: Sequence[float]) -> list[float]:
    """Compute the z-score of each sample against the series mean.

    A zero-variance series yields all zeros rather than dividing by zero: a perfectly
    flat metric has no outliers by definition.
    """
    mean = statistics.fmean(values)
    try:
        deviation = statistics.stdev(values)
    except statistics.StatisticsError:
        return [0.0] * len(values)
    if deviation == 0.0:
        return [0.0] * len(values)
    return [(value - mean) / deviation for value in values]


def detect_anomalies(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    threshold: float = DEFAULT_ANOMALY_Z_THRESHOLD,
    min_samples: int = DEFAULT_ANOMALY_MIN_SAMPLES,
) -> list[MetricAnomaly]:
    """Flag samples deviating from the series mean by more than `threshold` sigma.

    Series shorter than `min_samples` return nothing: a handful of points cannot
    establish a baseline, and reporting an "anomaly" against two samples would be noise
    dressed as a signal.
    """
    if len(values) < min_samples:
        return []

    scores = _z_scores(values)
    stamps = list(timestamps or range(len(values)))
    return [
        MetricAnomaly(
            index=index,
            timestamp=float(stamps[index]) if index < len(stamps) else float(index),
            value=float(values[index]),
            z_score=round(score, 4),
            direction="above" if score > 0 else "below",
        )
        for index, score in enumerate(scores)
        if abs(score) >= threshold
    ]


def ewma(values: Sequence[float], alpha: float = DEFAULT_EWMA_ALPHA) -> list[float]:
    """Compute the exponentially weighted moving average of a series.

    Recent samples dominate, so the smoothed line tracks a level shift quickly while
    still suppressing single-sample noise.
    """
    if not values:
        return []
    smoothed = [float(values[0])]
    for value in values[1:]:
        smoothed.append(alpha * float(value) + (1.0 - alpha) * smoothed[-1])
    return smoothed


def _linear_slope(values: Sequence[float]) -> float:
    """Fit the least-squares slope of a series against its sample index."""
    count = len(values)
    if count < 2:
        return 0.0
    mean_x = (count - 1) / 2.0
    mean_y = statistics.fmean(values)
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
    denominator = sum((index - mean_x) ** 2 for index in range(count))
    return numerator / denominator if denominator else 0.0


def _classify_trend(slope: float, values: Sequence[float]) -> TrendDirection:
    """Classify a slope as rising, falling, or flat relative to the series scale.

    The threshold is scaled by the series magnitude so a metric measured in bytes is not
    judged by the same absolute slope as one measured as a ratio.
    """
    magnitude = max(abs(statistics.fmean(values)), 1e-9)
    relative = slope / magnitude
    if relative > 0.01:
        return TrendDirection.RISING
    if relative < -0.01:
        return TrendDirection.FALLING
    return TrendDirection.FLAT


def forecast(
    values: Sequence[float],
    horizon: int = DEFAULT_FORECAST_HORIZON_SAMPLES,
    alpha: float = DEFAULT_EWMA_ALPHA,
) -> list[float]:
    """Project the series forward by extending its smoothed level along its slope."""
    if not values or horizon <= 0:
        return []
    smoothed = ewma(values, alpha=alpha)
    slope = _linear_slope(values)
    level = smoothed[-1]
    return [round(level + slope * step, 6) for step in range(1, horizon + 1)]


def analyze_series(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    threshold: float = DEFAULT_ANOMALY_Z_THRESHOLD,
    horizon: int = DEFAULT_FORECAST_HORIZON_SAMPLES,
    alpha: float = DEFAULT_EWMA_ALPHA,
) -> SeriesAnalysis:
    """Summarise a metric series: distribution, anomalies, trend, and projection."""
    numeric = [float(value) for value in values]
    if not numeric:
        return SeriesAnalysis(sample_count=0)

    anomalies = detect_anomalies(numeric, timestamps, threshold=threshold)
    slope = _linear_slope(numeric)
    return SeriesAnalysis(
        sample_count=len(numeric),
        minimum=min(numeric),
        maximum=max(numeric),
        mean=round(statistics.fmean(numeric), 6),
        median=round(statistics.median(numeric), 6),
        stdev=round(statistics.stdev(numeric), 6) if len(numeric) > 1 else 0.0,
        latest=numeric[-1],
        slope=round(slope, 6),
        trend=_classify_trend(slope, numeric),
        anomalies=anomalies,
        smoothed=[round(value, 6) for value in ewma(numeric, alpha=alpha)],
        forecast=forecast(numeric, horizon=horizon, alpha=alpha),
    )


def extract_series_values(result: dict[str, object]) -> tuple[list[float], list[float]]:
    """Extract timestamps and values from a Prometheus range-query result payload.

    Samples that cannot be parsed as numbers — Prometheus encodes them as strings, and
    `NaN` is legal — are skipped rather than coerced, so a gap never masquerades as zero.
    """
    raw_values = result.get("values")
    if not isinstance(raw_values, list):
        return [], []

    timestamps: list[float] = []
    values: list[float] = []
    for sample in raw_values:
        if not isinstance(sample, (list, tuple)) or len(sample) < 2:
            continue
        try:
            stamp = float(sample[0])
            value = float(sample[1])
        except TypeError, ValueError:
            continue
        if value != value:  # NaN: a reported gap, not a measurement.
            continue
        timestamps.append(stamp)
        values.append(value)
    return timestamps, values


__all__ = [
    "analyze_series",
    "detect_anomalies",
    "ewma",
    "extract_series_values",
    "forecast",
]
