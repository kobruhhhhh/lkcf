from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from app.services.selection import CutoffPolicy, assemble_periods, select_forecasts

# SYNTHETIC TEST DATA ONLY.


def policy(tz: str = "Europe/London") -> CutoffPolicy:
    return CutoffPolicy(
        local_time=time(9, 20),
        day_offset=-1,
        timezone=tz,
        label="test cutoff",
    )


def periods_frame(deliveries: list[str], actual: float | None = 1000.0) -> pd.DataFrame:
    index = pd.to_datetime(deliveries, utc=True)
    return pd.DataFrame(
        {
            "delivery_start_utc": index,
            "delivery_hour_start_utc": index.floor("h"),
            "delivery_start_local": index,
            "local_date": index.strftime("%Y-%m-%d"),
            "local_hour": index.hour,
            "settlement_date": index.strftime("%Y-%m-%d"),
            "settlement_period": ((index.hour * 60 + index.minute) // 30 + 1),
            "actual_mw": actual,
        }
    )


def forecast_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    start = pd.to_datetime([row[1] for row in rows], utc=True)
    publish = pd.to_datetime([row[0] for row in rows], utc=True)
    return pd.DataFrame(
        {
            "forecast_start_time_utc": start,
            "forecast_publish_time_utc": publish,
            "forecast_mw": [row[2] for row in rows],
            "forecast_hour_start_utc": start.floor("h"),
        }
    )


def run_selection(
    forecasts: pd.DataFrame,
    *,
    delivery: str = "2026-01-15T12:30:00Z",
    mapping: str = "hourly_block",
    actual: float | None = 1000.0,
    tz: str = "Europe/London",
):
    periods = periods_frame([delivery], actual=actual)
    selected, diagnostics = select_forecasts(periods, forecasts, policy(tz), mapping)  # type: ignore[arg-type]
    return assemble_periods(periods, selected, diagnostics)


def test_latest_publication_before_cutoff_is_selected() -> None:
    forecasts = forecast_frame(
        [
            ("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1000),
            ("2026-01-14T09:20:00Z", "2026-01-15T12:00:00Z", 1100),
            ("2026-01-14T09:20:01Z", "2026-01-15T12:00:00Z", 1200),
            ("2026-01-14T10:00:00Z", "2026-01-15T12:00:00Z", 1300),
        ]
    )
    result = run_selection(forecasts)
    row = result.iloc[0]
    assert row["status"] == "matched"
    assert row["forecast_publish_time_utc"] == pd.Timestamp("2026-01-14T09:20:00Z")
    assert row["forecast_mw"] == 1100
    assert row["match_type"] == "hour_block"
    assert row["lead_hours"] == pytest.approx(27.1667, abs=0.001)


def test_one_second_after_cutoff_is_excluded_and_fallback_used() -> None:
    forecasts = forecast_frame(
        [
            ("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1000),
            ("2026-01-14T09:20:01Z", "2026-01-15T12:00:00Z", 1200),
        ]
    )
    result = run_selection(forecasts)
    row = result.iloc[0]
    assert row["forecast_publish_time_utc"] == pd.Timestamp("2026-01-14T07:30:00Z")
    assert row["forecast_mw"] == 1000


def test_publication_exactly_at_cutoff_is_inclusive() -> None:
    forecasts = forecast_frame([("2026-01-14T09:20:00Z", "2026-01-15T12:00:00Z", 1250)])
    result = run_selection(forecasts)
    assert result.iloc[0]["forecast_mw"] == 1250


def test_hourly_forecast_is_applied_to_both_half_hours() -> None:
    forecasts = forecast_frame([("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1400)])
    on_hour = run_selection(forecasts, delivery="2026-01-15T12:00:00Z")
    half_hour = run_selection(forecasts, delivery="2026-01-15T12:30:00Z")
    assert on_hour.iloc[0]["forecast_mw"] == 1400
    assert half_hour.iloc[0]["forecast_mw"] == 1400
    assert on_hour.iloc[0]["match_type"] == "exact"
    assert half_hour.iloc[0]["match_type"] == "hour_block"


def test_exact_mapping_leaves_half_hour_unmatched() -> None:
    forecasts = forecast_frame([("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1400)])
    result = run_selection(forecasts, delivery="2026-01-15T12:30:00Z", mapping="exact")
    row = result.iloc[0]
    assert row["status"] == "missing_forecast"
    assert pd.isna(row["forecast_mw"])


def test_no_candidates_is_missing_forecast() -> None:
    assert forecast_frame([]).empty
    result = run_selection(forecast_frame([]))
    assert result.iloc[0]["status"] == "missing_forecast"
    assert result.iloc[0]["candidate_count"] == 0


def test_versions_after_cutoff_only_is_no_eligible_forecast() -> None:
    forecasts = forecast_frame([("2026-01-14T10:00:00Z", "2026-01-15T12:00:00Z", 1500)])
    result = run_selection(forecasts)
    row = result.iloc[0]
    assert row["status"] == "no_eligible_forecast"
    assert row["candidate_count"] == 1
    assert row["eligible_count"] == 0
    assert pd.isna(row["forecast_mw"])


def test_missing_actual_is_reported_without_zero_fill() -> None:
    forecasts = forecast_frame([("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1500)])
    result = run_selection(forecasts, actual=None)
    row = result.iloc[0]
    assert row["status"] == "missing_actual"
    assert pd.isna(row["actual_mw"])
    assert pd.isna(row["error_mw"])


def test_cutoff_is_local_in_summer_time() -> None:
    forecasts = forecast_frame(
        [
            ("2026-07-14T08:20:00Z", "2026-07-15T12:00:00Z", 900),
            ("2026-07-14T08:20:01Z", "2026-07-15T12:00:00Z", 950),
        ]
    )
    result = run_selection(forecasts, delivery="2026-07-15T12:30:00Z", tz="Europe/London")
    assert result.iloc[0]["forecast_mw"] == 900
    assert result.iloc[0]["cutoff_utc"] == pd.Timestamp("2026-07-14T08:20:00Z")


def test_duplicates_same_publish_are_deterministic() -> None:
    forecasts = forecast_frame(
        [
            ("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1000),
            ("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 1050),
        ]
    )
    result = run_selection(forecasts)
    assert result.iloc[0]["forecast_mw"] == 1050
