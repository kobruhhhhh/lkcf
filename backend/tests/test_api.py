from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.analysis_service import AnalysisService
from app.services.ingest import DatasetBundle


def client_for(settings: Settings, bundle: DatasetBundle) -> TestClient:
    service = AnalysisService(settings, bundle)
    app = create_app(settings, service=service)
    return TestClient(app)


def test_health_summary_and_cutoff(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["data"]["loaded"] is True

    response = client.get("/api/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["valid_matched_periods"] == 1488
    assert payload["kpis"]["bias_mw"] == 100.0
    assert payload["meta"]["cutoff"]["local_time"] == "09:20"
    assert payload["meta"]["cutoff"]["is_official_rule"] is False
    assert payload["meta"]["forecast_mapping"] == "hourly_block"
    assert payload["data_quality"]["matched_coverage_pct"] == 100.0


def test_timeseries_filters(client: TestClient) -> None:
    full = client.get("/api/timeseries")
    assert full.status_code == 200
    assert full.json()["count"] == 1488

    two_days = client.get(
        "/api/timeseries", params={"start_date": "2026-01-01", "end_date": "2026-01-02"}
    )
    assert two_days.status_code == 200
    assert two_days.json()["count"] == 96
    point = two_days.json()["data"][0]
    assert point["delivery_start_utc"] == "2026-01-01T00:00:00Z"
    assert point["delivery_start_local"].startswith("2026-01-01T00:00:00")
    assert point["forecast_mw"] == 1100.0
    assert point["actual_mw"] == 1000.0
    assert point["error_mw"] == 100.0
    assert point["status"] == "matched"

    matched = client.get("/api/timeseries", params={"status": "matched"})
    assert matched.json()["count"] == 1488


def test_accuracy_groups(client: TestClient) -> None:
    response = client.get("/api/accuracy")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["by_date"]) == 31
    assert len(payload["by_hour_local"]) == 24
    assert len(payload["by_lead_bucket"]) == 7
    assert payload["overall"]["mae_mw"] == 100.0
    assert payload["definitions"]["mape"].startswith("Mean of |error / actual|")


def test_forecast_history(client: TestClient) -> None:
    response = client.get(
        "/api/forecast-history", params={"delivery_start": "2026-01-15T12:30:00Z"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_eligible"] is True
    assert len(payload["versions"]) == 1
    assert payload["versions"][0]["selected"] is True
    assert payload["versions"][0]["eligible"] is True
    assert payload["selected_publish_time_utc"] == "2026-01-14T07:30:00Z"
    assert payload["actual_mw"] == 1000.0


def test_invalid_inputs(client: TestClient) -> None:
    inverted = client.get(
        "/api/timeseries", params={"start_date": "2026-01-10", "end_date": "2026-01-01"}
    )
    assert inverted.status_code == 400
    assert inverted.json()["detail"]["code"] == "INVALID_DATE_RANGE"

    outside = client.get(
        "/api/timeseries", params={"start_date": "2025-12-01", "end_date": "2026-01-01"}
    )
    assert outside.status_code == 400

    malformed = client.get("/api/timeseries", params={"start_date": "not-a-date"})
    assert malformed.status_code == 422

    bad_status = client.get("/api/timeseries", params={"status": "bogus"})
    assert bad_status.status_code == 422

    naive = client.get("/api/forecast-history", params={"delivery_start": "2026-01-15T12:30:00"})
    assert naive.status_code == 400
    assert naive.json()["detail"]["code"] == "INVALID_DELIVERY_TIME"

    misaligned = client.get(
        "/api/forecast-history", params={"delivery_start": "2026-01-15T12:15:00Z"}
    )
    assert misaligned.status_code == 400

    missing_period = client.get(
        "/api/forecast-history", params={"delivery_start": "2026-02-01T00:00:00Z"}
    )
    assert missing_period.status_code == 404
    assert missing_period.json()["detail"]["code"] == "PERIOD_NOT_FOUND"


def test_cors_and_docs(client: TestClient) -> None:
    preflight = client.options(
        "/api/summary",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"

    for origin in ("http://127.0.0.1:3000", "http://localhost:4173"):
        allowed = client.options(
            "/api/summary",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == origin

    assert client.get("/docs").status_code == 200


def test_missing_and_ineligible_data_are_reported(settings: Settings, synthetic_bundle) -> None:
    actuals = [
        record
        for record in synthetic_bundle.records_actual
        if record["startTime"] != "2026-01-01T00:00:00Z"
    ]
    forecasts = [
        record
        for record in synthetic_bundle.records_forecast
        if not record["startTime"].startswith("2026-01-01T02:")
    ]
    forecasts.append(
        {
            "dataset": "WINDFOR",
            "publishTime": "2026-01-01T10:00:00Z",
            "startTime": "2026-01-01T02:00:00Z",
            "generation": 1300,
        }
    )
    bundle = replace(
        synthetic_bundle,
        records_actual=actuals,
        records_forecast=forecasts,
    )
    client = client_for(settings, bundle)
    summary = client.get("/api/summary").json()
    assert summary["data_quality"]["missing_actual_periods"] == 1
    assert summary["data_quality"]["no_eligible_forecast_periods"] == 2
    assert summary["data_quality"]["matched_periods"] == 1485
    assert summary["data_quality"]["warnings"]

    series = client.get("/api/timeseries", params={"status": "no_eligible_forecast"}).json()
    assert series["count"] == 2
    assert series["data"][0]["forecast_mw"] is None

    history = client.get(
        "/api/forecast-history", params={"delivery_start": "2026-01-01T02:00:00Z"}
    ).json()
    assert history["has_eligible"] is False
    assert history["versions"][0]["after_cutoff"] is True
    assert history["versions"][0]["selected"] is False
