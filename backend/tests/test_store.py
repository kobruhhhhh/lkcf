from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import DataUnavailableError, UpstreamError
from app.main import create_app
from app.services.analysis_service import AnalysisService
from app.services.ingest import DatasetBundle
from app.services.store import AnalysisStore


def live_bundle(bundle: DatasetBundle, fetched_at: str) -> DatasetBundle:
    return replace(bundle, source="elexon-live", fetched_at=fetched_at)


def test_snapshot_store_reports_offline_provenance(
    settings: Settings, synthetic_bundle: DatasetBundle
) -> None:
    service = AnalysisService(settings, synthetic_bundle)
    store = AnalysisStore(settings, service=service)

    status = store.status()
    assert status["mode"] == "snapshot"
    assert status["status"] == "snapshot"
    assert status["source"] == "Offline snapshot data"
    assert status["loaded"] is True
    assert status["matched_periods"] == 1488
    assert status["cache_ttl_seconds"] == settings.live_cache_ttl_seconds


@pytest.mark.asyncio
async def test_live_store_uses_cache_until_ttl_then_refreshes(
    synthetic_bundle: DatasetBundle,
) -> None:
    settings = Settings(data_source="live", live_cache_ttl_seconds=900)
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    calls = 0

    async def loader() -> DatasetBundle:
        nonlocal calls
        calls += 1
        stamp = f"2026-10-24T12:0{calls}:00Z"
        return live_bundle(synthetic_bundle, stamp)

    store = AnalysisStore(settings, loader=loader, clock=lambda: now)
    first = await store.get_service()
    assert calls == 1
    assert store.status()["status"] == "live"
    assert store.status()["last_successful_fetch_at"] == "2026-10-24T12:01:00Z"

    now += timedelta(seconds=899)
    assert await store.get_service() is first
    assert calls == 1

    now += timedelta(seconds=2)
    second = await store.get_service()
    assert calls == 2
    assert second is not first
    assert store.status()["last_successful_fetch_at"] == "2026-10-24T12:02:00Z"


@pytest.mark.asyncio
async def test_refresh_failure_preserves_last_successful_analysis(
    settings: Settings, synthetic_bundle: DatasetBundle
) -> None:
    failing = False

    async def loader() -> DatasetBundle:
        if failing:
            raise UpstreamError("Elexon is unavailable", status_code=429)
        return live_bundle(synthetic_bundle, "2026-10-24T12:00:00Z")

    service = AnalysisService(settings, synthetic_bundle)
    store = AnalysisStore(settings, service=service, loader=loader)
    await store.refresh(force=True)

    loaded = store.current_service
    assert loaded is not None

    failing = True
    with pytest.raises(UpstreamError):
        await store.refresh(force=True)

    assert store.current_service is loaded
    status = store.status()
    assert status["status"] == "error"
    assert status["loaded"] is True
    assert status["error"]["message"] == "Elexon is unavailable"


@pytest.mark.asyncio
async def test_live_store_without_data_raises_unavailable() -> None:
    settings = Settings(data_source="live")

    async def loader() -> DatasetBundle:
        raise UpstreamError("Elexon returned no records")

    store = AnalysisStore(settings, loader=loader)
    with pytest.raises(DataUnavailableError):
        await store.get_service()

    status = store.status()
    assert status["status"] == "error"
    assert status["loaded"] is False
    assert status["error"]["code"] == "UPSTREAM_ERROR"


def test_status_and_refresh_endpoints(synthetic_bundle: DatasetBundle) -> None:
    settings = Settings(data_source="live")
    failing = False

    async def loader() -> DatasetBundle:
        if failing:
            raise UpstreamError("Elexon refresh failed")
        return live_bundle(synthetic_bundle, "2026-10-24T12:00:00Z")

    store = AnalysisStore(settings, loader=loader)
    app = create_app(settings, store=store)
    with TestClient(app) as client:
        status = client.get("/api/data-status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["mode"] == "live"
        assert payload["status"] == "live"
        assert payload["loaded"] is True
        assert payload["matched_periods"] == 1488

        refreshed = client.post("/api/refresh")
        assert refreshed.status_code == 200
        assert refreshed.json()["last_successful_fetch_at"] == "2026-10-24T12:00:00Z"

        failing = True
        failed = client.post("/api/refresh")
        assert failed.status_code == 502
        assert failed.json()["detail"]["code"] == "UPSTREAM_ERROR"

        assert client.get("/api/summary").status_code == 200
        assert client.get("/api/data-status").json()["status"] == "error"


def test_refresh_preflight_allowed(client: TestClient) -> None:
    preflight = client.options(
        "/api/refresh",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 200
    assert "POST" in preflight.headers["access-control-allow-methods"]
