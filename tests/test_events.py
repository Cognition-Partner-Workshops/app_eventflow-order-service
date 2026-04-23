"""Tests for Azure Service Bus event publisher."""

from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError

from app.models import OrderCreatedEvent, OrderEventData


def _make_event() -> OrderCreatedEvent:
    """Helper to create a minimal OrderCreatedEvent."""
    return OrderCreatedEvent(
        data=OrderEventData(
            order_id="order-1",
            customer_id="cust-1",
            currency="USD",
            amount=5000,
            items=[],
        )
    )


class TestGetServicebusClient:
    """Tests for get_servicebus_client singleton."""

    @patch("app.events.settings")
    @patch("app.events._client", None)
    def test_returns_none_when_no_connection_string(self, mock_settings):
        mock_settings.azure_servicebus_connection_string = ""
        from app.events import get_servicebus_client

        result = get_servicebus_client()
        assert result is None

    @patch("app.events.ServiceBusClient")
    @patch("app.events.settings")
    @patch("app.events._client", None)
    def test_creates_client_when_connection_string_set(self, mock_settings, mock_sb_class):
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://fake.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=val"
        mock_client_instance = MagicMock()
        mock_sb_class.from_connection_string.return_value = mock_client_instance

        from app.events import get_servicebus_client

        result = get_servicebus_client()
        assert result is mock_client_instance
        mock_sb_class.from_connection_string.assert_called_once()

    @patch("app.events.ServiceBusClient")
    @patch("app.events.settings")
    @patch("app.events._client", None)
    def test_returns_none_on_exception(self, mock_settings, mock_sb_class):
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://fake.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=val"
        mock_sb_class.from_connection_string.side_effect = Exception("Connection failed")

        from app.events import get_servicebus_client

        result = get_servicebus_client()
        assert result is None


class TestPublishOrderCreated:
    """Tests for publish_order_created."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client", return_value=None)
    async def test_returns_false_when_client_is_none(self, mock_get_client):
        from app.events import publish_order_created

        result = await publish_order_created(_make_event())
        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_true_on_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        from app.events import publish_order_created

        result = await publish_order_created(_make_event())
        assert result is True
        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_on_servicebus_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("Send failed")
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        from app.events import publish_order_created

        result = await publish_order_created(_make_event())
        assert result is False


class TestCheckServicebusHealth:
    """Tests for check_servicebus_health."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client", return_value=None)
    async def test_returns_false_when_no_client(self, mock_get_client):
        from app.events import check_servicebus_health

        result = await check_servicebus_health()
        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_true_when_receiver_opens(self, mock_get_client):
        mock_client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver
        mock_get_client.return_value = mock_client

        from app.events import check_servicebus_health

        result = await check_servicebus_health()
        assert result is True

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_on_servicebus_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_queue_receiver.side_effect = ServiceBusError("Health check failed")
        mock_get_client.return_value = mock_client

        from app.events import check_servicebus_health

        result = await check_servicebus_health()
        assert result is False


class TestCloseServicebusClient:
    """Tests for close_servicebus_client."""

    @patch("app.events._client", None)
    def test_close_when_client_is_none(self):
        """Should be a no-op when no client exists."""
        from app.events import close_servicebus_client

        # Should not raise
        close_servicebus_client()

    def test_close_when_client_exists(self):
        import app.events as events_module

        mock_client = MagicMock()
        events_module._client = mock_client
        events_module.close_servicebus_client()
        mock_client.close.assert_called_once()
        assert events_module._client is None

    def test_close_when_close_raises_exception(self):
        import app.events as events_module

        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close failed")
        events_module._client = mock_client
        # Should not raise — exception is caught and logged
        events_module.close_servicebus_client()
        assert events_module._client is None
