"""Tests for the FastAPI application lifespan and main module."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class TestLifespan:
    """Tests for the application lifespan context manager."""

    def test_lifespan_calls_close_servicebus_client_on_shutdown(self):
        """Should call close_servicebus_client when the application shuts down."""
        with patch("app.main.close_servicebus_client") as mock_close:
            with TestClient(app):
                pass
            mock_close.assert_called_once()
