"""Tests for the Azure Service Bus event publisher."""

from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError

import app.events as events_module
from app.events import (
    check_servicebus_health,
    close_servicebus_client,
    get_servicebus_client,
    publish_order_created,
)
from app.models import OrderCreatedEvent, OrderEventData, OrderItem


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the module-level Service Bus client before each test."""
    events_module._client = None
    events_module._sender = None
    yield
    events_module._client = None
    events_module._sender = None


@pytest.fixture
def sample_event() -> OrderCreatedEvent:
    """Create a sample OrderCreatedEvent for testing."""
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
    """Tests for get_servicebus_client()."""

    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_creates_client_when_connection_string_is_set(
        self, mock_sb_class, mock_settings
    ):
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=val"
        mock_client_instance = MagicMock()
        mock_sb_class.from_connection_string.return_value = mock_client_instance

        result = get_servicebus_client()

        assert result is mock_client_instance
        mock_sb_class.from_connection_string.assert_called_once_with(
            "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=key;SharedAccessKey=val"
        )

    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_returns_none_when_connection_string_empty(
        self, mock_sb_class, mock_settings
    ):
        mock_settings.azure_servicebus_connection_string = ""

        result = get_servicebus_client()

        assert result is None
        mock_sb_class.from_connection_string.assert_not_called()

    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_returns_none_on_initialization_failure(
        self, mock_sb_class, mock_settings
    ):
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test/"
        mock_sb_class.from_connection_string.side_effect = Exception("Connection failed")

        result = get_servicebus_client()

        assert result is None

    @patch("app.events.settings")
    @patch("app.events.ServiceBusClient")
    def test_returns_cached_client_on_second_call(
        self, mock_sb_class, mock_settings
    ):
        mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test/"
        mock_client_instance = MagicMock()
        mock_sb_class.from_connection_string.return_value = mock_client_instance

        first = get_servicebus_client()
        second = get_servicebus_client()

        assert first is second
        mock_sb_class.from_connection_string.assert_called_once()


class TestPublishOrderCreated:
    """Tests for publish_order_created()."""

    @pytest.mark.asyncio
    @patch("app.events.settings")
    @patch("app.events.get_servicebus_client")
    async def test_publishes_event_successfully(
        self, mock_get_client, mock_settings, sample_event
    ):
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        result = await publish_order_created(sample_event)

        assert result is True
        mock_client.get_queue_sender.assert_called_once_with(queue_name="order-events")
        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_when_client_unavailable(
        self, mock_get_client, sample_event
    ):
        mock_get_client.return_value = None

        result = await publish_order_created(sample_event)

        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.settings")
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_on_servicebus_error(
        self, mock_get_client, mock_settings, sample_event
    ):
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("Send failed")
        mock_client = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender
        mock_get_client.return_value = mock_client

        result = await publish_order_created(sample_event)

        assert result is False


class TestCheckServicebusHealth:
    """Tests for check_servicebus_health()."""

    @pytest.mark.asyncio
    @patch("app.events.settings")
    @patch("app.events.get_servicebus_client")
    async def test_returns_true_when_healthy(self, mock_get_client, mock_settings):
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.get_queue_receiver.return_value = mock_receiver
        mock_get_client.return_value = mock_client

        result = await check_servicebus_health()

        assert result is True
        mock_client.get_queue_receiver.assert_called_once_with(
            queue_name="order-events",
            max_wait_time=1,
        )

    @pytest.mark.asyncio
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_when_client_unavailable(self, mock_get_client):
        mock_get_client.return_value = None

        result = await check_servicebus_health()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.events.settings")
    @patch("app.events.get_servicebus_client")
    async def test_returns_false_on_servicebus_error(
        self, mock_get_client, mock_settings
    ):
        mock_settings.azure_servicebus_queue_name = "order-events"
        mock_client = MagicMock()
        mock_client.get_queue_receiver.side_effect = ServiceBusError("Health check failed")
        mock_get_client.return_value = mock_client

        result = await check_servicebus_health()

        assert result is False


class TestCloseServicebusClient:
    """Tests for close_servicebus_client()."""

    def test_closes_client_successfully(self):
        mock_client = MagicMock()
        events_module._client = mock_client

        close_servicebus_client()

        mock_client.close.assert_called_once()
        assert events_module._client is None

    def test_sets_client_to_none_on_close_error(self):
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close failed")
        events_module._client = mock_client

        close_servicebus_client()

        assert events_module._client is None

    def test_noop_when_client_is_none(self):
        events_module._client = None

        close_servicebus_client()

        assert events_module._client is None
