from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.config import Settings
from app.errors import DataUnavailableError, UpstreamError
from app.services.elexon import ElexonClient
from app.utils import iso_utc

logger = logging.getLogger(__name__)

ACTUAL_FILENAME = "fuelhh_wind_2026-01.json.gz"
FORECAST_FILENAME = "windfor_publications_2026-01.json.gz"


@dataclass(frozen=True)
class DatasetBundle:
    records_actual: list[dict[str, Any]]
    records_forecast: list[dict[str, Any]]
    source: str
    fetched_at: str
    manifest: dict[str, Any]

    @property
    def forecast_publications(self) -> int:
        return len({record.get("publishTime") for record in self.records_forecast})

    @property
    def max_publish_time(self) -> str | None:
        values = [
            str(record["publishTime"])
            for record in (*self.records_actual, *self.records_forecast)
            if record.get("publishTime")
        ]
        return max(values) if values else None


def actual_publish_window(settings: Settings) -> tuple[datetime, datetime]:
    start = datetime.combine(settings.analysis_start, time.min, tzinfo=UTC)
    end = datetime.combine(settings.analysis_end + timedelta(days=2), time.min, tzinfo=UTC)
    return start, end


def forecast_publish_window(settings: Settings) -> tuple[datetime, datetime]:
    # Start four days early to capture pre-cutoff vintages for 1 January.
    start = datetime.combine(settings.analysis_start - timedelta(days=4), time.min, tzinfo=UTC)
    end = datetime.combine(settings.analysis_end + timedelta(days=2), time.min, tzinfo=UTC)
    return start, end


def load_or_fetch(settings: Settings) -> DatasetBundle:
    if settings.data_source == "snapshot":
        try:
            return load_snapshot(settings)
        except Exception as exc:
            raise DataUnavailableError(
                "The offline Elexon snapshot could not be loaded",
                context={"error": str(exc)},
            ) from exc
    return _fetch_live_sync(settings)


