from __future__ import annotations

from pydantic import Field

from app.schemas.common import AnalysisMeta, Kpis, SchemaModel


class AccuracyGroup(SchemaModel):
    key: str
    label: str
    matched: int
    expected: int
    coverage_pct: float
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    mape_pct: float | None
    wape_pct: float | None
    overforecast: int
    underforecast: int


class ErrorBin(SchemaModel):
    from_mw: float
    to_mw: float
    count: int


class ErrorDistribution(SchemaModel):
    bins: list[ErrorBin] = Field(default_factory=list)
    percentiles: dict[str, float | None] = Field(default_factory=dict)
    min_mw: float | None = None
    max_mw: float | None = None
    mean_mw: float | None = None


class AccuracyResponse(SchemaModel):
    meta: AnalysisMeta
    overall: Kpis
    by_date: list[AccuracyGroup]
    by_hour_local: list[AccuracyGroup]
    by_lead_bucket: list[AccuracyGroup]
    error_distribution: ErrorDistribution
    definitions: dict[str, str]
