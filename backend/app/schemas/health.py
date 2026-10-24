from __future__ import annotations

from app.schemas.common import SchemaModel


class HealthData(SchemaModel):
    loaded: bool
    source: str | None = None
    fetched_at: str | None = None
    max_publish_time: str | None = None
    analysis_start: str | None = None
    analysis_end: str | None = None
    expected_periods: int | None = None
    matched_periods: int | None = None


class HealthResponse(SchemaModel):
    status: str
    version: str
    data: HealthData
    error: str | None = None
