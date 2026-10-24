from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.errors import UpstreamError
from app.utils import iso_utc, parse_iso_datetime

logger = logging.getLogger(__name__)

FUELHH_PATH = "/datasets/FUELHH/stream"
WINDFOR_PATH = "/datasets/WINDFOR/stream"
WINDFOR_EVOLUTION_PATH = "/forecast/generation/wind/evolution"

REQUIRED_ACTUAL_FIELDS = ("startTime", "publishTime", "generation", "fuelType")
REQUIRED_FORECAST_FIELDS = ("startTime", "publishTime", "generation")


class ElexonClient:
    """Async Elexon BMRS client; stream requests use bounded publication windows."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        self.settings = settings
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=settings.elexon_base_url.rstrip("/"),
            timeout=httpx.Timeout(settings.elexon_timeout_seconds),
            headers={
                "Accept": "application/json",
                "User-Agent": f"{settings.app_name}/{settings.app_version}",
            },
            transport=transport,
            follow_redirects=True,
        )

    async def __aenter__(self) -> ElexonClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        attempts = max(1, self.settings.elexon_max_retries + 1)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                await self._backoff(attempt)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                last_error = UpstreamError(
                    f"Elexon returned HTTP {response.status_code} for {path}",
                    context={"status_code": response.status_code, "path": path},
                )
                if attempt == attempts - 1:
                    break
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                await self._backoff(attempt, retry_after)
                continue

            if response.status_code >= 400:
                body = response.text[:500]
                raise UpstreamError(
                    f"Elexon rejected the request with HTTP {response.status_code}",
                    context={"status_code": response.status_code, "path": path, "body": body},
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise UpstreamError(
                    "Elexon returned a non-JSON response",
                    context={"path": path, "body": response.text[:500]},
                ) from exc

            records = _extract_records(payload, path)
            logger.info("Elexon %s %s -> %d records", path, params, len(records))
            return records

        raise UpstreamError(
            f"Elexon request failed after {attempts} attempts: {path}",
            context={"path": path, "params": params, "error": str(last_error)},
        ) from last_error

    async def _backoff(self, attempt: int, retry_after: float | None = None) -> None:
        if retry_after is not None:
            delay = retry_after
        else:
            delay = self.settings.elexon_retry_base_seconds * (2**attempt)
            delay += random.uniform(0, 0.25)
        delay = min(delay, 15.0)
        logger.warning("Retrying Elexon request in %.2fs", delay)
        await self._sleep(delay)

    async def fetch_fuelhh_wind(
        self, start: datetime, end: datetime, *, window_days: int = 7
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for win_start, win_end in chunk_windows(start, end, window_days):
            batch = await self._get(
                FUELHH_PATH,
                {
                    "publishDateTimeFrom": iso_utc(win_start),
                    "publishDateTimeTo": iso_utc(win_end),
                    "fuelType": "WIND",
                },
            )
            for record in batch:
                _validate_actual(record)
            records.extend(batch)
        return _dedupe_records(records, keys=("startTime", "publishTime", "fuelType", "generation"))

    async def fetch_windfor(
        self, start: datetime, end: datetime, *, window_days: int = 7
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for win_start, win_end in chunk_windows(start, end, window_days):
            batch = await self._get(
                WINDFOR_PATH,
                {
                    "publishDateTimeFrom": iso_utc(win_start),
                    "publishDateTimeTo": iso_utc(win_end),
                },
            )
            for record in batch:
                _validate_forecast(record)
            records.extend(batch)
        return _dedupe_records(records, keys=("startTime", "publishTime", "generation"))

    async def fetch_windfor_evolution(self, start_time: datetime) -> list[dict[str, Any]]:
        batch = await self._get(
            WINDFOR_EVOLUTION_PATH,
            {"startTime": iso_utc(start_time)},
        )
        for record in batch:
            _validate_forecast(record)
        return batch


def _dedupe_records(
    records: list[dict[str, Any]], *, keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Remove records duplicated at inclusive chunk boundaries."""
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(field) for field in keys)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    if len(unique) != len(records):
        logger.info("Removed %d duplicate records across fetch windows", len(records) - len(unique))
    return unique


def chunk_windows(
    start: datetime, end: datetime, window_days: int
) -> Iterable[tuple[datetime, datetime]]:
    if end <= start:
        raise ValueError("end must be after start")
    cursor = start.astimezone(UTC)
    final = end.astimezone(UTC)
    while cursor < final:
        nxt = min(cursor + timedelta(days=window_days), final)
        yield cursor, nxt
        cursor = nxt


def _extract_records(payload: Any, path: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        data = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        data = payload["data"]
    else:
        raise UpstreamError(
            "Unexpected Elexon response shape",
            context={"path": path, "payload_type": type(payload).__name__},
        )
    if not all(isinstance(record, dict) for record in data):
        raise UpstreamError(
            "Elexon returned non-object records",
            context={"path": path},
        )
    return data


def _require(record: dict[str, Any], keys: Iterable[str], dataset: str) -> None:
    missing = [key for key in keys if key not in record or record[key] is None]
    if missing:
        raise UpstreamError(
            f"Elexon {dataset} record is missing required fields: {missing}",
            context={"dataset": dataset, "missing": missing},
        )


def _validate_actual(record: dict[str, Any]) -> None:
    _require(record, REQUIRED_ACTUAL_FIELDS, "FUELHH")
    if str(record["fuelType"]).upper() != "WIND":
        raise UpstreamError(
            "FUELHH response contains a non-WIND record despite the fuelType filter",
            context={"fuelType": record["fuelType"]},
        )
    parse_iso_datetime(str(record["startTime"]))
    parse_iso_datetime(str(record["publishTime"]))
    try:
        float(record["generation"])
    except (TypeError, ValueError) as exc:
        raise UpstreamError("FUELHH generation is not numeric") from exc


def _validate_forecast(record: dict[str, Any]) -> None:
    _require(record, REQUIRED_FORECAST_FIELDS, "WINDFOR")
    parse_iso_datetime(str(record["startTime"]))
    parse_iso_datetime(str(record["publishTime"]))
    try:
        float(record["generation"])
    except (TypeError, ValueError) as exc:
        raise UpstreamError("WINDFOR generation is not numeric") from exc


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime

            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            return max(0.0, (when - datetime.now(tz=UTC)).total_seconds())
        except (TypeError, ValueError):
            return None
