from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.services.ingest import DatasetBundle

# SYNTHETIC TEST DATA ONLY. Never used by the production analysis.


@pytest.fixture()
def settings() -> Settings:
    # Ignore any developer .env so tests use deterministic defaults.
    return Settings(data_source="snapshot", _env_file=None)


def make_synthetic_bundle() -> DatasetBundle:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    actuals = []
    for half_hour in range(1488):
        delivery = start + timedelta(minutes=30 * half_hour)
        settlement_period = (delivery.hour * 60 + delivery.minute) // 30 + 1
        actuals.append(
            {
                "dataset": "FUELHH",
                "publishTime": (delivery + timedelta(minutes=30))
                .isoformat()
                .replace("+00:00", "Z"),
                "startTime": delivery.isoformat().replace("+00:00", "Z"),
                "settlementDate": delivery.date().isoformat(),
                "settlementPeriod": settlement_period,
                "fuelType": "WIND",
                "generation": 1000,
            }
        )

    forecasts = []
    for day in range(31):
        delivery_date = start + timedelta(days=day)
        publish = (delivery_date - timedelta(days=1)).replace(hour=7, minute=30)
        for hour in range(24):
            delivery = delivery_date.replace(hour=hour)
            forecasts.append(
                {
                    "dataset": "WINDFOR",
                    "publishTime": publish.isoformat().replace("+00:00", "Z"),
                    "startTime": delivery.isoformat().replace("+00:00", "Z"),
                    "generation": 1100,
                }
            )

    return DatasetBundle(
        records_actual=actuals,
        records_forecast=forecasts,
        source="synthetic-test",
        fetched_at="2026-10-24T00:00:00Z",
        manifest={
            "is_synthetic": True,
            "combined_sha256": "synthetic-test-hash",
            "created_at": "2026-10-24T00:00:00Z",
            "sources": {
                "fuelhh": {"sha256": "synthetic-actual"},
                "windfor": {"sha256": "synthetic-forecast"},
            },
        },
    )


@pytest.fixture()
def synthetic_bundle() -> DatasetBundle:
    return make_synthetic_bundle()


@pytest.fixture()
def client(settings: Settings, synthetic_bundle: DatasetBundle):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services.analysis_service import AnalysisService

    service = AnalysisService(settings, synthetic_bundle)
    return TestClient(create_app(settings, service=service))
