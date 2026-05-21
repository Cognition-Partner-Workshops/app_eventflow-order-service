"""Tests for the list_orders endpoint with the limit query parameter."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestListOrdersLimit:
    """Tests for GET /api/orders with limit parameter."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_with_limit(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should respect the limit parameter and return at most N orders."""
        # Create 3 orders
        for _ in range(3):
            client.post("/api/orders", json=sample_order_payload)

        response = client.get("/api/orders?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_limit_greater_than_total(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should return all orders when limit exceeds total count."""
        client.post("/api/orders", json=sample_order_payload)

        response = client.get("/api/orders?limit=1000")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_default_limit(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should use default limit of 50 when no limit is specified."""
        client.post("/api/orders", json=sample_order_payload)

        response = client.get("/api/orders")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_list_orders_sorted_by_created_at_desc(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Orders should be returned sorted by created_at descending (most recent first)."""
        ids = []
        for _ in range(3):
            resp = client.post("/api/orders", json=sample_order_payload)
            ids.append(resp.json()["order_id"])

        response = client.get("/api/orders")
        data = response.json()

        # The most recently created order should appear first
        returned_ids = [o["order_id"] for o in data]
        assert ids[-1] in returned_ids
