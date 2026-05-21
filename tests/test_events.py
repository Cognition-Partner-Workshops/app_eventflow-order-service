"""Tests for app/events.py — Azure Service Bus event publishing."""

from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError

from app.events import (
    check_servicebus_health,
    close_servicebus_client,
    get_servicebus_client,
    publish_order_created,
)
from app.models import OrderCreatedEvent, OrderEventData, OrderItem


@pytest.fixture
def sample_event() -> OrderCreatedEvent:
    """A valid OrderCreatedEvent for testing."""
    return OrderCreatedEvent(
        data=OrderEventData(
            order_id="order-123",
            customer_id="cust-001",
            currency="USD",
            amount=5000,
            items=[
                OrderItem(
                    product_id="prod-1",
                    name="Widget",
                    quantity=2,
                    unit_price=2500,
                )
            ],
        )
    )


class TestGetServicebusClient:
    """Tests for get_servicebus_client singleton creation."""

    @patch("app.events._client", None)
    @patch("app.events.settings")
    def test_returns_none_when_no_connection_string(self, mock_settings):
        """Should return None when connection string is empty."""
        mock_settings.azure_servicebus_connection_string = ""

        result = get_servicebus_client()

        assert result is None

    @patch("app.events._client", None)
    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_creates_client_when_connection_string_set(
        self, mock_sb_class, mock_settings
    ):
        """Should create and return a ServiceBusClient when connection string is available."""
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=secret"
        mock_client_instance = MagicMock()
        mock_sb_class.from_connection_string.return_value = mock_client_instance

        result = get_servicebus_client()

        assert result is mock_client_instance
        mock_sb_class.from_connection_string.assert_called_once_with(
            mock_settings.azure_servicebus_connection_string
        )

    @patch("app.events._client", None)
    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_returns_none_on_initialization_error(self, mock_sb_class, mock_settings):
        """Should return None and log error if client initialization fails."""
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=secret"
        mock_sb_class.from_connection_string.side_effect = Exception("Connection failed")

        result = get_servicebus_client()

        assert result is None


class TestPublishOrderCreated:
    """Tests for publish_order_created."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_when_client_is_none(
        self, mock_get_client, sample_event
    ):
        """Should return False and log warning when client is None."""
        mock_get_client.return_value = None

        result = await publish_order_created(sample_event)

        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    @patch("app.events.settings")
    async def test_publish_success(self, mock_settings, mock_get_client, sample_event):
        """Should return True when message is sent successfully."""
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        result = await publish_order_created(sample_event)

        assert result is True
        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    @patch("app.events.settings")
    async def test_returns_false_on_servicebus_error(
        self, mock_settings, mock_get_client, sample_event
    ):
        """Should return False when ServiceBusError is raised during send."""
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("Send failed")
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        result = await publish_order_created(sample_event)

        assert result is False


class TestCheckServicebusHealth:
    """Tests for check_servicebus_health."""

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_when_client_is_none(self, mock_get_client):
        """Should return False when no client is available."""
        mock_get_client.return_value = None

        result = await check_servicebus_health()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    @patch("app.events.settings")
    async def test_returns_true_when_healthy(self, mock_settings, mock_get_client):
        """Should return True when receiver can be opened successfully."""
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver
        mock_get_client.return_value = mock_client

        result = await check_servicebus_health()

        assert result is True

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    @patch("app.events.settings")
    async def test_returns_false_on_servicebus_error(
        self, mock_settings, mock_get_client
    ):
        """Should return False when ServiceBusError is raised."""
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(side_effect=ServiceBusError("Unhealthy"))
        mock_client.get_queue_receiver.return_value = mock_receiver
        mock_get_client.return_value = mock_client

        result = await check_servicebus_health()

        assert result is False


class TestCloseServicebusClient:
    """Tests for close_servicebus_client."""

    @patch("app.events._client", None)
    def test_close_when_no_client(self):
        """Should be a no-op when client is None."""
        close_servicebus_client()
        # No exception raised

    @patch("app.events._client")
    def test_close_success(self, mock_client):
        """Should close the client and reset global to None."""
        import app.events

        app.events._client = mock_client

        close_servicebus_client()

        mock_client.close.assert_called_once()
        assert app.events._client is None

    @patch("app.events._client")
    def test_close_with_exception(self, mock_client):
        """Should reset client to None even if close raises an exception."""
        import app.events

        app.events._client = mock_client
        mock_client.close.side_effect = Exception("Close error")

        close_servicebus_client()

        assert app.events._client is None
