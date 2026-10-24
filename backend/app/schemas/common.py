from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CutoffInfo(SchemaModel):
    local_time: str
    day_offset: int
    timezone: str
    label: str
    is_official_rule: bool = False
    description: str
    source_urls: list[str] = Field(default_factory=list)


class AnalysisMeta(SchemaModel):
    product: str
    analysis_start: str
    analysis_end: str
    timezone: str
    unit: str = "MW"
    expected_periods: int
    forecast_resolution: str = "hourly"
    forecast_mapping: str
    forecast_mapping_note: str
    cutoff: CutoffInfo
    data_source: str
    data_fetched_at: str | None
    data_max_publish_time: str | None
    generated_at: str
    source_urls: dict[str, str] = Field(default_factory=dict)


class Kpis(SchemaModel):
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    bias_pct_of_mean_actual: float | None
    mape_pct: float | None
    mape_n: int
    mape_excluded_zero_actual: int
    smape_pct: float | None
    wape_pct: float | None
    valid_matched_periods: int
    overforecast_periods: int
    underforecast_periods: int
    zero_error_periods: int
    overforecast_pct: float | None
    mean_forecast_mw: float | None
    mean_actual_mw: float | None


class DataQuality(SchemaModel):
    actual_records: int
    forecast_records: int
    forecast_publications: int
    duplicate_actual_rows_removed: int
    duplicate_forecast_rows_removed: int
    actual_periods_present: int
    matched_periods: int
    missing_actual_periods: int
    missing_forecast_periods: int
    no_eligible_forecast_periods: int
    actual_coverage_pct: float
    forecast_coverage_pct: float
    matched_coverage_pct: float
    warnings: list[str] = Field(default_factory=list)
