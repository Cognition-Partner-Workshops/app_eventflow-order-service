"""Tests for the FastAPI application setup in app/main.py."""

from fastapi.testclient import TestClient


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client: TestClient):
        """Responses should include CORS headers for cross-origin requests."""
        response = client.get(
            "/health",
            headers={"Origin": "http://example.com"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"

    def test_cors_preflight(self, client: TestClient):
        """OPTIONS preflight requests should return appropriate CORS headers."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert "access-control-allow-origin" in response.headers
        assert "POST" in response.headers["access-control-allow-methods"]


class TestRouterInclusion:
    """Tests verifying the orders router is mounted."""

    def test_orders_prefix_exists(self, client: TestClient):
        """The /api/orders prefix should be reachable."""
        response = client.get("/api/orders")
        assert response.status_code == 200

    def test_orders_post_returns_422_without_body(self, client: TestClient):
        """POST /api/orders without a body should return 422, not 404."""
        response = client.post("/api/orders")
        assert response.status_code == 422
