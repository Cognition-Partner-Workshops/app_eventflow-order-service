"""Resilience tests for the Order Service.

These tests validate how the order service behaves under adverse conditions:
- Event publishing failures and Service Bus unavailability
- Invalid and edge-case order payloads
- Boundary values for quantities and prices
- API behavior under degraded conditions
- Service Bus client lifecycle and health-check failures
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1. Order Creation Resilience
# ---------------------------------------------------------------------------


class TestOrderCreationResilience:
    """Verify order creation handles failure scenarios gracefully."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_single_item_order(self, mock_publish, client: TestClient):
        """Order with a single item should succeed."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Widget", "quantity": 1, "unit_price": 1000}
            ],
        })
        assert response.status_code == 201
        assert response.json()["amount"] == 1000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_multi_item_order_total_calculation(self, mock_publish, client: TestClient):
        """Order with multiple items should correctly sum the total."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-002",
            "currency": "EUR",
            "items": [
                {"product_id": "p1", "name": "Item A", "quantity": 3, "unit_price": 500},
                {"product_id": "p2", "name": "Item B", "quantity": 2, "unit_price": 1500},
            ],
        })
        assert response.status_code == 201
        # 3*500 + 2*1500 = 1500 + 3000 = 4500
        assert response.json()["amount"] == 4500

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_large_quantity_order(self, mock_publish, client: TestClient):
        """Order with large quantities should still process."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-large",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Bulk Item", "quantity": 10000, "unit_price": 100}
            ],
        })
        assert response.status_code == 201
        assert response.json()["amount"] == 1_000_000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_high_unit_price_order(self, mock_publish, client: TestClient):
        """Order with very high unit price should process without overflow."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-high",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Expensive", "quantity": 1, "unit_price": 99_999_999}
            ],
        })
        assert response.status_code == 201
        assert response.json()["amount"] == 99_999_999

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=False)
    def test_order_created_despite_publish_failure(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Order should still be created and returned even if event publishing fails."""
        response = client.post("/api/orders", json=sample_order_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["order_id"] is not None
        mock_publish.assert_called_once()

    @patch(
        "app.routers.orders.publish_order_created",
        new_callable=AsyncMock,
        side_effect=Exception("Service Bus exploded"),
    )
    def test_order_fails_if_publish_raises_unhandled_exception(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """If event publishing raises an unhandled exception, the error propagates.
        The current implementation does NOT catch generic exceptions from publish,
        so the request raises rather than returning a 500 response.
        This documents the lack of fault isolation in the publish path.
        """
        with pytest.raises(Exception, match="Service Bus exploded"):
            client.post("/api/orders", json=sample_order_payload)

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_jpy_order_accepted_by_order_service(
        self, mock_publish, client: TestClient, sample_jpy_order_payload: dict
    ):
        """Order Service should accept JPY orders — the bug is in Payment Service."""
        response = client.post("/api/orders", json=sample_jpy_order_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "JPY"
        assert data["amount"] == 15800

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_all_supported_currencies_accepted(self, mock_publish, client: TestClient):
        """Every currency in the enum should be accepted by the Order Service."""
        currencies = ["USD", "EUR", "GBP", "JPY", "KRW", "CHF", "CAD", "AUD", "CNY", "INR"]
        for currency in currencies:
            response = client.post("/api/orders", json={
                "customer_id": f"cust-{currency.lower()}",
                "currency": currency,
                "items": [
                    {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 1000}
                ],
            })
            assert response.status_code == 201, f"Failed for currency: {currency}"
            assert response.json()["currency"] == currency


class TestOrderInputValidation:
    """Verify the Order Service rejects invalid input correctly."""

    def test_empty_items_rejected(self, client: TestClient):
        """Orders with no items should be rejected with 422."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [],
        })
        assert response.status_code == 422

    def test_unsupported_currency_rejected(self, client: TestClient):
        """Orders with unsupported currency codes should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "INVALID",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}
            ],
        })
        assert response.status_code == 422

    def test_missing_customer_id(self, client: TestClient):
        """Orders with missing customer_id should be rejected."""
        response = client.post("/api/orders", json={
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}
            ],
        })
        assert response.status_code == 422

    def test_missing_currency(self, client: TestClient):
        """Orders with missing currency should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}
            ],
        })
        assert response.status_code == 422

    def test_missing_items(self, client: TestClient):
        """Orders with no items field should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
        })
        assert response.status_code == 422

    def test_negative_quantity_rejected(self, client: TestClient):
        """Items with negative quantity should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": -1, "unit_price": 100}
            ],
        })
        assert response.status_code == 422

    def test_zero_quantity_rejected(self, client: TestClient):
        """Items with zero quantity should be rejected (gt=0 constraint)."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 0, "unit_price": 100}
            ],
        })
        assert response.status_code == 422

    def test_negative_unit_price_rejected(self, client: TestClient):
        """Items with negative unit_price should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": -100}
            ],
        })
        assert response.status_code == 422

    def test_zero_unit_price_rejected(self, client: TestClient):
        """Items with zero unit_price should be rejected (gt=0 constraint)."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 0}
            ],
        })
        assert response.status_code == 422

    def test_empty_body_rejected(self, client: TestClient):
        """Completely empty request body should be rejected."""
        response = client.post(
            "/api/orders", content=b"", headers={"content-type": "application/json"}
        )
        assert response.status_code == 422

    def test_non_json_body_rejected(self, client: TestClient):
        """Non-JSON request body should be rejected."""
        response = client.post(
            "/api/orders",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    def test_extra_fields_ignored(self, client: TestClient):
        """Extra fields in the request body should be silently ignored."""
        with patch(
            "app.routers.orders.publish_order_created",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.post("/api/orders", json={
                "customer_id": "cust-extra",
                "currency": "USD",
                "items": [
                    {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 500}
                ],
                "extra_field": "this should be ignored",
            })
            assert response.status_code == 201


# ---------------------------------------------------------------------------
# 2. Order Retrieval Resilience
# ---------------------------------------------------------------------------


class TestOrderRetrievalResilience:
    """Verify order retrieval endpoints handle edge cases."""

    def test_get_nonexistent_order(self, client: TestClient):
        """Requesting a non-existent order should return 404."""
        response = client.get("/api/orders/nonexistent-order-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_order_with_special_characters(self, client: TestClient):
        """Order ID with special characters should return 404, not 500."""
        response = client.get("/api/orders/../../etc/passwd")
        assert response.status_code == 404

    def test_list_orders_returns_list(self, client: TestClient):
        """List orders should always return a list, even if empty."""
        response = client.get("/api/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_orders_with_limit_zero(self, client: TestClient):
        """List orders with limit=0 should return empty list."""
        response = client.get("/api/orders?limit=0")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_orders_with_negative_limit(self, client: TestClient):
        """Negative limit — Python slicing returns all but last N items.
        This documents the current behaviour (no server-side clamping).
        """
        response = client.get("/api/orders?limit=-5")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_orders_with_large_limit(self, client: TestClient):
        """Very large limit should not crash."""
        response = client.get("/api/orders?limit=999999")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_created_order_is_retrievable(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """An order that was created should be retrievable by its ID."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        get_resp = client.get(f"/api/orders/{order_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["order_id"] == order_id
        assert get_resp.json()["amount"] == create_resp.json()["amount"]


# ---------------------------------------------------------------------------
# 3. Health & Readiness Endpoint Resilience
# ---------------------------------------------------------------------------


class TestHealthEndpointResilience:
    """Verify health and readiness endpoints under various conditions."""

    def test_health_always_returns_200(self, client: TestClient):
        """Health endpoint should always succeed with 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    def test_readiness_without_servicebus(self, client: TestClient):
        """Without Service Bus, readiness should return degraded but not error."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["servicebus_connected"] is False

    @patch("app.events.get_servicebus_client")
    async def test_readiness_when_servicebus_healthy(self, mock_get_client):
        """When Service Bus is healthy, readiness should return 'ready'."""
        from app.events import check_servicebus_health

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_receiver = MagicMock()
        mock_client.get_queue_receiver.return_value = mock_receiver
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)

        result = await check_servicebus_health()
        assert result is True

    @patch("app.events.get_servicebus_client")
    async def test_readiness_when_servicebus_throws(self, mock_get_client):
        """When Service Bus throws, health check should return False."""
        from app.events import check_servicebus_health

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_queue_receiver.side_effect = ServiceBusError("connection failed")

        result = await check_servicebus_health()
        assert result is False


