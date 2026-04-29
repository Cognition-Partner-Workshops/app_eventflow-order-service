"""EventFlow Order Service — FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.error_handlers import register_error_handlers
from app.events import check_servicebus_health, close_servicebus_client
from app.logging_config import setup_logging
from app.metrics import init_metrics
from app.metrics import router as metrics_router
from app.middleware import CorrelationIdMiddleware, RequestLoggingMiddleware
from app.routers import orders

setup_logging()

logger = structlog.stdlib.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    if settings.metrics_enabled:
        init_metrics()
    logger.info(
        "service_starting",
        service_name=settings.service_name,
        service_version=settings.service_version,
        environment=settings.environment,
        log_format=settings.log_format,
        metrics_enabled=settings.metrics_enabled,
    )
    yield
    logger.info("service_stopping", service_name=settings.service_name)
    close_servicebus_client()


app = FastAPI(
    title="EventFlow Order Service",
    description="Accepts customer orders and publishes OrderCreated events to Azure Service Bus.",
    version=settings.service_version,
    lifespan=lifespan,
)

register_error_handlers(app)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)
app.include_router(metrics_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic liveness probe."""
    return {"status": "healthy", "service": settings.service_name}


@app.get("/ready", tags=["health"])
async def readiness_check() -> dict[str, str | bool]:
    """Readiness probe — verifies downstream dependencies."""
    servicebus_ok = await check_servicebus_health()
    overall = "ready" if servicebus_ok else "degraded"
    return {
        "status": overall,
        "service": settings.service_name,
        "servicebus_connected": servicebus_ok,
    }
