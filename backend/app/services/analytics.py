from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

PERCENTILES = (10, 25, 50, 75, 90)
BIN_WIDTH_MW = 250.0
LEAD_BINS = [16, 20, 24, 28, 32, 36, 40, 44, 48]
LEAD_LABELS = [
    "16–20 h",
    "20–24 h",
    "24–28 h",
    "28–32 h",
    "32–36 h",
    "36–40 h",
    "40–44 h",
    "44–48 h",
]

DEFINITIONS = {
    "mae": "Mean of |forecast - actual| over matched half-hour periods, in MW.",
    "rmse": "Square root of the mean squared error over matched periods, in MW.",
    "bias": "Mean of (forecast - actual), in MW. Positive means over-forecasting.",
    "bias_pct": "Bias divided by mean actual generation, as a percentage.",
    "mape": (
        "Mean of |error / actual| * 100. Periods with actual = 0 are excluded; "
        "the excluded count is shown."
    ),
    "smape": (
        "Symmetric MAPE: mean of 2|forecast - actual| / (|forecast| + |actual|) * 100. "
        "Defined as 0 when both values are 0."
    ),
    "wape": (
        "Weighted absolute percentage error: sum |error| / sum actual * 100. "
        "Scale-independent and robust to individual zero actuals."
    ),
    "coverage": (
        "Matched periods divided by the expected number of half-hour periods in the selected range."
    ),
    "lead_time": (
        "Delivery start minus the selected forecast publication time, in hours. "
        "With one cutoff per day, lead time is correlated with time of day."
    ),
}


def matched_only(periods: pd.DataFrame) -> pd.DataFrame:
    return periods.dropna(subset=["forecast_mw", "actual_mw"]).copy()


def compute_kpis(periods: pd.DataFrame) -> dict[str, Any]:
    matched = matched_only(periods)
    n = len(matched)
    if n == 0:
        return {
            "mae_mw": None,
            "rmse_mw": None,
            "bias_mw": None,
            "bias_pct_of_mean_actual": None,
            "mape_pct": None,
            "mape_n": 0,
            "mape_excluded_zero_actual": 0,
            "smape_pct": None,
            "wape_pct": None,
            "valid_matched_periods": 0,
            "overforecast_periods": 0,
            "underforecast_periods": 0,
            "zero_error_periods": 0,
            "overforecast_pct": None,
            "mean_forecast_mw": None,
            "mean_actual_mw": None,
        }

    errors = matched["error_mw"].astype(float)
    actual = matched["actual_mw"].astype(float)
    forecast = matched["forecast_mw"].astype(float)
    abs_errors = errors.abs()

    mae = float(abs_errors.mean())
    rmse = float(math.sqrt(float((errors**2).mean())))
    bias = float(errors.mean())
    mean_actual = float(actual.mean())
    mean_forecast = float(forecast.mean())
    bias_pct = float(bias / mean_actual * 100.0) if mean_actual != 0 else None

    nonzero = matched["actual_mw"].astype(float) != 0
    mape_n = int(nonzero.sum())
    mape = float((abs_errors[nonzero] / actual[nonzero]).mean() * 100.0) if mape_n else None
    mape_excluded = int(n - mape_n)

    smape_denom = forecast.abs() + actual.abs()
    smape_terms = np.where(
        smape_denom == 0,
        0.0,
        2.0 * abs_errors / smape_denom,
    )
    smape = float(np.mean(smape_terms) * 100.0)

    actual_sum = float(actual.sum())
    wape = float(abs_errors.sum() / actual_sum * 100.0) if actual_sum != 0 else None

    over = int((errors > 0).sum())
    under = int((errors < 0).sum())
    zero = int((errors == 0).sum())

    return {
        "mae_mw": mae,
        "rmse_mw": rmse,
        "bias_mw": bias,
        "bias_pct_of_mean_actual": bias_pct,
        "mape_pct": mape,
        "mape_n": mape_n,
        "mape_excluded_zero_actual": mape_excluded,
        "smape_pct": smape,
        "wape_pct": wape,
        "valid_matched_periods": n,
        "overforecast_periods": over,
        "underforecast_periods": under,
        "zero_error_periods": zero,
        "overforecast_pct": float(over / n * 100.0),
        "mean_forecast_mw": mean_forecast,
        "mean_actual_mw": mean_actual,
    }


