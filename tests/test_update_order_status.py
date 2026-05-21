"""Tests for the PATCH /api/orders/{order_id}/status endpoint."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestUpdateOrderStatus:
    """Tests for updating order status."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_success(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should successfully update the status of an existing order."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        response = client.patch(
            f"/api/orders/{order_id}/status",
            json={"status": "paid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == order_id
        assert data["status"] == "paid"

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_update_status_multiple_transitions(
        self, mock_publish, client: TestClient, sample_order_payload: dict
    ):
        """Should allow multiple status transitions on the same order."""
        create_resp = client.post("/api/orders", json=sample_order_payload)
        order_id = create_resp.json()["order_id"]

        client.patch(f"/api/orders/{order_id}/status", json={"status": "paid"})
        response = client.patch(
            f"/api/orders/{order_id}/status", json={"status": "shipped"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "shipped"

    def test_update_status_nonexistent_order(self, client: TestClient):
        """Should return 404 when updating status of a non-existent order."""
        response = client.patch(
            "/api/orders/nonexistent-id/status",
            json={"status": "paid"},
        )

        assert response.status_code == 404
        assert "nonexistent-id" in response.json()["detail"]
