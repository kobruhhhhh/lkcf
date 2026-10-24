export interface CutoffInfo {
  local_time: string;
  day_offset: number;
  timezone: string;
  label: string;
  is_official_rule: boolean;
  description: string;
  source_urls: string[];
}

export interface AnalysisMeta {
  product: string;
  analysis_start: string;
  analysis_end: string;
  timezone: string;
  unit: string;
  expected_periods: number;
  forecast_resolution: string;
  forecast_mapping: string;
  forecast_mapping_note: string;
  cutoff: CutoffInfo;
  data_source: string;
  data_fetched_at: string | null;
  data_max_publish_time: string | null;
  generated_at: string;
  source_urls: Record<string, string>;
}

export type DataStatusState = "live" | "refreshing" | "error" | "snapshot";

export interface DataStatusError {
  code: string;
  message: string;
  at: string;
}

export interface DataStatusResponse {
  mode: "live" | "snapshot";
  source: string;
  status: DataStatusState;
  loaded: boolean;
  actual_records: number | null;
  forecast_records: number | null;
  forecast_publications: number | null;
  matched_periods: number | null;
  expected_periods: number;
  matched_coverage_pct: number | null;
  last_successful_fetch_at: string | null;
  last_attempt_at: string | null;
  data_max_publish_time: string | null;
  cache_ttl_seconds: number;
  next_refresh_at: string | null;
  cache_expired: boolean;
  can_refresh: boolean;
  error: DataStatusError | null;
  generated_at: string;
}

export interface Kpis {
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  bias_pct_of_mean_actual: number | null;
  mape_pct: number | null;
  mape_n: number;
  mape_excluded_zero_actual: number;
  smape_pct: number | null;
  wape_pct: number | null;
  valid_matched_periods: number;
  overforecast_periods: number;
  underforecast_periods: number;
  zero_error_periods: number;
  overforecast_pct: number | null;
  mean_forecast_mw: number | null;
  mean_actual_mw: number | null;
}

export interface DataQuality {
  actual_records: number;
  forecast_records: number;
  forecast_publications: number;
  duplicate_actual_rows_removed: number;
  duplicate_forecast_rows_removed: number;
  actual_periods_present: number;
  matched_periods: number;
  missing_actual_periods: number;
  missing_forecast_periods: number;
  no_eligible_forecast_periods: number;
  actual_coverage_pct: number;
  forecast_coverage_pct: number;
  matched_coverage_pct: number;
  warnings: string[];
}

export interface SummaryResponse {
  meta: AnalysisMeta;
  kpis: Kpis;
  data_quality: DataQuality;
}

export type PeriodStatus =
  | "matched"
  | "missing_actual"
  | "no_eligible_forecast"
  | "missing_forecast";

export interface TimeseriesPoint {
  delivery_start_utc: string;
  delivery_start_local: string;
  settlement_date: string;
  settlement_period: number;
  forecast_hour_start_utc: string | null;
  forecast_publish_time_utc: string | null;
  forecast_publish_time_local: string | null;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  percentage_error: number | null;
  lead_hours: number | null;
  status: PeriodStatus;
  note: string | null;
}

export interface TimeseriesResponse {
  meta: AnalysisMeta;
  count: number;
  data: TimeseriesPoint[];
}

export interface AccuracyGroup {
  key: string;
  label: string;
  matched: number;
  expected: number;
  coverage_pct: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  mape_pct: number | null;
  wape_pct: number | null;
  overforecast: number;
  underforecast: number;
}

export interface ErrorBin {
  from_mw: number;
  to_mw: number;
  count: number;
}

export interface ErrorDistribution {
  bins: ErrorBin[];
  percentiles: Record<string, number | null>;
  min_mw: number | null;
  max_mw: number | null;
  mean_mw: number | null;
}

export interface AccuracyResponse {
  meta: AnalysisMeta;
  overall: Kpis;
  by_date: AccuracyGroup[];
  by_hour_local: AccuracyGroup[];
  by_lead_bucket: AccuracyGroup[];
  error_distribution: ErrorDistribution;
  definitions: Record<string, string>;
}

export interface ForecastVersion {
  publish_time_utc: string;
  publish_time_local: string;
  forecast_mw: number;
  lead_hours: number;
  eligible: boolean;
  after_cutoff: boolean;
  selected: boolean;
}

export interface ForecastHistoryResponse {
  meta: AnalysisMeta;
  delivery_start_utc: string;
  delivery_start_local: string;
  settlement_date: string;
  settlement_period: number;
  forecast_hour_start_utc: string;
  cutoff_utc: string;
  cutoff_local: string;
  selected_publish_time_utc: string | null;
  selected_forecast_mw: number | null;
  actual_mw: number | null;
  has_eligible: boolean;
  message: string | null;
  forecast_mapping_note: string;
  versions: ForecastVersion[];
}
