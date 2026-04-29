"""Global exception handler for unhandled errors."""

import traceback

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware import get_correlation_id

logger = structlog.stdlib.get_logger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return a structured JSON error response."""
    cid = get_correlation_id()
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        traceback=traceback.format_exc(),
        http_method=request.method,
        http_path=request.url.path,
        correlation_id=cid,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": cid,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""
    app.add_exception_handler(Exception, global_exception_handler)
