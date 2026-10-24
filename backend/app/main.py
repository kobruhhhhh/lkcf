from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.errors import AppError
from app.logging_config import configure_logging
from app.services.analysis_service import AnalysisService
from app.services.store import AnalysisStore
from app.utils import utc_now

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    service: AnalysisService | None = None,
    store: AnalysisStore | None = None,
) -> FastAPI:
    app_settings = settings or Settings()
    if service is not None and store is not None:
        raise ValueError("Pass either service or store, not both")
    configure_logging(app_settings.log_level)
    app_store = store or AnalysisStore(app_settings, service=service)
    load_on_startup = service is None and store is None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.started_at = utc_now()
        if load_on_startup:
            await app_store.refresh(force=True, raise_on_error=False)
        app.state.service = app_store.current_service
        status = app_store.status()
        if status["status"] == "error" and status["error"]:
            app.state.startup_error = status["error"]["message"]
        logger.info("WindTrace data mode=%s status=%s", status["mode"], status["status"])
        yield
        logger.info("WindTrace shutting down")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "UK national wind generation forecast accuracy analysis for January 2026, "
            "retrieved live from the official Elexon BMRS FUELHH and WINDFOR APIs."
        ),
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.store = app_store
    app.state.service = app_store.current_service
    app.state.startup_error = None
    app.state.started_at = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
        expose_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.message,
                    "context": exc.context,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error")
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "context": {},
                }
            },
        )

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        return {
            "product": app_settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
            "analysis": f"{app_settings.analysis_start} to {app_settings.analysis_end}",
        }

    return app


app = create_app()
