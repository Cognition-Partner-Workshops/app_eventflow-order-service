"""Tests for the Azure Service Bus event publishing module."""

from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError

from app.models import OrderCreatedEvent, OrderEventData, OrderItem


def _make_event() -> OrderCreatedEvent:
    """Create a sample OrderCreatedEvent for testing."""
    return OrderCreatedEvent(
        data=OrderEventData(
            order_id="order-123",
            customer_id="cust-001",
            currency="USD",
            amount=5000,
            items=[
                OrderItem(product_id="p1", name="Widget", quantity=2, unit_price=2500),
            ],
        )
    )


class TestPublishOrderCreated:
    """Tests for the publish_order_created function."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client", return_value=None)
    async def test_publish_returns_false_when_client_is_none(self, mock_get_client):
        """Should return False when Service Bus client is not available."""
        from app.events import publish_order_created

        result = await publish_order_created(_make_event())
        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_publish_returns_false_on_servicebus_error(self, mock_get_client):
        """Should return False when ServiceBusError is raised during send."""
        from app.events import publish_order_created

        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("Connection failed")
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        result = await publish_order_created(_make_event())
        assert result is False


class TestCheckServicebusHealth:
    """Tests for the check_servicebus_health function."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client", return_value=None)
    async def test_health_returns_false_when_client_is_none(self, mock_get_client):
        """Should return False when connection string is empty / client is None."""
        from app.events import check_servicebus_health

        result = await check_servicebus_health()
        assert result is False


class TestCloseServicebusClient:
    """Tests for the close_servicebus_client function."""

    @patch("app.events._client", None)
    def test_close_when_client_is_none(self):
        """Should not raise an error when client is None."""
        from app.events import close_servicebus_client

        close_servicebus_client()

    @patch("app.events._client", new_callable=lambda: MagicMock)
    def test_close_when_client_close_raises(self, mock_client):
        """Should handle exceptions from client.close() gracefully."""
        import app.events as events_module

        mock_client_instance = MagicMock()
        mock_client_instance.close.side_effect = Exception("Close failed")
        events_module._client = mock_client_instance

        events_module.close_servicebus_client()
        assert events_module._client is None


class TestGetServicebusClient:
    """Tests for the get_servicebus_client function."""

    @patch("app.events._client", None)
    @patch("app.events.settings")
    def test_returns_none_when_connection_string_empty(self, mock_settings):
        """Should return None when connection string is empty."""
        from app.events import get_servicebus_client

        mock_settings.azure_servicebus_connection_string = ""

        result = get_servicebus_client()
        assert result is None

    @patch("app.events._client", None)
    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_returns_none_when_from_connection_string_raises(
        self, mock_sb_class, mock_settings
    ):
        """Should return None when ServiceBusClient.from_connection_string raises."""
        from app.events import get_servicebus_client

        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://fake.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=abc123="
        mock_sb_class.from_connection_string.side_effect = Exception("Auth failed")

        result = get_servicebus_client()
        assert result is None
