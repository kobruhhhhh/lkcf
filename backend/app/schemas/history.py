from __future__ import annotations

from app.schemas.common import AnalysisMeta, SchemaModel


class ForecastVersion(SchemaModel):
    publish_time_utc: str
    publish_time_local: str
    forecast_mw: float
    lead_hours: float
    eligible: bool
    after_cutoff: bool
    selected: bool


class ForecastHistoryResponse(SchemaModel):
    meta: AnalysisMeta
    delivery_start_utc: str
    delivery_start_local: str
    settlement_date: str
    settlement_period: int
    forecast_hour_start_utc: str
    cutoff_utc: str
    cutoff_local: str
    selected_publish_time_utc: str | None
    selected_forecast_mw: float | None
    actual_mw: float | None
    has_eligible: bool
    message: str | None
    forecast_mapping_note: str
    versions: list[ForecastVersion]
