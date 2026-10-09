import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.container import Container, build_container
from app.domain.errors import (
    DataInconsistencyError,
    DomainError,
    EmptyQueryError,
    IndexNotReadyError,
    InvalidSpreadsheetError,
    StorageUnavailableError,
)
from app.log import configure_logging

logger = logging.getLogger(__name__)

ERROR_STATUS: dict[type[DomainError], int] = {
    EmptyQueryError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidSpreadsheetError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    IndexNotReadyError: status.HTTP_503_SERVICE_UNAVAILABLE,
    StorageUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    DataInconsistencyError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def create_app(
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    app_settings = settings or Settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = container_factory(app_settings)
        container.warm_up()
        app.state.settings = app_settings
        app.state.container = container
        try:
            yield
        finally:
            container.close()

    app = FastAPI(title="Semantic Q&A", version="1.0.0", lifespan=lifespan)
    app.include_router(router)
    app.add_exception_handler(DomainError, _handle_domain_error)
    return app


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    code = next(
        (code for error, code in ERROR_STATUS.items() if isinstance(exc, error)),
        status.HTTP_400_BAD_REQUEST,
    )
    log = logger.error if code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logger.info
    log("%s %s -> %d: %s", request.method, request.url.path, code, exc)
    return JSONResponse(status_code=code, content={"detail": str(exc)})
