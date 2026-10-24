from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def parse_iso_datetime(value: str, *, assume_utc: bool = False) -> datetime:
    """Parse an ISO timestamp; Elexon returns Z-suffixed UTC values."""
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        if not assume_utc:
            raise ValueError("Timestamp must include a timezone offset")
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_utc(value: datetime | pd.Timestamp) -> str:
    dt = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def iso_local(value: datetime | pd.Timestamp, timezone: str = "Europe/London") -> str:
    dt = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
    return dt.astimezone(ZoneInfo(timezone)).isoformat()