def load_snapshot(settings: Settings) -> DatasetBundle:
    manifest_path = settings.manifest_path
    if not manifest_path.exists():
        raise FileNotFoundError(f"Snapshot manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("is_synthetic") is not False:
        raise DataUnavailableError(
            "Snapshot manifest must declare is_synthetic: false",
            context={"manifest": str(manifest_path)},
        )
    actual = _read_gzip_json(settings.snapshot_dir / ACTUAL_FILENAME)
    forecast = _read_gzip_json(settings.snapshot_dir / FORECAST_FILENAME)
    _verify_hash(actual, _nested(manifest, "sources", "fuelhh", "sha256"), ACTUAL_FILENAME)
    _verify_hash(forecast, _nested(manifest, "sources", "windfor", "sha256"), FORECAST_FILENAME)
    if not actual or not forecast:
        raise DataUnavailableError("Snapshot files are empty")
    logger.info(
        "Loaded Elexon snapshot: %d actual records, %d forecast records, fetched %s",
        len(actual),
        len(forecast),
        manifest.get("created_at"),
    )
    return DatasetBundle(
        records_actual=actual,
        records_forecast=forecast,
        source="snapshot",
        fetched_at=str(manifest.get("created_at") or ""),
        manifest=manifest,
    )


def save_snapshot(
    settings: Settings,
    records_actual: list[dict[str, Any]],
    records_forecast: list[dict[str, Any]],
    *,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    actual_bytes = _canonical_json(records_actual)
    forecast_bytes = _canonical_json(records_forecast)
    actual_sha = hashlib.sha256(actual_bytes).hexdigest()
    forecast_sha = hashlib.sha256(forecast_bytes).hexdigest()
    combined_sha = hashlib.sha256(f"{actual_sha}:{forecast_sha}".encode()).hexdigest()

    _write_gzip(settings.snapshot_dir / ACTUAL_FILENAME, actual_bytes)
    _write_gzip(settings.snapshot_dir / FORECAST_FILENAME, forecast_bytes)

    actual_window = actual_publish_window(settings)
    forecast_window = forecast_publish_window(settings)
    publications = sorted({str(record["publishTime"]) for record in records_forecast})
    manifest = {
        "product": settings.app_name,
        "version": settings.app_version,
        "created_at": (created_at or datetime.now(tz=UTC))
        .astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "is_synthetic": False,
        "analysis": {
            "start": settings.analysis_start.isoformat(),
            "end": settings.analysis_end.isoformat(),
            "timezone": settings.delivery_timezone,
        },
        "retrieval": {
            "source": "Elexon BMRS Insights API",
            "base_url": settings.elexon_base_url,
        },
        "sources": {
            "fuelhh": {
                "file": ACTUAL_FILENAME,
                "dataset": "FUELHH",
                "url": f"{settings.elexon_base_url.rstrip('/')}/datasets/FUELHH/stream",
                "params": {
                    "publishDateTimeFrom": iso_utc(actual_window[0]),
                    "publishDateTimeTo": iso_utc(actual_window[1]),
                    "fuelType": "WIND",
                },
                "records": len(records_actual),
                "sha256": actual_sha,
                "min_start_time": _min_field(records_actual, "startTime"),
                "max_start_time": _max_field(records_actual, "startTime"),
                "min_publish_time": _min_field(records_actual, "publishTime"),
                "max_publish_time": _max_field(records_actual, "publishTime"),
            },
            "windfor": {
                "file": FORECAST_FILENAME,
                "dataset": "WINDFOR",
                "url": f"{settings.elexon_base_url.rstrip('/')}/datasets/WINDFOR/stream",
                "params": {
                    "publishDateTimeFrom": iso_utc(forecast_window[0]),
                    "publishDateTimeTo": iso_utc(forecast_window[1]),
                },
                "records": len(records_forecast),
                "publications": len(publications),
                "sha256": forecast_sha,
                "min_publish_time": publications[0] if publications else None,
                "max_publish_time": publications[-1] if publications else None,
                "min_start_time": _min_field(records_forecast, "startTime"),
                "max_start_time": _max_field(records_forecast, "startTime"),
            },
        },
        "total_records": len(records_actual) + len(records_forecast),
        "combined_sha256": combined_sha,
    }
    _atomic_write_text(
        settings.manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    logger.info(
        "Saved snapshot: %d actual, %d forecast, %d publications",
        len(records_actual),
        len(records_forecast),
        len(publications),
    )
    return manifest


def _fetch_live_sync(settings: Settings) -> DatasetBundle:
    import asyncio

    return asyncio.run(fetch_live(settings))


async def fetch_live(settings: Settings) -> DatasetBundle:
    actual_start, actual_end = actual_publish_window(settings)
    forecast_start, forecast_end = forecast_publish_window(settings)
    async with ElexonClient(settings) as client:
        actual, forecast = await _fetch_both(
            client,
            actual_start,
            actual_end,
            forecast_start,
            forecast_end,
            window_days=settings.elexon_window_days,
        )
    if not actual:
        raise UpstreamError("Elexon returned no FUELHH WIND records for the analysis window")
    if not forecast:
        raise UpstreamError("Elexon returned no WINDFOR records for the analysis window")
    created_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    manifest = build_manifest(settings, actual, forecast, created_at)
    logger.info(
        "Fetched live Elexon data: %d actual, %d forecast records",
        len(actual),
        len(forecast),
    )
    return DatasetBundle(
        records_actual=actual,
        records_forecast=forecast,
        source="live",
        fetched_at=created_at,
        manifest=manifest,
    )


async def _fetch_both(
    client: ElexonClient,
    actual_start: datetime,
    actual_end: datetime,
    forecast_start: datetime,
    forecast_end: datetime,
    *,
    window_days: int = 7,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actual = await client.fetch_fuelhh_wind(actual_start, actual_end, window_days=window_days)
    forecast = await client.fetch_windfor(forecast_start, forecast_end, window_days=window_days)
    return actual, forecast


def build_manifest(
    settings: Settings,
    records_actual: list[dict[str, Any]],
    records_forecast: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    actual_sha = hashlib.sha256(_canonical_json(records_actual)).hexdigest()
    forecast_sha = hashlib.sha256(_canonical_json(records_forecast)).hexdigest()
    publications = sorted({str(record["publishTime"]) for record in records_forecast})
    return {
        "product": settings.app_name,
        "version": settings.app_version,
        "created_at": created_at,
        "is_synthetic": False,
        "sources": {
            "fuelhh": {
                "records": len(records_actual),
                "sha256": actual_sha,
                "min_start_time": _min_field(records_actual, "startTime"),
                "max_start_time": _max_field(records_actual, "startTime"),
            },
            "windfor": {
                "records": len(records_forecast),
                "publications": len(publications),
                "sha256": forecast_sha,
                "min_publish_time": publications[0] if publications else None,
                "max_publish_time": publications[-1] if publications else None,
            },
        },
        "total_records": len(records_actual) + len(records_forecast),
        "combined_sha256": hashlib.sha256(f"{actual_sha}:{forecast_sha}".encode()).hexdigest(),
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _write_gzip(path: Path, payload: bytes) -> None:
    compressed = gzip.compress(payload, compresslevel=6, mtime=0)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(compressed)
    os.replace(tmp, path)


def _read_gzip_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {path}")
    data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    if not isinstance(data, list):
        raise DataUnavailableError(f"Snapshot file is not a JSON array: {path}")
    return data


def _verify_hash(records: list[dict[str, Any]], expected: str | None, name: str) -> None:
    if not expected:
        raise DataUnavailableError(f"Snapshot manifest has no SHA-256 for {name}")
    actual = hashlib.sha256(_canonical_json(records)).hexdigest()
    if actual != expected:
        raise DataUnavailableError(
            f"Snapshot checksum mismatch for {name}",
            context={"expected": expected, "actual": actual},
        )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _min_field(records: list[dict[str, Any]], field: str) -> str | None:
    values = [str(record[field]) for record in records if record.get(field)]
    return min(values) if values else None


def _max_field(records: list[dict[str, Any]], field: str) -> str | None:
    values = [str(record[field]) for record in records if record.get(field)]
    return max(values) if values else None


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
