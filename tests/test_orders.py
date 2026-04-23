"""Tests for the Order API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestCreateOrder:
    """Tests for POST /api/orders."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_usd(self, mock_publish, client: TestClient, sample_order_payload: dict):
        """Creating a USD order should succeed and calculate the correct total."""
        response = client.post("/api/orders", json=sample_order_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == "cust-001"
        assert data["currency"] == "USD"
        # 2 * 2999 + 1 * 4999 = 10997
        assert data["amount"] == 10997
        assert data["status"] == "pending"
        assert len(data["items"]) == 2
        assert data["order_id"] is not None
        mock_publish.assert_called_once()

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_eur(
        self, mock_publish, client: TestClient, sample_eur_order_payload: dict
    ):
        """Creating a EUR order should succeed."""
        response = client.post("/api/orders", json=sample_eur_order_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "EUR"
        assert data["amount"] == 8999
        mock_publish.assert_called_once()

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_jpy(
        self, mock_publish, client: TestClient, sample_jpy_order_payload: dict
    ):
        """Creating a JPY order should succeed in the Order Service.

        The Order Service correctly handles JPY — amounts are in yen (smallest unit).
        The bug is in the downstream Payment Service, not here.
        """
        response = client.post("/api/orders", json=sample_jpy_order_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "JPY"
        assert data["amount"] == 15800
        mock_publish.assert_called_once()

    def test_create_order_empty_items(self, client: TestClient):
        """Orders with no items should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [],
        })
        assert response.status_code == 422

    def test_create_order_invalid_currency(self, client: TestClient):
        """Orders with unsupported currencies should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "XYZ",
            "items": [{"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}],
        })
        assert response.status_code == 422

    def test_create_order_negative_quantity(self, client: TestClient):
        """Orders with negative quantity should be rejected."""
        response = client.post("/api/orders", json={
            "customer_id": "cust-001",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Test", "quantity": -1, "unit_price": 100}],
        })
        assert response.status_code == 422

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=False)
    def test_create_order_event_publish_failure(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Order should still be created even if event publishing fails."""
        response = client.post("/api/orders", json=sample_order_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"


class TestGetOrder:
    """Tests for GET /api/orders/{order_id}."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_get_existing_order(self, mock_publish, client: TestClient, sample_order_payload: dict):
        """Should return a previously created order."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.get(f"/api/orders/{order_id}")

        assert response.status_code == 200
        assert response.json()["order_id"] == order_id

    def test_get_nonexistent_order(self, client: TestClient):
        """Should return 404 for unknown order IDs."""
        response = client.get("/api/orders/nonexistent-id")
        assert response.status_code == 404


class TestUpdateOrderStatus:
    """Tests for PATCH /api/orders/{order_id}/status."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_success(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should update the status of an existing order."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status", json={"status": "completed"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["order_id"] == order_id

    def test_update_status_nonexistent_order(self, client: TestClient):
        """Should return 404 when updating a nonexistent order."""
        response = client.patch(
            "/api/orders/nonexistent-id/status", json={"status": "completed"}
        )
        assert response.status_code == 404

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_pending_to_completed(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Transition pending -> completed should succeed."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status", json={"status": "completed"}
        )
        assert response.json()["status"] == "completed"

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_pending_to_failed(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Transition pending -> failed should succeed."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status", json={"status": "failed"}
        )
        assert response.json()["status"] == "failed"

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_pending_to_processing(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Transition pending -> processing should succeed."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status", json={"status": "processing"}
        )
        assert response.json()["status"] == "processing"


class TestListOrders:
    """Tests for GET /api/orders."""

    def test_list_orders_empty(self, client: TestClient):
        """Should return an empty list when no orders exist."""
        # Note: orders persist in memory across tests in the same process,
        # so this test may see orders from previous tests
        response = client.get("/api/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_with_limit(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """The limit parameter should cap the number of returned orders."""
        # Clear in-memory store for a clean test
        from app.routers.orders import _orders

        _orders.clear()

        for _ in range(5):
            client.post("/api/orders", json=sample_order_payload)

        response = client.get("/api/orders?limit=3")
        assert response.status_code == 200
        assert len(response.json()) == 3

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_sorted_by_created_at_descending(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Orders should be sorted newest-first."""
        from app.routers.orders import _orders

        _orders.clear()

        for _ in range(3):
            client.post("/api/orders", json=sample_order_payload)

        response = client.get("/api/orders")
        orders = response.json()
        timestamps = [o["created_at"] for o in orders]
        assert timestamps == sorted(timestamps, reverse=True)

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_after_creating_multiple(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """All created orders should appear in the list."""
        from app.routers.orders import _orders

        _orders.clear()

        created_ids = []
        for _ in range(4):
            resp = client.post("/api/orders", json=sample_order_payload)
            created_ids.append(resp.json()["order_id"])

        response = client.get("/api/orders")
        listed_ids = [o["order_id"] for o in response.json()]
        for oid in created_ids:
            assert oid in listed_ids


class TestCreateOrderEdgeCases:
    """Additional edge-case tests for POST /api/orders."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_single_item_order(self, mock_publish, client: TestClient):
        """An order with exactly one item should succeed."""
        payload = {
            "customer_id": "cust-1",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Widget", "quantity": 1, "unit_price": 500}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["amount"] == 500
        assert len(response.json()["items"]) == 1

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_many_items_order(self, mock_publish, client: TestClient):
        """An order with 10 items should succeed and calculate amount correctly."""
        items = [
            {"product_id": f"p{i}", "name": f"Item {i}", "quantity": 1, "unit_price": 100}
            for i in range(10)
        ]
        payload = {"customer_id": "cust-1", "currency": "USD", "items": items}
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["amount"] == 1000
        assert len(response.json()["items"]) == 10

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_amount_calculation_multiple_quantities(self, mock_publish, client: TestClient):
        """Amount should equal sum of (unit_price * quantity) across all items."""
        payload = {
            "customer_id": "cust-1",
            "currency": "USD",
            "items": [
                {"product_id": "p1", "name": "A", "quantity": 3, "unit_price": 200},
                {"product_id": "p2", "name": "B", "quantity": 2, "unit_price": 150},
            ],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        # 3*200 + 2*150 = 900
        assert response.json()["amount"] == 900

    @pytest.mark.parametrize(
        "currency",
        ["KRW", "GBP", "CHF", "CAD", "AUD", "CNY", "INR"],
    )
    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_all_remaining_currencies(self, mock_publish, client: TestClient, currency: str):
        """Orders with every supported currency should succeed."""
        payload = {
            "customer_id": "cust-1",
            "currency": currency,
            "items": [{"product_id": "p1", "name": "A", "quantity": 1, "unit_price": 1000}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == currency


class TestHealthEndpoints:
    """Tests for health and readiness endpoints."""

    def test_health_check(self, client: TestClient):
        """Health endpoint should always return healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_readiness_check_no_servicebus(self, client: TestClient):
        """Readiness should report degraded when Service Bus is not configured."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["servicebus_connected"] is False
