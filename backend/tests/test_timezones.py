from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from app.config import Settings
from app.services.selection import CutoffPolicy
from app.services.transform import build_period_grid
from app.utils import iso_local, iso_utc, parse_iso_datetime

# SYNTHETIC TEST DATA ONLY.


def test_parse_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError):
        parse_iso_datetime("2026-01-01T00:00:00")


def test_parse_handles_z_and_offsets() -> None:
    assert parse_iso_datetime("2026-01-01T00:00:00Z") == parse_iso_datetime(
        "2026-01-01T01:00:00+01:00"
    )


def test_iso_helpers_use_utc_and_london() -> None:
    value = parse_iso_datetime("2026-01-01T12:00:00Z")
    assert iso_utc(value) == "2026-01-01T12:00:00Z"
    assert iso_local(value) == "2026-01-01T12:00:00+00:00"


def test_london_dst_conversion() -> None:
    value = parse_iso_datetime("2026-07-01T12:00:00Z")
    assert iso_local(value) == "2026-07-01T13:00:00+01:00"


def test_cutoff_construction_in_winter_and_summer() -> None:
    policy = CutoffPolicy(
        local_time=time(9, 20),
        day_offset=-1,
        timezone="Europe/London",
        label="test",
    )
    winter = policy.cutoff_for(pd.Timestamp("2026-01-15T12:30:00Z"))
    summer = policy.cutoff_for(pd.Timestamp("2026-07-15T12:30:00Z"))
    assert winter == pd.Timestamp("2026-01-14T09:20:00Z")
    assert summer == pd.Timestamp("2026-07-14T08:20:00Z")


def test_january_boundaries_are_inclusive_start_exclusive_end(settings: Settings) -> None:
    grid = build_period_grid(settings)
    starts = set(grid["delivery_start_utc"])
    assert pd.Timestamp("2026-01-01T00:00:00Z") in starts
    assert pd.Timestamp("2026-01-31T23:30:00Z") in starts
    assert pd.Timestamp("2026-02-01T00:00:00Z") not in starts
    assert pd.Timestamp("2025-12-31T23:30:00Z") not in starts


def test_local_dates_are_all_january(settings: Settings) -> None:
    grid = build_period_grid(settings)
    assert set(grid["local_date"]) == {
        pd.Timestamp(f"2026-01-{day:02d}").strftime("%Y-%m-%d") for day in range(1, 32)
    }
