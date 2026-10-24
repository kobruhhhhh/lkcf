from __future__ import annotations

import pandas as pd
import pytest

from app.services.analytics import (
    compute_kpis,
    error_distribution,
    grouped_accuracy,
    matched_only,
)

# SYNTHETIC TEST DATA ONLY.


def frame(rows: list[dict]) -> pd.DataFrame:
    data = pd.DataFrame(rows)
    if "forecast_mw" in data and "actual_mw" in data:
        data["error_mw"] = pd.to_numeric(data["forecast_mw"]) - pd.to_numeric(data["actual_mw"])
        data["abs_error_mw"] = data["error_mw"].abs()
    return data


def test_known_metric_values() -> None:
    data = frame(
        [
            {"forecast_mw": 110.0, "actual_mw": 100.0},
            {"forecast_mw": 120.0, "actual_mw": 100.0},
        ]
    )
    kpis = compute_kpis(data)
    assert kpis["mae_mw"] == pytest.approx(15.0)
    assert kpis["rmse_mw"] == pytest.approx((250.0) ** 0.5)
    assert kpis["bias_mw"] == pytest.approx(15.0)
    assert kpis["bias_pct_of_mean_actual"] == pytest.approx(15.0)
    assert kpis["mape_pct"] == pytest.approx(15.0)
    assert kpis["smape_pct"] == pytest.approx(13.8528, abs=0.001)
    assert kpis["wape_pct"] == pytest.approx(15.0)
    assert kpis["valid_matched_periods"] == 2
    assert kpis["overforecast_periods"] == 2
    assert kpis["underforecast_periods"] == 0
    assert kpis["mape_n"] == 2


def test_zero_actual_is_excluded_only_from_mape() -> None:
    data = frame(
        [
            {"forecast_mw": 10.0, "actual_mw": 0.0},
            {"forecast_mw": 110.0, "actual_mw": 100.0},
        ]
    )
    kpis = compute_kpis(data)
    assert kpis["mae_mw"] == pytest.approx(10.0)
    assert kpis["rmse_mw"] == pytest.approx(10.0)
    assert kpis["bias_mw"] == pytest.approx(10.0)
    assert kpis["mape_pct"] == pytest.approx(10.0)
    assert kpis["mape_n"] == 1
    assert kpis["mape_excluded_zero_actual"] == 1
    assert kpis["wape_pct"] == pytest.approx(20.0)
    assert kpis["valid_matched_periods"] == 2


def test_all_zero_actuals_make_percentage_metrics_null() -> None:
    data = frame([{"forecast_mw": 0.0, "actual_mw": 0.0}])
    kpis = compute_kpis(data)
    assert kpis["mae_mw"] == 0.0
    assert kpis["mape_pct"] is None
    assert kpis["wape_pct"] is None
    assert kpis["smape_pct"] == 0.0
    assert kpis["mape_excluded_zero_actual"] == 1


def test_empty_match_set_returns_null_metrics() -> None:
    data = frame(
        [
            {"forecast_mw": None, "actual_mw": 100.0, "error_mw": None},
            {"forecast_mw": 100.0, "actual_mw": None, "error_mw": None},
        ]
    )
    assert matched_only(data).empty
    kpis = compute_kpis(data)
    assert kpis["mae_mw"] is None
    assert kpis["valid_matched_periods"] == 0
    assert kpis["overforecast_pct"] is None


def test_grouped_accuracy_and_distribution() -> None:
    data = frame(
        [
            {
                "forecast_mw": 1100.0,
                "actual_mw": 1000.0,
                "local_date": "2026-01-01",
                "local_hour": 0,
                "lead_hours": 17.0,
            },
            {
                "forecast_mw": 900.0,
                "actual_mw": 1000.0,
                "local_date": "2026-01-01",
                "local_hour": 1,
                "lead_hours": 21.0,
            },
            {
                "forecast_mw": 1050.0,
                "actual_mw": 1000.0,
                "local_date": "2026-01-02",
                "local_hour": 0,
                "lead_hours": 25.0,
            },
            {
                "forecast_mw": 1200.0,
                "actual_mw": 1000.0,
                "local_date": "2026-01-02",
                "local_hour": 1,
                "lead_hours": 40.0,
            },
        ]
    )
    groups = grouped_accuracy(data)
    assert len(groups["by_date"]) == 2
    assert len(groups["by_hour_local"]) == 2
    assert len(groups["by_lead_bucket"]) == 4
    assert groups["by_date"][0]["mae_mw"] == pytest.approx(100.0)
    distribution = error_distribution(data)
    assert sum(item["count"] for item in distribution["bins"]) == 4
    assert set(distribution["percentiles"]) == {
        "p10_mw",
        "p25_mw",
        "p50_mw",
        "p75_mw",
        "p90_mw",
    }
    assert distribution["mean_mw"] == pytest.approx(62.5)


def test_empty_groups_and_distribution() -> None:
    data = frame(
        [
            {
                "forecast_mw": None,
                "actual_mw": None,
                "error_mw": None,
                "local_date": "2026-01-01",
                "local_hour": 0,
                "lead_hours": None,
            }
        ]
    )
    groups = grouped_accuracy(data)
    assert len(groups["by_date"]) == 1
    assert groups["by_date"][0]["matched"] == 0
    assert groups["by_date"][0]["mae_mw"] is None
    assert groups["by_lead_bucket"] == []
    distribution = error_distribution(data)
    assert distribution["bins"] == []
    assert distribution["mean_mw"] is None
