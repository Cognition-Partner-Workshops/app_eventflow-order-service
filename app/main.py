"""EventFlow Order Service — FastAPI application entry point.

This service accepts customer orders via a REST API and publishes
``OrderCreated`` events to Azure Service Bus for downstream processing
(e.g. by the payment service).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.events import check_servicebus_health, close_servicebus_client
from app.routers import orders

# Configure structured logging — level is driven by the LOG_LEVEL env var.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    On startup: logs service metadata.
    On shutdown: closes the Azure Service Bus client to release connections.
    """
    logger.info(
        "Starting %s v%s (env=%s)",
        settings.service_name,
        settings.service_version,
        settings.environment,
    )
    yield
    logger.info("Shutting down %s", settings.service_name)
    close_servicebus_client()


app = FastAPI(
    title="EventFlow Order Service",
    description="Accepts customer orders and publishes OrderCreated events to Azure Service Bus.",
    version=settings.service_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)


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
