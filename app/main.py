"""EventFlow Order Service — FastAPI application entry point.

This module is the top-level entrypoint for the EventFlow Order Service, a
FastAPI-based microservice responsible for managing customer order lifecycles
within an event-driven architecture.

Architecture overview:
    1. Clients submit orders via the REST API (``POST /api/orders``).
    2. The service calculates order totals using integer-based currency
       arithmetic (amounts are expressed in the smallest currency unit, e.g.
       cents for USD, yen for JPY) and persists orders in an in-memory store.
    3. An ``OrderCreated`` event is published to an Azure Service Bus queue
       (``order-events``) so that downstream consumers — such as the
       EventFlow Payment Service — can react asynchronously.

The application is started via **uvicorn**::

    uvicorn app.main:app --reload --port 8001

Key design decisions:
    * **In-memory order storage** — Orders are held in a plain ``dict``
      rather than a database.  This keeps the demo lightweight and
      dependency-free; a production deployment would swap in a persistent
      store.
    * **Lazy Service Bus client** — The Azure Service Bus client is created
      on first use (see ``app.events``) rather than at startup, so the
      service can still serve HTTP requests when the connection string is
      absent or the broker is unreachable.
    * **Structured logging** — Log output follows a ``%(asctime)s
      %(levelname)s [%(name)s] %(message)s`` pattern compatible with Azure
      Application Insights ingestion.

Modules:
    app.config   — Pydantic-based settings loaded from environment / ``.env``.
    app.models   — Pydantic schemas for requests, responses, and events.
    app.events   — Azure Service Bus client management and event publishing.
    app.routers.orders — CRUD endpoints for the ``/api/orders`` resource.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.events import check_servicebus_health, close_servicebus_client
from app.routers import orders

# ---------------------------------------------------------------------------
# Structured logging configuration
# ---------------------------------------------------------------------------
# The log level is driven by the ``LOG_LEVEL`` environment variable (default
# ``INFO``).  ``getattr`` is used so that an invalid level string degrades
# gracefully to ``INFO`` rather than crashing at import time.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage the application startup and shutdown lifecycle.

    FastAPI invokes this async context manager once when the server starts
    and again when it is shutting down (via the ``yield``).

    Startup phase (before ``yield``):
        * Logs the service name, version, and target environment so that
          operators can correlate container logs with a specific release.
        * No eager connections are opened here — the Azure Service Bus
          client is initialised lazily on first publish to avoid blocking
          startup if the broker is unreachable.

    Shutdown phase (after ``yield``):
        * Gracefully closes the Service Bus client, flushing any pending
          I/O and releasing network sockets.  This prevents resource leaks
          when the container is stopped or restarted by the orchestrator.
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

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
# ``allow_origins=["*"]`` is intentionally permissive because this service is
# designed to sit behind an API gateway or Azure Front Door in production,
# which enforces its own origin policy.  For local development it allows any
# frontend (e.g. a React / Angular SPA on a different port) to call the API
# without extra proxy configuration.
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
    """Kubernetes / container-orchestrator **liveness** probe.

    Returns a minimal JSON payload indicating the process is running and
    able to serve HTTP traffic.  This endpoint does **not** verify
    downstream dependencies — it only confirms that the FastAPI event loop
    is responsive.  If this check fails the orchestrator should restart the
    container.

    Returns:
        A dict with ``status`` (``"healthy"``) and the ``service`` name.
    """
    return {"status": "healthy", "service": settings.service_name}


@app.get("/ready", tags=["health"])
async def readiness_check() -> dict[str, str | bool]:
    """Kubernetes / container-orchestrator **readiness** probe.

    Unlike the liveness probe, this endpoint actively verifies connectivity
    to critical downstream dependencies — currently the Azure Service Bus
    queue.  When the check reports ``"degraded"``, the orchestrator should
    stop routing new traffic to this instance until connectivity recovers,
    but it should **not** restart the container (that is the liveness
    probe's responsibility).

    Returns:
        A dict containing:
        - ``status``: ``"ready"`` when all dependencies are reachable,
          ``"degraded"`` otherwise.
        - ``service``: The service name from configuration.
        - ``servicebus_connected``: Boolean indicating Service Bus
          connectivity.
    """
    servicebus_ok = await check_servicebus_health()
    overall = "ready" if servicebus_ok else "degraded"
    return {
        "status": overall,
        "service": settings.service_name,
        "servicebus_connected": servicebus_ok,
    }
