from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import Settings

logger = logging.getLogger(__name__)

ACTUAL_COLUMNS = [
    "delivery_start_utc",
    "actual_publish_time_utc",
    "actual_mw",
    "settlement_period_actual",
]
FORECAST_COLUMNS = [
    "forecast_start_time_utc",
    "forecast_publish_time_utc",
    "forecast_mw",
    "forecast_hour_start_utc",
]


@dataclass(frozen=True)
class NormalizationStats:
    actual_rows: int
    forecast_rows: int
    duplicate_actual_rows_removed: int
    duplicate_forecast_rows_removed: int
    invalid_actual_rows: int
    invalid_forecast_rows: int


def build_period_grid(settings: Settings) -> pd.DataFrame:
    tz = ZoneInfo(settings.delivery_timezone)
    local_start = pd.Timestamp(settings.analysis_start, tz=tz)
    local_end = pd.Timestamp(settings.analysis_end + timedelta(days=1), tz=tz)
    utc_start = local_start.tz_convert("UTC")
    utc_end = local_end.tz_convert("UTC")
    index = pd.date_range(utc_start, utc_end, freq="30min", inclusive="left")
    local = index.tz_convert(tz)

    frame = pd.DataFrame(
        {
            "delivery_start_utc": index,
            "delivery_start_local": local,
            "local_date": local.strftime("%Y-%m-%d"),
            "local_hour": local.hour.astype(int),
            "settlement_date": local.strftime("%Y-%m-%d"),
            "settlement_period": ((local.hour * 60 + local.minute) // 30 + 1).astype(int),
            "delivery_hour_start_utc": index.floor("h"),
        }
    )
    return frame.reset_index(drop=True)


def normalize_actuals(
    records: list[dict[str, Any]], settings: Settings
) -> tuple[pd.DataFrame, int, int]:
    if not records:
        return pd.DataFrame(columns=ACTUAL_COLUMNS), 0, 0

    frame = pd.DataFrame.from_records(records)
    frame["delivery_start_utc"] = pd.to_datetime(frame["startTime"], utc=True, errors="coerce")
    frame["actual_publish_time_utc"] = pd.to_datetime(
        frame["publishTime"], utc=True, errors="coerce"
    )
    frame["actual_mw"] = pd.to_numeric(frame["generation"], errors="coerce")
    frame["settlement_period_actual"] = pd.to_numeric(
        frame.get("settlementPeriod"), errors="coerce"
    )

    invalid_mask = (
        frame["delivery_start_utc"].isna()
        | frame["actual_publish_time_utc"].isna()
        | frame["actual_mw"].isna()
    )
    invalid = int(invalid_mask.sum())
    if invalid:
        logger.warning("Dropping %d invalid FUELHH rows", invalid)
    frame = frame.loc[~invalid_mask].copy()

    tz = ZoneInfo(settings.delivery_timezone)
    start_utc = pd.Timestamp(settings.analysis_start, tz=tz).tz_convert("UTC")
    end_utc = pd.Timestamp(settings.analysis_end + timedelta(days=1), tz=tz).tz_convert("UTC")
    frame = frame.loc[
        (frame["delivery_start_utc"] >= start_utc) & (frame["delivery_start_utc"] < end_utc)
    ].copy()

    frame = frame.sort_values(["delivery_start_utc", "actual_publish_time_utc"])
    before = len(frame)
    frame = frame.drop_duplicates(subset=["delivery_start_utc"], keep="last")
    duplicates = before - len(frame)
    if duplicates:
        logger.warning("Removed %d duplicate FUELHH delivery periods", duplicates)

    return frame[ACTUAL_COLUMNS].reset_index(drop=True), duplicates, invalid


def normalize_forecasts(
    records: list[dict[str, Any]], settings: Settings
) -> tuple[pd.DataFrame, int, int]:
    if not records:
        return pd.DataFrame(columns=FORECAST_COLUMNS), 0, 0

    frame = pd.DataFrame.from_records(records)
    frame["forecast_start_time_utc"] = pd.to_datetime(frame["startTime"], utc=True, errors="coerce")
    frame["forecast_publish_time_utc"] = pd.to_datetime(
        frame["publishTime"], utc=True, errors="coerce"
    )
    frame["forecast_mw"] = pd.to_numeric(frame["generation"], errors="coerce")

    invalid_mask = (
        frame["forecast_start_time_utc"].isna()
        | frame["forecast_publish_time_utc"].isna()
        | frame["forecast_mw"].isna()
    )
    invalid = int(invalid_mask.sum())
    if invalid:
        logger.warning("Dropping %d invalid WINDFOR rows", invalid)
    frame = frame.loc[~invalid_mask].copy()

    tz = ZoneInfo(settings.delivery_timezone)
    start_utc = pd.Timestamp(settings.analysis_start, tz=tz).tz_convert("UTC")
    end_utc = pd.Timestamp(settings.analysis_end + timedelta(days=1), tz=tz).tz_convert("UTC")
    frame = frame.loc[
        (frame["forecast_start_time_utc"] >= start_utc)
        & (frame["forecast_start_time_utc"] < end_utc)
    ].copy()

    frame["forecast_hour_start_utc"] = frame["forecast_start_time_utc"].dt.floor("h")
    frame = frame.sort_values(["forecast_publish_time_utc", "forecast_start_time_utc"])
    before = len(frame)
    frame = frame.drop_duplicates(
        subset=["forecast_publish_time_utc", "forecast_start_time_utc"],
        keep="last",
    )
    duplicates = before - len(frame)
    if duplicates:
        logger.warning("Removed %d duplicate WINDFOR publication rows", duplicates)

    return frame[FORECAST_COLUMNS].reset_index(drop=True), duplicates, invalid


def attach_actuals(grid: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    merged = grid.merge(
        actuals,
        on="delivery_start_utc",
        how="left",
        validate="one_to_one",
    )
    actual_sp = merged["settlement_period_actual"]
    merged["settlement_period"] = actual_sp.fillna(merged["settlement_period"]).astype("int64")
    merged = merged.drop(columns=["settlement_period_actual"])
    return merged
