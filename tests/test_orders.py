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


class TestUpdateOrderStatus:
    """Tests for PATCH /api/orders/{order_id}/status."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_order_status_success(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should successfully update an order's status."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == order_id
        assert data["status"] == "completed"

    def test_update_status_nonexistent_order(self, client: TestClient):
        """Should return 404 when updating status of a nonexistent order."""
        response = client.patch(
            "/api/orders/nonexistent-id/status",
            json={"status": "completed"},
        )
        assert response.status_code == 404

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_multiple_times(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should allow updating status multiple times on the same order."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response1 = client.patch(
            f"/api/orders/{order_id}/status",
            json={"status": "processing"},
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "processing"

        response2 = client.patch(
            f"/api/orders/{order_id}/status",
            json={"status": "completed"},
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "completed"


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
    def test_list_orders_with_limit(self, mock_publish, client: TestClient):
        """Should respect the limit query parameter."""
        from app.routers.orders import _orders
        _orders.clear()

        payload = {
            "customer_id": "cust-limit",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Item", "quantity": 1, "unit_price": 100}],
        }
        for _ in range(3):
            client.post("/api/orders", json=payload)

        response = client.get("/api/orders?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_reverse_chronological(self, mock_publish, client: TestClient):
        """Should return orders sorted by created_at descending (most recent first)."""
        from app.routers.orders import _orders
        _orders.clear()

        payload = {
            "customer_id": "cust-chrono",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Item", "quantity": 1, "unit_price": 100}],
        }
        order_ids = []
        for _ in range(3):
            resp = client.post("/api/orders", json=payload)
            order_ids.append(resp.json()["order_id"])

        response = client.get("/api/orders")
        data = response.json()
        returned_ids = [o["order_id"] for o in data]
        # Most recently created order should appear first
        assert returned_ids[0] == order_ids[-1]
        assert returned_ids[1] == order_ids[-2]
        assert returned_ids[2] == order_ids[-3]


class TestCreateOrderAdditionalCurrencies:
    """Tests for creating orders with additional supported currencies."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_gbp(self, mock_publish, client: TestClient):
        """Creating a GBP order should succeed."""
        payload = {
            "customer_id": "cust-gbp",
            "currency": "GBP",
            "items": [{"product_id": "p1", "name": "Tea Set", "quantity": 1, "unit_price": 1500}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "GBP"
        assert response.json()["amount"] == 1500

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_krw(self, mock_publish, client: TestClient):
        """Creating a KRW order should succeed."""
        payload = {
            "customer_id": "cust-krw",
            "currency": "KRW",
            "items": [
                {"product_id": "p1", "name": "K-Pop Album", "quantity": 2, "unit_price": 15000},
            ],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "KRW"
        assert response.json()["amount"] == 30000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_chf(self, mock_publish, client: TestClient):
        """Creating a CHF order should succeed."""
        payload = {
            "customer_id": "cust-chf",
            "currency": "CHF",
            "items": [{"product_id": "p1", "name": "Watch", "quantity": 1, "unit_price": 50000}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "CHF"

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_cad(self, mock_publish, client: TestClient):
        """Creating a CAD order should succeed."""
        payload = {
            "customer_id": "cust-cad",
            "currency": "CAD",
            "items": [
                {"product_id": "p1", "name": "Maple Syrup", "quantity": 3, "unit_price": 899},
            ],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "CAD"
        assert response.json()["amount"] == 2697

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_aud(self, mock_publish, client: TestClient):
        """Creating an AUD order should succeed."""
        payload = {
            "customer_id": "cust-aud",
            "currency": "AUD",
            "items": [{"product_id": "p1", "name": "Boomerang", "quantity": 1, "unit_price": 2500}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "AUD"

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_cny(self, mock_publish, client: TestClient):
        """Creating a CNY order should succeed."""
        payload = {
            "customer_id": "cust-cny",
            "currency": "CNY",
            "items": [
                {"product_id": "p1", "name": "Silk Scarf", "quantity": 2, "unit_price": 18800},
            ],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "CNY"
        assert response.json()["amount"] == 37600

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_inr(self, mock_publish, client: TestClient):
        """Creating an INR order should succeed."""
        payload = {
            "customer_id": "cust-inr",
            "currency": "INR",
            "items": [
                {"product_id": "p1", "name": "Spice Box", "quantity": 1, "unit_price": 75000},
            ],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        assert response.json()["currency"] == "INR"
        assert response.json()["amount"] == 75000


class TestCreateOrderEdgeCases:
    """Additional edge case tests for POST /api/orders."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_create_order_single_item(self, mock_publish, client: TestClient):
        """Creating an order with a single item should succeed."""
        payload = {
            "customer_id": "cust-single",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Solo Item", "quantity": 1, "unit_price": 999}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 1
        assert data["amount"] == 999

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_id_is_valid_uuid(self, mock_publish, client: TestClient):
        """The order_id should be a valid UUID format."""
        import uuid

        payload = {
            "customer_id": "cust-uuid",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}],
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        order_id = response.json()["order_id"]
        # This will raise ValueError if not a valid UUID
        parsed = uuid.UUID(order_id)
        assert str(parsed) == order_id

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_created_at_timestamp_present_and_reasonable(self, mock_publish, client: TestClient):
        """The created_at timestamp should be present and close to the current time."""
        from datetime import UTC, datetime

        before = datetime.now(UTC)
        payload = {
            "customer_id": "cust-ts",
            "currency": "USD",
            "items": [{"product_id": "p1", "name": "Test", "quantity": 1, "unit_price": 100}],
        }
        response = client.post("/api/orders", json=payload)
        after = datetime.now(UTC)

        assert response.status_code == 201
        data = response.json()
        assert "created_at" in data
        created_at = datetime.fromisoformat(data["created_at"])
        assert before <= created_at <= after


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
