from __future__ import annotations

from app.schemas.common import AnalysisMeta, SchemaModel


class TimeseriesPoint(SchemaModel):
    delivery_start_utc: str
    delivery_start_local: str
    settlement_date: str
    settlement_period: int
    forecast_hour_start_utc: str | None = None
    forecast_publish_time_utc: str | None = None
    forecast_publish_time_local: str | None = None
    forecast_mw: float | None = None
    actual_mw: float | None = None
    error_mw: float | None = None
    abs_error_mw: float | None = None
    percentage_error: float | None = None
    lead_hours: float | None = None
    status: str
    note: str | None = None


class TimeseriesResponse(SchemaModel):
    meta: AnalysisMeta
    count: int
    data: list[TimeseriesPoint]
