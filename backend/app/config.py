from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load .env relative to the backend directory, regardless of the process cwd.
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "WindTrace"
    app_version: str = "1.0.0"
    app_env: str = "development"
    log_level: str = "INFO"

    data_source: Literal["snapshot", "live"] = "live"
    data_dir: Path = Field(default=BACKEND_DIR / "data")
    snapshot_dirname: str = "snapshot"

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = Field(default=30.0, gt=0)
    elexon_max_retries: int = Field(default=3, ge=0)
    elexon_retry_base_seconds: float = Field(default=1.0, ge=0)
    elexon_window_days: int = Field(default=7, ge=1)
    live_cache_ttl_seconds: int = Field(default=300, ge=1)

    analysis_start: date = date(2026, 1, 1)
    analysis_end: date = date(2026, 1, 31)
    delivery_timezone: str = "Europe/London"

    decision_cutoff_local_time: time = time(9, 20)
    decision_cutoff_day_offset: int = -1
    decision_cutoff_timezone: str = "Europe/London"
    decision_cutoff_label: str = "EPEX GB day-ahead gate closure (pilot default)"

    forecast_mapping: Literal["hourly_block", "exact"] = "hourly_block"

    allowed_origins: str = (
        "http://localhost:5173,http://localhost:4173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:4173,http://127.0.0.1:3000"
    )

    @field_validator("elexon_base_url")
    @classmethod
    def _validate_elexon_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("ELEXON_BASE_URL must be an absolute http:// or https:// URL")
        return cleaned

    @field_validator("allowed_origins")
    @classmethod
    def _validate_allowed_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must list at least one browser origin")
        for origin in origins:
            parsed = urlparse(origin)
            if origin == "*" or parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"Invalid origin in ALLOWED_ORIGINS: {origin!r}. "
                    "Use explicit http:// or https:// origins, not '*'."
                )
            if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValueError(
                    f"Invalid origin in ALLOWED_ORIGINS: {origin!r}. "
                    "Origins must not include a path."
                )
        return ",".join(origins)

    @field_validator("decision_cutoff_local_time", mode="before")
    @classmethod
    def _parse_time(cls, value: object) -> object:
        if isinstance(value, str):
            parts = value.strip().split(":")
            if len(parts) not in (2, 3):
                raise ValueError("Cutoff time must be HH:MM or HH:MM:SS")
            hour, minute = int(parts[0]), int(parts[1])
            second = int(parts[2]) if len(parts) == 3 else 0
            return time(hour, minute, second)
        return value

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / self.snapshot_dirname

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.json"
