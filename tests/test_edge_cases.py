"""Edge case tests for order creation."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestOrderEdgeCases:
    """Edge case tests for order creation and validation."""

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_with_single_item(self, mock_publish, client: TestClient):
        """Should successfully create an order with exactly one item."""
        payload = {
            "customer_id": "cust-single",
            "currency": "USD",
            "items": [
                {
                    "product_id": "prod-solo",
                    "name": "Solo Product",
                    "quantity": 1,
                    "unit_price": 999,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 999
        assert len(data["items"]) == 1

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_with_many_items(self, mock_publish, client: TestClient):
        """Should successfully create an order with many line items."""
        items = [
            {
                "product_id": f"prod-{i}",
                "name": f"Product {i}",
                "quantity": 1,
                "unit_price": 100,
            }
            for i in range(20)
        ]
        payload = {
            "customer_id": "cust-bulk",
            "currency": "USD",
            "items": items,
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 2000  # 20 items * 100
        assert len(data["items"]) == 20

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_gbp_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with GBP currency."""
        payload = {
            "customer_id": "cust-uk",
            "currency": "GBP",
            "items": [
                {
                    "product_id": "prod-uk-1",
                    "name": "Tea Set",
                    "quantity": 1,
                    "unit_price": 3499,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "GBP"
        assert data["amount"] == 3499

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_krw_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with KRW (zero-decimal currency)."""
        payload = {
            "customer_id": "cust-kr",
            "currency": "KRW",
            "items": [
                {
                    "product_id": "prod-kr-1",
                    "name": "K-Pop Album",
                    "quantity": 3,
                    "unit_price": 18000,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "KRW"
        assert data["amount"] == 54000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_chf_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with CHF currency."""
        payload = {
            "customer_id": "cust-ch",
            "currency": "CHF",
            "items": [
                {
                    "product_id": "prod-ch-1",
                    "name": "Swiss Watch",
                    "quantity": 1,
                    "unit_price": 250000,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "CHF"
        assert data["amount"] == 250000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_cad_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with CAD currency."""
        payload = {
            "customer_id": "cust-ca",
            "currency": "CAD",
            "items": [
                {
                    "product_id": "prod-ca-1",
                    "name": "Maple Syrup",
                    "quantity": 5,
                    "unit_price": 1299,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "CAD"
        assert data["amount"] == 6495

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_aud_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with AUD currency."""
        payload = {
            "customer_id": "cust-au",
            "currency": "AUD",
            "items": [
                {
                    "product_id": "prod-au-1",
                    "name": "Boomerang",
                    "quantity": 2,
                    "unit_price": 4500,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "AUD"
        assert data["amount"] == 9000

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_cny_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with CNY currency."""
        payload = {
            "customer_id": "cust-cn",
            "currency": "CNY",
            "items": [
                {
                    "product_id": "prod-cn-1",
                    "name": "Silk Scarf",
                    "quantity": 1,
                    "unit_price": 28800,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "CNY"
        assert data["amount"] == 28800

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_inr_currency(self, mock_publish, client: TestClient):
        """Should successfully create an order with INR currency."""
        payload = {
            "customer_id": "cust-in",
            "currency": "INR",
            "items": [
                {
                    "product_id": "prod-in-1",
                    "name": "Spice Box",
                    "quantity": 4,
                    "unit_price": 75000,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "INR"
        assert data["amount"] == 300000

    def test_order_zero_unit_price(self, client: TestClient):
        """Should reject an order with zero unit_price (gt=0 validation)."""
        payload = {
            "customer_id": "cust-free",
            "currency": "USD",
            "items": [
                {
                    "product_id": "prod-free",
                    "name": "Free Sample",
                    "quantity": 1,
                    "unit_price": 0,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 422

    def test_order_zero_quantity(self, client: TestClient):
        """Should reject an order with zero quantity (gt=0 validation)."""
        payload = {
            "customer_id": "cust-zero",
            "currency": "USD",
            "items": [
                {
                    "product_id": "prod-zero",
                    "name": "Zero Qty Item",
                    "quantity": 0,
                    "unit_price": 500,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 422

    @patch("app.routers.orders.publish_order_created", new_callable=AsyncMock, return_value=True)
    def test_order_large_quantity(self, mock_publish, client: TestClient):
        """Should handle large quantity values correctly."""
        payload = {
            "customer_id": "cust-large",
            "currency": "USD",
            "items": [
                {
                    "product_id": "prod-large",
                    "name": "Bulk Item",
                    "quantity": 10000,
                    "unit_price": 1,
                }
            ],
        }

        response = client.post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 10000
