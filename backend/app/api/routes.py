from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_service, get_store
from app.schemas import (
    AccuracyResponse,
    DataStatusResponse,
    ForecastHistoryResponse,
    HealthResponse,
    SummaryResponse,
    TimeseriesResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.store import AnalysisStore

router = APIRouter(prefix="/api", tags=["wind-analysis"])

StatusFilter = Literal[
    "all",
    "matched",
    "missing_actual",
    "missing_forecast",
    "no_eligible_forecast",
]


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse | JSONResponse:
    store = get_store(request)
    settings = request.app.state.settings
    status = store.status()
    service = store.current_service
    if service is None:
        error = status.get("error")
        payload = HealthResponse(
            status="unavailable",
            version=settings.app_version,
            data={
                "loaded": False,
                "source": status.get("source"),
                "fetched_at": status.get("last_successful_fetch_at"),
                "max_publish_time": None,
                "analysis_start": settings.analysis_start.isoformat(),
                "analysis_end": settings.analysis_end.isoformat(),
                "expected_periods": None,
                "matched_periods": None,
            },
            error=(error or {}).get("message", "Data not loaded"),
        )
        return JSONResponse(status_code=503, content=payload.model_dump())
    payload = HealthResponse.model_validate(service.health())
    return payload


@router.get("/data-status", response_model=DataStatusResponse, tags=["system"])
async def data_status(request: Request) -> DataStatusResponse:
    store = get_store(request)
    try:
        await store.get_service()
    except Exception:
        pass
    return DataStatusResponse.model_validate(store.status())


@router.post("/refresh", response_model=DataStatusResponse, tags=["system"])
async def refresh_data(request: Request) -> DataStatusResponse:
    store: AnalysisStore = get_store(request)
    status = await store.refresh(force=True, raise_on_error=True)
    return DataStatusResponse.model_validate(status)


@router.get("/summary", response_model=SummaryResponse)
def summary(service: AnalysisService = Depends(get_service)) -> SummaryResponse:
    return SummaryResponse.model_validate(service.summary())


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    start_date: date | None = None,
    end_date: date | None = None,
    status: StatusFilter = "all",
    service: AnalysisService = Depends(get_service),
) -> TimeseriesResponse:
    return TimeseriesResponse.model_validate(
        service.timeseries(start_date=start_date, end_date=end_date, status=status)
    )


@router.get("/accuracy", response_model=AccuracyResponse)
def accuracy(
    start_date: date | None = None,
    end_date: date | None = None,
    service: AnalysisService = Depends(get_service),
) -> AccuracyResponse:
    return AccuracyResponse.model_validate(
        service.accuracy(start_date=start_date, end_date=end_date)
    )


@router.get("/forecast-history", response_model=ForecastHistoryResponse)
def forecast_history(
    delivery_start: str,
    service: AnalysisService = Depends(get_service),
) -> ForecastHistoryResponse:
    return ForecastHistoryResponse.model_validate(service.forecast_history(delivery_start))