# ---------------------------------------------------------------------------
# 4. Event Publishing Resilience
# ---------------------------------------------------------------------------


class TestEventPublishingResilience:
    """Verify event publishing handles failures gracefully."""

    @patch("app.events.get_servicebus_client", return_value=None)
    async def test_publish_returns_false_when_client_unavailable(self, mock_get_client):
        """When Service Bus client is None, publish should return False."""
        from app.events import publish_order_created
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-test",
                customer_id="cust-test",
                currency="USD",
                amount=1000,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=1000)],
            )
        )
        result = await publish_order_created(event)
        assert result is False

    @patch("app.events.get_servicebus_client")
    async def test_publish_returns_false_on_servicebus_error(self, mock_get_client):
        """When Service Bus throws during send, publish should return False."""
        from app.events import publish_order_created
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("send failed")

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-err",
                customer_id="cust-err",
                currency="USD",
                amount=2000,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=2000)],
            )
        )
        result = await publish_order_created(event)
        assert result is False

    @patch("app.events.get_servicebus_client")
    async def test_publish_succeeds_when_servicebus_available(self, mock_get_client):
        """When Service Bus is available, publish should succeed and return True."""
        from app.events import publish_order_created
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-ok",
                customer_id="cust-ok",
                currency="GBP",
                amount=3000,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=3000)],
            )
        )
        result = await publish_order_created(event)
        assert result is True
        mock_sender.send_messages.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Service Bus Client Lifecycle Resilience
