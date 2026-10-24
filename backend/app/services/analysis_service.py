from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.config import Settings
from app.errors import (
    InvalidDeliveryTimeError,
    InvalidRangeError,
    PeriodNotFoundError,
)
from app.services.analytics import (
    DEFINITIONS,
    compute_kpis,
    error_distribution,
    grouped_accuracy,
    round_kpis,
)
from app.services.ingest import DatasetBundle, load_or_fetch
from app.services.selection import (
    CutoffPolicy,
    assemble_periods,
    select_forecasts,
)
from app.services.transform import (
    NormalizationStats,
    attach_actuals,
    build_period_grid,
    normalize_actuals,
    normalize_forecasts,
)
from app.utils import iso_local, iso_utc, parse_iso_datetime, utc_now

logger = logging.getLogger(__name__)

EXPECTED_PERIODS = 1488
FORECAST_MAPPING_NOTE = (
    "WINDFOR is published at hourly resolution. Each hourly value is applied to "
    "both half-hour settlement periods in that hour; the original forecast hour "
    "and publication timestamp are preserved."
)


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        bundle: DatasetBundle,
        *,
        generated_at: datetime | None = None,
    ) -> None:
        self.settings = settings
        self.bundle = bundle
        self.generated_at = generated_at or utc_now()
        self._build()

    @classmethod
    def from_settings(cls, settings: Settings) -> AnalysisService:
        bundle = load_or_fetch(settings)
        return cls(settings, bundle)

    @property
    def cutoff_policy(self) -> CutoffPolicy:
        return CutoffPolicy(
            local_time=self.settings.decision_cutoff_local_time,
            day_offset=self.settings.decision_cutoff_day_offset,
            timezone=self.settings.decision_cutoff_timezone,
            label=self.settings.decision_cutoff_label,
        )

    def _build(self) -> None:
        actuals, dup_a, inv_a = normalize_actuals(self.bundle.records_actual, self.settings)
        forecasts, dup_f, inv_f = normalize_forecasts(self.bundle.records_forecast, self.settings)
        self.stats = NormalizationStats(
            actual_rows=len(actuals),
            forecast_rows=len(forecasts),
            duplicate_actual_rows_removed=dup_a,
            duplicate_forecast_rows_removed=dup_f,
            invalid_actual_rows=inv_a,
            invalid_forecast_rows=inv_f,
        )
        grid = build_period_grid(self.settings)
        if len(grid) != EXPECTED_PERIODS:
            logger.warning(
                "Expected %d half-hour periods but built %d", EXPECTED_PERIODS, len(grid)
            )
        with_actuals = attach_actuals(grid, actuals)
        selected, diagnostics = select_forecasts(
            with_actuals,
            forecasts,
            self.cutoff_policy,
            self.settings.forecast_mapping,
        )
        self.periods = assemble_periods(with_actuals, selected, diagnostics)
        self.forecasts = forecasts
        self._forecast_by_hour = {
            key: group.copy()
            for key, group in forecasts.groupby("forecast_hour_start_utc", sort=False)
        }
        self._period_by_start = self.periods.set_index("delivery_start_utc", drop=False)
        self._kpis = compute_kpis(self.periods)
        self._groups = grouped_accuracy(self.periods)
        self._distribution = error_distribution(self.periods)
        self._data_quality = self._build_data_quality()
        logger.info(
            "Analysis ready: %d periods, %d matched, MAE %.1f MW",
            len(self.periods),
            self._kpis["valid_matched_periods"],
            self._kpis["mae_mw"] or 0.0,
        )

    @property
    def data_quality(self) -> dict[str, Any]:
        return self._data_quality

    def _build_data_quality(self) -> dict[str, Any]:
        total = len(self.periods)
        actual_present = int(self.periods["actual_mw"].notna().sum())
        forecast_present = int(self.periods["forecast_mw"].notna().sum())
        matched = int(self.periods["status"].eq("matched").sum())
        missing_actual = int(self.periods["actual_mw"].isna().sum())
        missing_forecast = int(self.periods["forecast_mw"].isna().sum())
        no_eligible = int(self.periods["status"].eq("no_eligible_forecast").sum())
        warnings: list[str] = []
        if self.stats.duplicate_actual_rows_removed:
            warnings.append(
                f"{self.stats.duplicate_actual_rows_removed} duplicate FUELHH rows were removed."
            )
        if self.stats.duplicate_forecast_rows_removed:
            warnings.append(
                f"{self.stats.duplicate_forecast_rows_removed} duplicate WINDFOR rows were removed."
            )
        if self.stats.invalid_actual_rows or self.stats.invalid_forecast_rows:
            warnings.append(
                "Invalid Elexon rows were excluded: "
                f"{self.stats.invalid_actual_rows} actual, "
                f"{self.stats.invalid_forecast_rows} forecast."
            )
        if missing_actual:
            warnings.append(f"{missing_actual} delivery periods have no actual generation.")
        if missing_forecast:
            warnings.append(f"{missing_forecast} delivery periods have no selected forecast.")
        if no_eligible:
            warnings.append(
                f"{no_eligible} periods have forecast versions but none eligible at the cutoff."
            )
        if total != EXPECTED_PERIODS:
            warnings.append(f"Analysis grid contains {total} periods; expected {EXPECTED_PERIODS}.")
        if self.settings.forecast_mapping == "hourly_block":
            warnings.append(
                "Hourly WINDFOR values are mapped to both half-hours of each hour "
                "(documented resampling assumption)."
            )
        return {
            "actual_records": actual_present,
            "forecast_records": len(self.forecasts),
            "forecast_publications": int(self.forecasts["forecast_publish_time_utc"].nunique()),
            "duplicate_actual_rows_removed": self.stats.duplicate_actual_rows_removed,
            "duplicate_forecast_rows_removed": self.stats.duplicate_forecast_rows_removed,
            "actual_periods_present": actual_present,
            "matched_periods": matched,
            "missing_actual_periods": missing_actual,
            "missing_forecast_periods": missing_forecast,
            "no_eligible_forecast_periods": no_eligible,
            "actual_coverage_pct": _pct(actual_present, total),
            "forecast_coverage_pct": _pct(forecast_present, total),
            "matched_coverage_pct": _pct(matched, total),
            "warnings": warnings,
        }

    def meta(self) -> dict[str, Any]:
        return {
            "product": self.settings.app_name,
            "analysis_start": self.settings.analysis_start.isoformat(),
            "analysis_end": self.settings.analysis_end.isoformat(),
            "timezone": self.settings.delivery_timezone,
            "unit": "MW",
            "expected_periods": EXPECTED_PERIODS,
            "forecast_resolution": "hourly",
            "forecast_mapping": self.settings.forecast_mapping,
            "forecast_mapping_note": FORECAST_MAPPING_NOTE,
            "cutoff": {
                "local_time": self.settings.decision_cutoff_local_time.strftime("%H:%M"),
                "day_offset": self.settings.decision_cutoff_day_offset,
                "timezone": self.settings.decision_cutoff_timezone,
                "label": self.settings.decision_cutoff_label,
                "is_official_rule": False,
                "description": (
                    "For each delivery day, the latest WINDFOR publication with "
                    "publishTime on or before the cutoff is used. The cutoff is a "
                    "pilot assumption based on the EPEX GB day-ahead gate-closure "
                    "context, not an official Elexon rule."
                ),
                "source_urls": [
                    "https://www.epexspot.com/en/tradingproducts",
                    "https://support.nordpoolgroup.com/support/solutions/articles/8000088463-about-the-n2ex-day-ahead-auction",
                    "https://assets.publishing.service.gov.uk/media/64e5d4bfbc2b52000da004d3/recoupling-gb-auctions-for-cross-border-trade-with-eu-consultation-government-response.pdf",
                ],
            },
            "data_source": self.bundle.source,
            "data_fetched_at": self.bundle.fetched_at or None,
            "data_max_publish_time": self.bundle.max_publish_time,
            "generated_at": iso_utc(self.generated_at),
            "source_urls": {
                "fuelhh": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
                "windfor": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
                "windfor_evolution": "https://bmrs.elexon.co.uk/api-documentation/endpoint/forecast/generation/wind/evolution",
            },
        }

    def summary(self) -> dict[str, Any]:
        return {
            "meta": self.meta(),
            "kpis": round_kpis(self._kpis),
            "data_quality": self._data_quality,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "version": self.settings.app_version,
            "data": {
                "loaded": True,
                "source": self.bundle.source,
                "fetched_at": self.bundle.fetched_at or None,
                "max_publish_time": self.bundle.max_publish_time,
                "analysis_start": self.settings.analysis_start.isoformat(),
                "analysis_end": self.settings.analysis_end.isoformat(),
                "expected_periods": EXPECTED_PERIODS,
                "matched_periods": self._kpis["valid_matched_periods"],
            },
        }

    def timeseries(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        status: str = "all",
    ) -> dict[str, Any]:
        filtered = self._filtered_periods(start_date, end_date)
        if status != "all":
            filtered = filtered[filtered["status"] == status]
        points = [self._point(row) for row in filtered.itertuples(index=False)]
        return {"meta": self.meta(), "count": len(points), "data": points}

    def accuracy(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> dict[str, Any]:
        filtered = self._filtered_periods(start_date, end_date)
        groups = grouped_accuracy(filtered)
        return {
            "meta": self.meta(),
            "overall": round_kpis(compute_kpis(filtered)),
            "by_date": [_round_group(group) for group in groups["by_date"]],
            "by_hour_local": [_round_group(group) for group in groups["by_hour_local"]],
            "by_lead_bucket": [_round_group(group) for group in groups["by_lead_bucket"]],
            "error_distribution": error_distribution(filtered),
            "definitions": DEFINITIONS,
        }

    def forecast_history(self, delivery_start: str) -> dict[str, Any]:
        try:
            parsed = parse_iso_datetime(delivery_start)
        except ValueError as exc:
            raise InvalidDeliveryTimeError(
                "delivery_start must be an ISO 8601 timestamp with a timezone offset"
            ) from exc
        if parsed.minute not in (0, 30) or parsed.second != 0 or parsed.microsecond != 0:
            raise InvalidDeliveryTimeError(
                "delivery_start must align exactly to a half-hour boundary"
            )
        delivery_utc = pd.Timestamp(parsed).tz_convert("UTC")
        if delivery_utc not in self._period_by_start.index:
            raise PeriodNotFoundError(
                "Delivery period is outside the January 2026 analysis window",
                context={"delivery_start": iso_utc(delivery_utc)},
            )
        period = self._period_by_start.loc[delivery_utc]
        cutoff = pd.Timestamp(period["cutoff_utc"])
        hour_start = delivery_utc.floor("h")
        versions_frame = self._forecast_by_hour.get(hour_start, pd.DataFrame())
        selected_publish = (
            pd.Timestamp(period["forecast_publish_time_utc"])
            if pd.notna(period["forecast_publish_time_utc"])
            else None
        )
        selected_mw = float(period["forecast_mw"]) if pd.notna(period["forecast_mw"]) else None

        versions: list[dict[str, Any]] = []
        if not versions_frame.empty:
            ordered = versions_frame.sort_values("forecast_publish_time_utc")
            for row in ordered.itertuples(index=False):
                publish = pd.Timestamp(row.forecast_publish_time_utc)
                forecast_mw = float(row.forecast_mw)
                eligible = publish <= cutoff
                versions.append(
                    {
                        "publish_time_utc": iso_utc(publish),
                        "publish_time_local": iso_local(publish, self.settings.delivery_timezone),
                        "forecast_mw": forecast_mw,
                        "lead_hours": round((delivery_utc - publish).total_seconds() / 3600.0, 2),
                        "eligible": bool(eligible),
                        "after_cutoff": not bool(eligible),
                        "selected": bool(
                            selected_publish is not None
                            and publish == selected_publish
                            and selected_mw is not None
                            and forecast_mw == selected_mw
                        ),
                    }
                )

        has_eligible = any(version["eligible"] for version in versions)
        message: str | None = None
        if not versions:
            message = "No WINDFOR publications were found for this delivery hour."
        elif not has_eligible:
            message = (
                "No forecast was published on or before the decision cutoff; this "
                "period is excluded from the accuracy metrics."
            )

        result = {
            "meta": self.meta(),
            "delivery_start_utc": iso_utc(delivery_utc),
            "delivery_start_local": iso_local(delivery_utc, self.settings.delivery_timezone),
            "settlement_date": str(period["settlement_date"]),
            "settlement_period": int(period["settlement_period"]),
            "forecast_hour_start_utc": iso_utc(hour_start),
            "cutoff_utc": iso_utc(cutoff),
            "cutoff_local": iso_local(cutoff, self.settings.delivery_timezone),
            "selected_publish_time_utc": (
                iso_utc(selected_publish) if selected_publish is not None else None
            ),
            "selected_forecast_mw": selected_mw,
            "actual_mw": (float(period["actual_mw"]) if pd.notna(period["actual_mw"]) else None),
            "has_eligible": has_eligible,
            "message": message,
            "forecast_mapping_note": FORECAST_MAPPING_NOTE,
            "versions": versions,
        }
        return result

    def _filtered_periods(self, start_date: date | None, end_date: date | None) -> pd.DataFrame:
        start = start_date or self.settings.analysis_start
        end = end_date or self.settings.analysis_end
        if start > end:
            raise InvalidRangeError("start_date must be on or before end_date")
        if start < self.settings.analysis_start or end > self.settings.analysis_end:
            raise InvalidRangeError(
                "Requested range must lie within the January 2026 analysis period",
                context={
                    "allowed_start": self.settings.analysis_start.isoformat(),
                    "allowed_end": self.settings.analysis_end.isoformat(),
                },
            )
        mask = (self.periods["local_date"] >= start.isoformat()) & (
            self.periods["local_date"] <= end.isoformat()
        )
        return self.periods.loc[mask]

    def _point(self, row: Any) -> dict[str, Any]:
        tz = self.settings.delivery_timezone
        publish = (
            pd.Timestamp(row.forecast_publish_time_utc)
            if pd.notna(row.forecast_publish_time_utc)
            else None
        )
        forecast_hour = (
            pd.Timestamp(row.forecast_hour_start_utc)
            if pd.notna(row.forecast_hour_start_utc)
            else None
        )
        return {
            "delivery_start_utc": iso_utc(row.delivery_start_utc),
            "delivery_start_local": iso_local(row.delivery_start_utc, tz),
            "settlement_date": str(row.settlement_date),
            "settlement_period": int(row.settlement_period),
            "forecast_hour_start_utc": (
                iso_utc(forecast_hour) if forecast_hour is not None else None
            ),
            "forecast_publish_time_utc": iso_utc(publish) if publish else None,
            "forecast_publish_time_local": iso_local(publish, tz) if publish else None,
            "forecast_mw": _float_or_none(row.forecast_mw),
            "actual_mw": _float_or_none(row.actual_mw),
            "error_mw": _float_or_none(row.error_mw),
            "abs_error_mw": _float_or_none(row.abs_error_mw),
            "percentage_error": (
                round(float(row.percentage_error), 4) if pd.notna(row.percentage_error) else None
            ),
            "lead_hours": (round(float(row.lead_hours), 2) if pd.notna(row.lead_hours) else None),
            "status": str(row.status),
            "note": row.note if isinstance(row.note, str) else None,
        }


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100.0, 2) if denominator else 0.0


def _float_or_none(value: Any) -> float | None:
    return round(float(value), 4) if pd.notna(value) else None


def _round_group(group: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in group.items():
        if isinstance(value, float):
            result[key] = round(value, 2)
        else:
            result[key] = value
    return result
