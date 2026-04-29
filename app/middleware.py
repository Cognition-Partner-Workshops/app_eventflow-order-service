"""Correlation ID and request/response logging middleware."""

import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

SKIP_LOG_PATHS: set[str] = {"/health", "/ready"}

logger = structlog.stdlib.get_logger(__name__)


def get_correlation_id() -> str | None:
    """Return the current request's correlation ID (or None outside a request)."""
    return _correlation_id_ctx.get(None)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate a correlation ID for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        token = _correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            _correlation_id_ctx.reset(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log HTTP requests and responses with structured fields."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in SKIP_LOG_PATHS:
            return await call_next(request)

        start = time.perf_counter()

        log = logger.bind(
            http_method=request.method,
            http_path=path,
            query_string=str(request.url.query),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            correlation_id=get_correlation_id(),
        )
        log.info("request_started")

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code

        log = log.bind(
            status_code=status_code,
            response_time_ms=duration_ms,
        )

        if duration_ms >= settings.slow_request_threshold_ms:
            log.warning("slow_request")

        if status_code >= 500:
            log.error("request_finished")
        elif status_code >= 400:
            log.warning("request_finished")
        else:
            log.info("request_finished")

        from app.metrics import metrics_collector

        if settings.metrics_enabled and metrics_collector is not None:
            metrics_collector.record_request(
                method=request.method,
                path=path,
                status_code=status_code,
                duration_seconds=duration_ms / 1000,
            )

        return response
