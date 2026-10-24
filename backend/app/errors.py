from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with a stable API code."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.context = context or {}


class UpstreamError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"


class DataUnavailableError(AppError):
    status_code = 503
    code = "DATA_UNAVAILABLE"


class InvalidRangeError(AppError):
    status_code = 400
    code = "INVALID_DATE_RANGE"


class InvalidDeliveryTimeError(AppError):
    status_code = 400
    code = "INVALID_DELIVERY_TIME"


class PeriodNotFoundError(AppError):
    status_code = 404
    code = "PERIOD_NOT_FOUND"
