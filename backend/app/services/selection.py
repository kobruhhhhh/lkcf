from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CutoffPolicy:
    local_time: time
    day_offset: int
    timezone: str
    label: str

    def cutoff_for(self, delivery_utc: pd.Timestamp) -> pd.Timestamp:
        tz = ZoneInfo(self.timezone)
        local = delivery_utc.tz_convert(tz)
        target_date = local.date() + timedelta(days=self.day_offset)
        cutoff_local = datetime.combine(
            target_date,
            self.local_time,
            tzinfo=tz,
        )
        return pd.Timestamp(cutoff_local).tz_convert("UTC")


def select_forecasts(
    periods: pd.DataFrame,
    forecasts: pd.DataFrame,
    policy: CutoffPolicy,
    mapping: Literal["hourly_block", "exact"] = "hourly_block",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select the latest pre-cutoff forecast; hourly_block maps each hour to both half-hours."""

    base = periods[["delivery_start_utc", "delivery_hour_start_utc"]].copy()
    base["cutoff_utc"] = base["delivery_start_utc"].map(policy.cutoff_for)
    base["join_key"] = (
        base["delivery_start_utc"] if mapping == "exact" else base["delivery_hour_start_utc"]
    )

    if forecasts.empty:
        diagnostics = base[["delivery_start_utc", "cutoff_utc"]].copy()
        diagnostics["candidate_count"] = 0
        diagnostics["eligible_count"] = 0
        return _empty_selected(), diagnostics

    f = forecasts.copy()
    f["join_key"] = (
        f["forecast_start_time_utc"] if mapping == "exact" else f["forecast_hour_start_utc"]
    )

    candidates = base.merge(
        f[
            [
                "join_key",
                "forecast_start_time_utc",
                "forecast_publish_time_utc",
                "forecast_mw",
                "forecast_hour_start_utc",
            ]
        ],
        on="join_key",
        how="inner",
    )

    if candidates.empty:
        diagnostics = base[["delivery_start_utc", "cutoff_utc"]].copy()
        diagnostics["candidate_count"] = 0
        diagnostics["eligible_count"] = 0
        return _empty_selected(), diagnostics

    candidates["match_type"] = np.where(
        candidates["forecast_start_time_utc"] == candidates["delivery_start_utc"],
        "exact",
        "hour_block",
    )
    candidates["exact_rank"] = np.where(candidates["match_type"] == "exact", 0, 1)
    candidates = candidates.drop_duplicates(
        subset=[
            "delivery_start_utc",
            "forecast_start_time_utc",
            "forecast_publish_time_utc",
        ],
        keep="last",
    )

    candidate_counts = candidates.groupby("delivery_start_utc").size().rename("candidate_count")
    eligible = candidates[
        candidates["forecast_publish_time_utc"] <= candidates["cutoff_utc"]
    ].copy()
    eligible_counts = eligible.groupby("delivery_start_utc").size().rename("eligible_count")

    diagnostics = base[["delivery_start_utc", "cutoff_utc"]].copy()
    diagnostics = diagnostics.merge(
        candidate_counts, left_on="delivery_start_utc", right_index=True, how="left"
    )
    diagnostics = diagnostics.merge(
        eligible_counts, left_on="delivery_start_utc", right_index=True, how="left"
    )
    diagnostics["candidate_count"] = diagnostics["candidate_count"].fillna(0).astype(int)
    diagnostics["eligible_count"] = diagnostics["eligible_count"].fillna(0).astype(int)

    if eligible.empty:
        return _empty_selected(), diagnostics

    chosen = (
        eligible.sort_values(
            [
                "delivery_start_utc",
                "forecast_publish_time_utc",
                "exact_rank",
                "forecast_start_time_utc",
            ],
            ascending=[True, False, True, False],
        )
        .drop_duplicates(subset=["delivery_start_utc"], keep="first")
        .copy()
    )

    selected = chosen[
        [
            "delivery_start_utc",
            "forecast_start_time_utc",
            "forecast_publish_time_utc",
            "forecast_mw",
            "forecast_hour_start_utc",
            "match_type",
        ]
    ].reset_index(drop=True)

    return selected, diagnostics


def assemble_periods(
    periods: pd.DataFrame,
    selected: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> pd.DataFrame:
    frame = periods.merge(
        diagnostics,
        on="delivery_start_utc",
        how="left",
        validate="one_to_one",
    )
    frame = frame.merge(
        selected,
        on="delivery_start_utc",
        how="left",
        validate="one_to_one",
    )

    has_candidates = frame["candidate_count"].fillna(0).astype(int) > 0
    has_eligible = frame["eligible_count"].fillna(0).astype(int) > 0
    has_forecast = frame["forecast_mw"].notna()
    has_actual = frame["actual_mw"].notna()

    status = np.select(
        [
            ~has_candidates,
            ~has_eligible,
            has_forecast & ~has_actual,
            has_forecast & has_actual,
            ~has_forecast & has_actual,
            ~has_forecast & ~has_actual,
        ],
        [
            "missing_forecast",
            "no_eligible_forecast",
            "missing_actual",
            "matched",
            "missing_forecast",
            "missing_forecast",
        ],
        default="missing_forecast",
    )
    frame["status"] = status

    frame["forecast_publish_time_utc"] = pd.to_datetime(
        frame["forecast_publish_time_utc"], utc=True, errors="coerce"
    )
    frame["delivery_start_utc"] = pd.to_datetime(
        frame["delivery_start_utc"], utc=True, errors="coerce"
    )
    frame["error_mw"] = frame["forecast_mw"] - frame["actual_mw"]
    frame["abs_error_mw"] = frame["error_mw"].abs()
    frame["percentage_error"] = np.where(
        frame["actual_mw"].notna() & (frame["actual_mw"] != 0),
        frame["error_mw"] / frame["actual_mw"] * 100.0,
        np.nan,
    )
    frame["lead_hours"] = (
        frame["delivery_start_utc"] - frame["forecast_publish_time_utc"]
    ).dt.total_seconds() / 3600.0

    notes: list[str | None] = []
    for row in frame.itertuples(index=False):
        if row.status == "no_eligible_forecast":
            notes.append(
                "Forecast versions exist, but none were published on or before the decision cutoff."
            )
        elif row.status == "missing_forecast":
            notes.append("No WINDFOR publication covers this delivery hour.")
        elif row.status == "missing_actual":
            notes.append("No FUELHH actual generation record for this delivery period.")
        elif row.match_type == "hour_block":
            notes.append("Hourly WINDFOR value applied to this half-hour delivery period.")
        else:
            notes.append(None)
    frame["note"] = notes
    frame["lead_hours"] = frame["lead_hours"].astype(float)
    return frame.reset_index(drop=True)


def _empty_selected() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "delivery_start_utc",
            "forecast_start_time_utc",
            "forecast_publish_time_utc",
            "forecast_mw",
            "forecast_hour_start_utc",
            "match_type",
        ]
    )