# ---------------------------------------------------------------------------


class TestServiceBusClientLifecycle:
    """Verify Service Bus client creation and teardown."""

    @patch("app.events.settings")
    def test_client_not_created_without_connection_string(self, mock_settings):
        """Client should not be created when connection string is empty."""
        from app.events import get_servicebus_client

        mock_settings.azure_servicebus_connection_string = ""
        # Reset global client
        import app.events

        app.events._client = None
        result = get_servicebus_client()
        assert result is None

    @patch("app.events.ServiceBusClient")
    @patch("app.events.settings")
    def test_client_creation_failure_returns_none(self, mock_settings, mock_sb_client):
        """If client creation throws, get_servicebus_client should return None."""
        from app.events import get_servicebus_client

        mock_settings.azure_servicebus_connection_string = "fake-conn"
        mock_sb_client.from_connection_string.side_effect = Exception("auth failed")
        import app.events

        app.events._client = None
        result = get_servicebus_client()
        assert result is None

    @patch("app.events.settings")
    def test_close_client_when_none(self, mock_settings):
        """Closing a None client should be a no-op."""
        import app.events
        from app.events import close_servicebus_client

        app.events._client = None
        close_servicebus_client()  # Should not raise
        assert app.events._client is None

    @patch("app.events.settings")
    def test_close_client_handles_exception(self, mock_settings):
        """Closing client that throws during close should not propagate."""
        import app.events
        from app.events import close_servicebus_client

        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("close failed")
        app.events._client = mock_client
        close_servicebus_client()  # Should not raise
        assert app.events._client is None


# ---------------------------------------------------------------------------
# 6. Event Data Serialization Resilience
# ---------------------------------------------------------------------------


class TestEventSerializationResilience:
    """Verify event model serialization handles edge cases."""

    def test_order_event_serialization(self):
        """OrderCreatedEvent should serialize to valid JSON."""
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-ser",
                customer_id="cust-ser",
                currency="USD",
                amount=5000,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=5000)],
            )
        )
        serialized = json.dumps(event.model_dump(), default=str)
        parsed = json.loads(serialized)
        assert parsed["event_type"] == "OrderCreated"
        assert parsed["data"]["order_id"] == "order-ser"
        assert parsed["data"]["amount"] == 5000

    def test_order_event_with_special_characters_in_name(self):
        """Product names with special characters should serialize correctly."""
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-special",
                customer_id="cust-special",
                currency="EUR",
                amount=2000,
                items=[
                    OrderItem(
                        product_id="p1",
                        name='Widget "Pro" <v2> & More',
                        quantity=1,
                        unit_price=2000,
                    )
                ],
            )
        )
        serialized = json.dumps(event.model_dump(), default=str)
        parsed = json.loads(serialized)
        assert parsed["data"]["items"][0]["name"] == 'Widget "Pro" <v2> & More'

    def test_order_event_with_unicode_product_name(self):
        """Product names with unicode characters should serialize correctly."""
        from app.models import OrderCreatedEvent, OrderEventData, OrderItem

        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="order-unicode",
                customer_id="cust-unicode",
                currency="JPY",
                amount=15800,
                items=[
                    OrderItem(
                        product_id="p1",
                        name="キーボード (Keyboard)",
                        quantity=1,
                        unit_price=15800,
                    )
                ],
            )
        )
        serialized = json.dumps(event.model_dump(), default=str, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert "キーボード" in parsed["data"]["items"][0]["name"]


# ---------------------------------------------------------------------------
# 7. Concurrent Order Creation Resilience
# ---------------------------------------------------------------------------


class TestConcurrentOrderResilience:
    """Verify the service handles rapid successive order creation."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_rapid_order_creation(self, mock_publish, client: TestClient):
        """Creating multiple orders in rapid succession should all succeed."""
        order_ids = set()
        for i in range(20):
            response = client.post("/api/orders", json={
                "customer_id": f"cust-rapid-{i}",
                "currency": "USD",
                "items": [
                    {"product_id": f"p{i}", "name": f"Item {i}", "quantity": 1, "unit_price": 100}
                ],
            })
            assert response.status_code == 201
            order_id = response.json()["order_id"]
            assert order_id not in order_ids, f"Duplicate order ID: {order_id}"
            order_ids.add(order_id)

        assert len(order_ids) == 20

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_orders_with_mixed_currencies(self, mock_publish, client: TestClient):
        """Creating orders with different currencies should all succeed."""
        currencies = ["USD", "EUR", "GBP", "JPY", "KRW", "CHF", "CAD", "AUD", "CNY", "INR"]
        for currency in currencies:
            response = client.post("/api/orders", json={
                "customer_id": f"cust-mix-{currency.lower()}",
                "currency": currency,
                "items": [
                    {"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 5000}
                ],
            })
            assert response.status_code == 201
            assert response.json()["currency"] == currency
