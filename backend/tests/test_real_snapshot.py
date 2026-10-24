from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services.analysis_service import AnalysisService
from app.services.ingest import ACTUAL_FILENAME, FORECAST_FILENAME, load_snapshot

_SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshot"

pytestmark = [
    pytest.mark.realdata,
    pytest.mark.skipif(
        not all((_SNAPSHOT_DIR / name).exists() for name in (ACTUAL_FILENAME, FORECAST_FILENAME)),
        reason="Offline Elexon snapshot absent; run python scripts/fetch_snapshot.py to create it",
    ),
]


def test_committed_snapshot_is_real_and_complete() -> None:
    settings = Settings(data_source="snapshot")
    bundle = load_snapshot(settings)
    assert bundle.manifest["is_synthetic"] is False
    assert bundle.manifest["sources"]["fuelhh"]["records"] == 1537
    assert bundle.manifest["sources"]["windfor"]["records"] == 21024
    assert bundle.source == "snapshot"


def test_real_january_metrics_and_history() -> None:
    settings = Settings(data_source="snapshot")
    service = AnalysisService.from_settings(settings)
    summary = service.summary()
    assert summary["data_quality"]["matched_periods"] == 1488
    assert summary["data_quality"]["matched_coverage_pct"] == 100.0
    assert summary["kpis"]["mae_mw"] == pytest.approx(2145.17, abs=0.01)
    assert summary["kpis"]["rmse_mw"] == pytest.approx(2615.81, abs=0.01)
    assert summary["kpis"]["bias_mw"] == pytest.approx(1851.90, abs=0.01)
    assert summary["kpis"]["mape_pct"] == pytest.approx(22.44, abs=0.01)
    assert summary["kpis"]["overforecast_periods"] == 1263
    assert summary["kpis"]["underforecast_periods"] == 225

    history = service.forecast_history("2026-01-01T00:00:00Z")
    assert len(history["versions"]) == 24
    assert history["selected_publish_time_utc"] == "2025-12-31T07:30:00Z"
    assert history["has_eligible"] is True
    after_cutoff = [v for v in history["versions"] if v["after_cutoff"]]
    assert after_cutoff
    assert not any(v["selected"] for v in after_cutoff)
