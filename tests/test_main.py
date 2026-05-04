"""Tests for the application lifespan and startup/shutdown behavior."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class TestLifespan:
    """Tests for the lifespan context manager."""

    @patch("app.main.close_servicebus_client")
    def test_lifespan_startup_and_shutdown(self, mock_close):
        """The lifespan should log startup, yield, then close the client on shutdown."""
        with TestClient(app):
            pass
        mock_close.assert_called_once()
