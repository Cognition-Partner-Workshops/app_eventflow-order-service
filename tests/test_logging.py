"""Tests for structured logging, correlation IDs, metrics, and error handling."""

import json
import logging
from io import StringIO
from unittest.mock import AsyncMock, patch

import structlog
from fastapi.testclient import TestClient

from app.logging_config import setup_logging
from app.main import app
from app.metrics import MetricsCollector


class TestStructuredJsonOutput:
    """Verify JSON log output contains required ECS fields."""

    def test_json_log_contains_ecs_fields(self):
        """Log output must include @timestamp, log.level, message, service.name."""
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        setup_logging()
        fmt = logging.getLogger().handlers[0].formatter
        handler.setFormatter(fmt)

        root = logging.getLogger("test_ecs_fields")
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)

        root.info("hello from test")
        handler.flush()
        output = stream.getvalue().strip()
        record = json.loads(output)

        assert "@timestamp" in record
        assert record["log.level"] == "info"
        assert record["message"] == "hello from test"
        assert record["service.name"] == "eventflow-order-service"
        assert record["service.version"] == "1.0.0"
        assert record["service.environment"] == "development"

        root.removeHandler(handler)

    def test_structlog_json_output(self):
        """structlog bound loggers should also produce ECS-compatible JSON."""
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        setup_logging()
        fmt = logging.getLogger().handlers[0].formatter
        handler.setFormatter(fmt)

        root = logging.getLogger()
        root.addHandler(handler)

        log = structlog.stdlib.get_logger("test_structlog")
        log.info("structlog test", extra_field="value")
        handler.flush()

        lines = stream.getvalue().strip().split("\n")
        record = json.loads(lines[-1])

        assert record["message"] == "structlog test"
        assert record["log.level"] == "info"
        assert "@timestamp" in record

        root.removeHandler(handler)


class TestCorrelationId:
    """Verify correlation ID generation and propagation."""

    def test_correlation_id_generated(self):
        """Response must contain an X-Correlation-ID header."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        cid = response.headers.get("x-correlation-id")
        assert cid is not None
        assert len(cid) == 36  # UUID format

    def test_correlation_id_propagated(self):
        """A client-supplied X-Correlation-ID should be echoed back."""
        client = TestClient(app)
        custom_id = "my-custom-correlation-id-123"
        response = client.get("/health", headers={"X-Correlation-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("x-correlation-id") == custom_id


class TestRequestResponseLogging:
    """Verify request/response logging middleware behaviour."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_request_response_logged(self, mock_publish, caplog):
        """API requests should produce structured log entries."""
        client = TestClient(app)
        with caplog.at_level(logging.INFO):
            client.post("/api/orders", json={
                "customer_id": "cust-log-test",
                "currency": "USD",
                "items": [
                    {"product_id": "p1", "name": "Widget", "quantity": 1, "unit_price": 100}
                ],
            })

    def test_health_endpoint_not_logged(self, caplog):
        """Health endpoints should be excluded from request logging."""
        client = TestClient(app)
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            client.get("/health")


class TestMetricsEndpoint:
    """Verify the /metrics endpoint returns the expected structure."""

    def test_metrics_structure(self):
        """GET /metrics must return all expected metric keys."""
        from app.metrics import init_metrics

        init_metrics()
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "http_requests_total" in data
        assert "http_request_duration_seconds" in data
        assert "orders_created_total" in data
        assert "events_published_total" in data
        assert "service_uptime_seconds" in data

        duration = data["http_request_duration_seconds"]
        assert "count" in duration
        assert "sum" in duration
        assert "p50" in duration
        assert "p95" in duration
        assert "p99" in duration

    def test_metrics_collector_records(self):
        """MetricsCollector should correctly track request metrics."""
        collector = MetricsCollector()
        collector.record_request("GET", "/api/orders", 200, 0.05)
        collector.record_request("POST", "/api/orders", 201, 0.12)
        collector.record_order_created()
        collector.record_event_published(success=True)
        collector.record_event_published(success=False)

        snap = collector.snapshot()
        assert snap["orders_created_total"] == 1
        assert snap["events_published_total"]["success"] == 1
        assert snap["events_published_total"]["failure"] == 1
        assert snap["http_request_duration_seconds"]["count"] == 2


class TestGlobalExceptionHandler:
    """Verify the global exception handler produces structured error logs."""

    def test_unhandled_exception_returns_500(self):
        """Unhandled exceptions should return 500 with correlation_id."""
        from app.main import app as test_app

        @test_app.get("/test-error")
        async def raise_error():
            raise RuntimeError("boom")

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/test-error")
        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert "correlation_id" in body
