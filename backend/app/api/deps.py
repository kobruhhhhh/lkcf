from __future__ import annotations

from fastapi import Request

from app.errors import DataUnavailableError
from app.services.analysis_service import AnalysisService
from app.services.store import AnalysisStore


def get_store(request: Request) -> AnalysisStore:
    store: AnalysisStore | None = getattr(request.app.state, "store", None)
    if store is None:
        raise DataUnavailableError("Analysis data store is not initialised")
    return store


async def get_service(request: Request) -> AnalysisService:
    return await get_store(request).get_service()
