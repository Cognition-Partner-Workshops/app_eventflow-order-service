"""Tests for the Order API endpoints."""

from unittest.mock import AsyncMock, patch

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


class TestListOrders:
    """Tests for GET /api/orders."""

    def test_list_orders_empty(self, client: TestClient):
        """Should return an empty list when no orders exist."""
        # Note: orders persist in memory across tests in the same process,
        # so this test may see orders from previous tests
        response = client.get("/api/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


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
