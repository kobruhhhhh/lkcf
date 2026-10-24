from __future__ import annotations

import pandas as pd

from app.config import Settings
from app.services.transform import (
    attach_actuals,
    build_period_grid,
    normalize_actuals,
    normalize_forecasts,
)

# SYNTHETIC TEST DATA ONLY.


def actual(start: str, publish: str, mw: float = 1000.0) -> dict:
    return {
        "dataset": "FUELHH",
        "startTime": start,
        "publishTime": publish,
        "settlementDate": start[:10],
        "settlementPeriod": 1,
        "fuelType": "WIND",
        "generation": mw,
    }


def forecast(start: str, publish: str, mw: float = 1100.0) -> dict:
    return {
        "dataset": "WINDFOR",
        "startTime": start,
        "publishTime": publish,
        "generation": mw,
    }


def test_grid_has_1488_periods_and_correct_boundaries(settings: Settings) -> None:
    grid = build_period_grid(settings)
    assert len(grid) == 1488
    assert grid.iloc[0]["delivery_start_utc"] == pd.Timestamp("2026-01-01T00:00:00Z")
    assert grid.iloc[-1]["delivery_start_utc"] == pd.Timestamp("2026-01-31T23:30:00Z")
    assert set(grid["delivery_start_utc"].dt.minute) == {0, 30}
    assert grid.iloc[0]["settlement_period"] == 1
    assert grid.iloc[-1]["settlement_period"] == 48


def test_actual_deduplication_keeps_latest_publication(settings: Settings) -> None:
    records = [
        actual("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z", 1000),
        actual("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", 1200),
        actual("2026-01-01T00:30:00Z", "2026-01-01T01:00:00Z", 1300),
    ]
    frame, duplicates, invalid = normalize_actuals(records, settings)
    assert invalid == 0
    assert duplicates == 1
    assert len(frame) == 2
    assert frame.iloc[0]["actual_mw"] == 1200


def test_invalid_actual_rows_are_dropped(settings: Settings) -> None:
    records = [
        actual("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"),
        {"startTime": None, "publishTime": None, "generation": None},
    ]
    frame, _, invalid = normalize_actuals(records, settings)
    assert invalid == 1
    assert len(frame) == 1


def test_actuals_outside_january_are_excluded(settings: Settings) -> None:
    records = [
        actual("2025-12-31T23:30:00Z", "2026-01-01T00:00:00Z"),
        actual("2026-03-01T00:00:00Z", "2026-03-01T00:30:00Z"),
        actual("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"),
    ]
    frame, _, _ = normalize_actuals(records, settings)
    assert len(frame) == 1
    assert frame.iloc[0]["delivery_start_utc"] == pd.Timestamp("2026-01-01T00:00:00Z")


def test_forecast_deduplication_and_hour_floor(settings: Settings) -> None:
    records = [
        forecast("2026-01-01T00:00:00Z", "2025-12-31T07:30:00Z", 1000),
        forecast("2026-01-01T00:00:00Z", "2025-12-31T07:30:00Z", 1050),
        forecast("2026-01-01T01:00:00Z", "2025-12-31T07:30:00Z", 1100),
    ]
    frame, duplicates, invalid = normalize_forecasts(records, settings)
    assert invalid == 0
    assert duplicates == 1
    assert len(frame) == 2
    assert frame.iloc[0]["forecast_mw"] == 1050
    assert frame.iloc[0]["forecast_hour_start_utc"] == pd.Timestamp("2026-01-01T00:00:00Z")


def test_missing_actuals_remain_null(settings: Settings) -> None:
    grid = build_period_grid(settings)
    actuals, _, _ = normalize_actuals(
        [actual("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z")], settings
    )
    merged = attach_actuals(grid, actuals)
    assert merged["actual_mw"].notna().sum() == 1
    assert merged["actual_mw"].isna().sum() == 1487
    assert not merged["actual_mw"].fillna(-1).eq(0).any()
