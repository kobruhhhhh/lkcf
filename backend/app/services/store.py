from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from app.config import Settings
from app.errors import AppError, DataUnavailableError
from app.services.analysis_service import EXPECTED_PERIODS, AnalysisService
from app.services.ingest import DatasetBundle, load_or_fetch
from app.utils import iso_utc, parse_iso_datetime, utc_now

logger = logging.getLogger(__name__)

BundleLoader = Callable[[], Awaitable[DatasetBundle]]
Clock = Callable[[], datetime]


class AnalysisStore:
    """Own the current analysis; failed refreshes keep the last successful one."""

    def __init__(
        self,
        settings: Settings,
        *,
        service: AnalysisService | None = None,
        loader: BundleLoader | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self.settings = settings
        self.mode = settings.data_source
        self._service = service
        self._loader = loader
        self._clock = clock
        self._lock = asyncio.Lock()
        self._refreshing = False
        self._last_error: dict[str, Any] | None = None
        self._last_attempt_at: datetime | None = clock() if service is not None else None
        self._last_success_at: datetime | None = (
            _bundle_time(service.bundle) if service is not None else None
        )

    @property
    def current_service(self) -> AnalysisService | None:
        return self._service

    async def get_service(self) -> AnalysisService:
        if self.mode == "live" and self._should_refresh(self._clock()):
            await self.refresh(force=False, raise_on_error=False)
        if self._service is None:
            reason = (
                self._last_error["message"]
                if self._last_error
                else "Live Elexon data has not been loaded yet."
            )
            raise DataUnavailableError(
                "WindTrace data is not available. Retry the live Elexon request.",
                context={"reason": reason},
            )
        return self._service

    async def refresh(self, *, force: bool = False, raise_on_error: bool = True) -> dict[str, Any]:
        async with self._lock:
            now = self._clock()
            if not force and not self._should_refresh(now):
                return self.status()

            self._refreshing = True
            self._last_attempt_at = now
            try:
                bundle = await self._load_bundle()
                service = await asyncio.to_thread(AnalysisService, self.settings, bundle)
                self._service = service
                self._last_success_at = _bundle_time(bundle) or now
                self._last_error = None
                logger.info(
                    "Analysis cache refreshed from %s: %d actual, %d forecast records",
                    self.mode,
                    len(bundle.records_actual),
                    len(bundle.records_forecast),
                )
            except Exception as exc:  # noqa: BLE001
                self._last_error = _error_detail(exc, now)
                logger.exception("WindTrace data refresh failed")
                if raise_on_error:
                    if isinstance(exc, AppError):
                        raise
                    raise DataUnavailableError(
                        "WindTrace could not refresh its live Elexon data.",
                        context=self._last_error,
                    ) from exc
            finally:
                self._refreshing = False

        return self.status()

    def status(self) -> dict[str, Any]:
        service = self._service
        quality = service.data_quality if service is not None else None
        bundle = service.bundle if service is not None else None
        now = self._clock()

        if self._refreshing:
            status = "refreshing"
        elif self._last_error is not None:
            status = "error"
        elif self.mode == "snapshot":
            status = "snapshot"
        else:
            status = "live"

        next_refresh = (
            self._last_attempt_at + timedelta(seconds=self.settings.live_cache_ttl_seconds)
            if self.mode == "live" and self._last_attempt_at is not None
            else None
        )

        return {
            "mode": self.mode,
            "source": ("Elexon BMRS Live API" if self.mode == "live" else "Offline snapshot data"),
            "status": status,
            "loaded": service is not None,
            "actual_records": len(bundle.records_actual) if bundle is not None else None,
            "forecast_records": len(bundle.records_forecast) if bundle is not None else None,
            "forecast_publications": (bundle.forecast_publications if bundle is not None else None),
            "matched_periods": quality["matched_periods"] if quality is not None else None,
            "expected_periods": EXPECTED_PERIODS,
            "matched_coverage_pct": (
                quality["matched_coverage_pct"] if quality is not None else None
            ),
            "last_successful_fetch_at": (
                iso_utc(self._last_success_at) if self._last_success_at is not None else None
            ),
            "last_attempt_at": (
                iso_utc(self._last_attempt_at) if self._last_attempt_at is not None else None
            ),
            "data_max_publish_time": bundle.max_publish_time if bundle is not None else None,
            "cache_ttl_seconds": self.settings.live_cache_ttl_seconds,
            "next_refresh_at": iso_utc(next_refresh) if next_refresh is not None else None,
            "cache_expired": (
                self.mode == "live" and self._should_refresh(now) and not self._refreshing
            ),
            "can_refresh": True,
            "error": self._last_error,
            "generated_at": iso_utc(now),
        }

    async def _load_bundle(self) -> DatasetBundle:
        if self._loader is not None:
            return await self._loader()
        return await asyncio.to_thread(load_or_fetch, self.settings)

    def _should_refresh(self, now: datetime) -> bool:
        if self.mode != "live":
            return False
        if self._last_attempt_at is None:
            return True
        return now >= self._last_attempt_at + timedelta(
            seconds=self.settings.live_cache_ttl_seconds
        )


def _bundle_time(bundle: DatasetBundle) -> datetime | None:
    if not bundle.fetched_at:
        return None
    try:
        return parse_iso_datetime(str(bundle.fetched_at))
    except ValueError:
        return None


def _error_detail(exc: Exception, at: datetime) -> dict[str, Any]:
    if isinstance(exc, AppError):
        return {
            "code": exc.code,
            "message": exc.message,
            "at": iso_utc(at),
        }
    return {
        "code": "INTERNAL_ERROR",
        "message": "Unexpected error while retrieving Elexon data.",
        "at": iso_utc(at),
    }
