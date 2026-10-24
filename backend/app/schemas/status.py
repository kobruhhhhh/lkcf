from __future__ import annotations

from typing import Literal

from app.schemas.common import SchemaModel


class DataStatusError(SchemaModel):
    code: str
    message: str
    at: str


class DataStatusResponse(SchemaModel):
    mode: Literal["live", "snapshot"]
    source: str
    status: Literal["live", "refreshing", "error", "snapshot"]
    loaded: bool
    actual_records: int | None
    forecast_records: int | None
    forecast_publications: int | None
    matched_periods: int | None
    expected_periods: int
    matched_coverage_pct: float | None
    last_successful_fetch_at: str | None
    last_attempt_at: str | None
    data_max_publish_time: str | None
    cache_ttl_seconds: int
    next_refresh_at: str | None
    cache_expired: bool
    can_refresh: bool
    error: DataStatusError | None
    generated_at: str
