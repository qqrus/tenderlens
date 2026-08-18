from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tenderlens.api.router import api_router
from tenderlens.core.config import Settings, get_settings
from tenderlens.core.errors import register_error_handlers
from tenderlens.core.logging import configure_logging
from tenderlens.core.middleware import RequestContextMiddleware
from tenderlens.db.session import Database

logger = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        log_level=resolved_settings.log_level,
        json_logs=resolved_settings.app_env != "development",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(resolved_settings.database_dsn)
        application.state.database = database
        logger.info("application_started", environment=resolved_settings.app_env)
        try:
            yield
        finally:
            await database.close()
            logger.info("application_stopped")

    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description=(
            "AI-assisted tender analysis with verifiable citations. "
            "The service does not provide legal advice."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in resolved_settings.cors_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=resolved_settings.api_prefix)
    register_error_handlers(application)
    return application


app = create_app()
