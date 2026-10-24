from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.errors import UpstreamError
from app.services.elexon import ElexonClient, chunk_windows

# SYNTHETIC TEST DATA ONLY. No network calls are made.


def actual_record(mw: int = 1000, fuel: str = "WIND") -> dict:
    return {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T00:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 1,
        "fuelType": fuel,
        "generation": mw,
    }


def forecast_record(mw: int = 1100) -> dict:
    return {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-31T07:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "generation": mw,
    }


async def test_fuelhh_parses_bare_array() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fuelType"] == "WIND"
        assert "publishDateTimeFrom" in request.url.params
        return httpx.Response(200, json=[actual_record()])

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        records = await client.fetch_fuelhh_wind(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
    finally:
        await client.close()
    assert len(records) == 1
    assert records[0]["generation"] == 1000


async def test_windfor_parses_wrapped_data_and_evolution() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/forecast/generation/wind/evolution")
        return httpx.Response(200, json={"metadata": {}, "data": [forecast_record()]})

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        records = await client.fetch_windfor_evolution(datetime(2026, 1, 1, tzinfo=UTC))
    finally:
        await client.close()
    assert len(records) == 1


async def test_429_is_retried_and_retry_after_honoured() -> None:
    calls = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[actual_record()])

    client = ElexonClient(
        Settings(elexon_max_retries=2, elexon_retry_base_seconds=0.01),
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )
    try:
        records = await client.fetch_fuelhh_wind(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
    finally:
        await client.close()
    assert len(records) == 1
    assert calls == 2
    assert sleeps == [0.0]


async def test_500_exhausts_retries() -> None:
    calls = 0

    async def fake_sleep(_: float) -> None:
        return None

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, text="boom")

    client = ElexonClient(
        Settings(elexon_max_retries=2, elexon_retry_base_seconds=0.01),
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()
    assert calls == 3


async def test_timeout_is_retried_then_wrapped() -> None:
    calls = 0

    async def fake_sleep(_: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out", request=request)

    client = ElexonClient(
        Settings(elexon_max_retries=1, elexon_retry_base_seconds=0.01),
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()
    assert calls == 2


async def test_malformed_json_is_rejected() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()


async def test_unexpected_shape_is_rejected() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rows": []})

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()


async def test_non_wind_record_is_rejected() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[actual_record(fuel="CCGT")])

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()


async def test_missing_required_field_is_rejected() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        record = actual_record()
        record.pop("generation")
        return httpx.Response(200, json=[record])

    client = ElexonClient(
        Settings(elexon_max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UpstreamError):
        try:
            await client.fetch_fuelhh_wind(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        finally:
            await client.close()


def test_chunk_windows_are_bounded() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=15)
    windows = list(chunk_windows(start, end, 7))
    assert windows[0] == (start, start + timedelta(days=7))
    assert windows[-1][1] == end
    assert all(end > begin for begin, end in windows)