def grouped_accuracy(periods: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    return {
        "by_date": _group_by(periods, "local_date", sort_key="local_date"),
        "by_hour_local": _group_by_hour(periods),
        "by_lead_bucket": _group_by_lead(periods),
    }


def _group_by(frame: pd.DataFrame, column: str, *, sort_key: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped: list[dict[str, Any]] = []
    for key, group in frame.groupby(column, dropna=True, sort=False):
        expected = len(group)
        metrics = compute_kpis(group)
        label = _date_label(str(key)) if sort_key == "local_date" else str(key)
        grouped.append(_group_record(str(key), label, expected, metrics))
    return sorted(grouped, key=lambda item: item["key"])


def _group_by_hour(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped: list[dict[str, Any]] = []
    for hour, group in frame.groupby("local_hour", dropna=True, sort=True):
        metrics = compute_kpis(group)
        grouped.append(
            _group_record(
                f"{int(hour):02d}",
                f"{int(hour):02d}:00",
                len(group),
                metrics,
            )
        )
    return grouped


def _group_by_lead(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    working = frame.dropna(subset=["lead_hours"]).copy()
    if working.empty:
        return []
    working["lead_bucket"] = pd.cut(
        working["lead_hours"],
        bins=LEAD_BINS,
        labels=LEAD_LABELS,
        right=False,
    )
    grouped: list[dict[str, Any]] = []
    for label, group in working.groupby("lead_bucket", observed=True, sort=True):
        metrics = compute_kpis(group)
        key = str(label).replace(" h", "").replace("–", "-")
        grouped.append(_group_record(key, str(label), len(group), metrics))
    order = {label: index for index, label in enumerate(LEAD_LABELS)}
    return sorted(grouped, key=lambda item: order.get(item["label"], 99))


def _group_record(key: str, label: str, expected: int, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "matched": metrics["valid_matched_periods"],
        "expected": expected,
        "coverage_pct": (metrics["valid_matched_periods"] / expected * 100.0 if expected else 0.0),
        "mae_mw": metrics["mae_mw"],
        "rmse_mw": metrics["rmse_mw"],
        "bias_mw": metrics["bias_mw"],
        "mape_pct": metrics["mape_pct"],
        "wape_pct": metrics["wape_pct"],
        "overforecast": metrics["overforecast_periods"],
        "underforecast": metrics["underforecast_periods"],
    }


def error_distribution(periods: pd.DataFrame) -> dict[str, Any]:
    matched = matched_only(periods)
    if matched.empty:
        return {
            "bins": [],
            "percentiles": {f"p{p}_mw": None for p in PERCENTILES},
            "min_mw": None,
            "max_mw": None,
            "mean_mw": None,
        }
    errors = matched["error_mw"].astype(float)
    minimum = float(errors.min())
    maximum = float(errors.max())
    low = math.floor(minimum / BIN_WIDTH_MW) * BIN_WIDTH_MW
    high = math.ceil(maximum / BIN_WIDTH_MW) * BIN_WIDTH_MW
    if high <= low:
        high = low + BIN_WIDTH_MW
    edges = np.arange(low, high + BIN_WIDTH_MW, BIN_WIDTH_MW)
    counts, edges = np.histogram(errors, bins=edges)
    bins = [
        {
            "from_mw": float(edges[i]),
            "to_mw": float(edges[i + 1]),
            "count": int(counts[i]),
        }
        for i in range(len(counts))
    ]
    percentiles = {f"p{p}_mw": float(np.percentile(errors, p)) for p in PERCENTILES}
    return {
        "bins": bins,
        "percentiles": percentiles,
        "min_mw": minimum,
        "max_mw": maximum,
        "mean_mw": float(errors.mean()),
    }


def _date_label(value: str) -> str:
    try:
        return pd.Timestamp(value).strftime("%d %b")
    except (ValueError, TypeError):
        return value


def round_kpis(kpis: dict[str, Any], digits: int = 2) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in kpis.items():
        if isinstance(value, float) and math.isfinite(value):
            rounded[key] = round(value, digits)
        elif isinstance(value, float):
            rounded[key] = None
        else:
            rounded[key] = value
    return rounded
