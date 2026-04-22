"""Tests for Azure Service Bus event publisher."""

import json
from unittest.mock import MagicMock, patch

import pytest
from azure.servicebus.exceptions import ServiceBusError

from app.models import OrderCreatedEvent, OrderEventData, OrderItem


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the global _client before each test."""
    with patch("app.events._client", None):
        yield


def _make_event() -> OrderCreatedEvent:
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

    def test_returns_none_when_connection_string_empty(self):
        """Should return None when connection string is empty (default)."""
        with patch("app.events.settings") as mock_settings:
            mock_settings.azure_servicebus_connection_string = ""
            from app.events import get_servicebus_client

            result = get_servicebus_client()
            assert result is None

    def test_creates_client_when_connection_string_set(self):
        """Should create a ServiceBusClient when connection string is configured."""
        mock_client = MagicMock()
        with (
            patch("app.events.settings") as mock_settings,
            patch("app.events.ServiceBusClient") as mock_sbc,
        ):
            mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=abc123="
            mock_sbc.from_connection_string.return_value = mock_client

            from app.events import get_servicebus_client

            result = get_servicebus_client()
            assert result is mock_client
            mock_sbc.from_connection_string.assert_called_once_with(
                "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=abc123="
            )

    def test_returns_existing_client_on_subsequent_calls(self):
        """Should return the same client (singleton) on subsequent calls."""
        mock_client = MagicMock()
        with patch("app.events._client", mock_client):
            from app.events import get_servicebus_client

            result = get_servicebus_client()
            assert result is mock_client

    def test_returns_none_when_client_creation_throws(self):
        """Should return None when ServiceBusClient creation raises an exception."""
        with (
            patch("app.events.settings") as mock_settings,
            patch("app.events.ServiceBusClient") as mock_sbc,
        ):
            mock_settings.azure_servicebus_connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=abc123="
            mock_sbc.from_connection_string.side_effect = Exception("Connection failed")

            from app.events import get_servicebus_client

            result = get_servicebus_client()
            assert result is None


class TestPublishOrderCreated:
    """Tests for publish_order_created()."""

    @pytest.mark.asyncio
    async def test_returns_false_when_client_is_none(self):
        """Should return False when no Service Bus client is available."""
        with patch("app.events.get_servicebus_client", return_value=None):
            from app.events import publish_order_created

            event = _make_event()
            result = await publish_order_created(event)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_publish(self):
        """Should return True when the event is published successfully."""
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("app.events.get_servicebus_client", return_value=mock_client):
            from app.events import publish_order_created

            event = _make_event()
            result = await publish_order_created(event)
            assert result is True
            mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_servicebus_error(self):
        """Should return False when ServiceBusError is raised during send."""
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_sender.send_messages.side_effect = ServiceBusError("Send failed")
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("app.events.get_servicebus_client", return_value=mock_client):
            from app.events import publish_order_created

            event = _make_event()
            result = await publish_order_created(event)
            assert result is False

    @pytest.mark.asyncio
    async def test_message_body_contains_correct_json(self):
        """Should send a message with correct JSON body and properties."""
        mock_client = MagicMock()
        mock_sender = MagicMock()
        mock_sender.__enter__ = MagicMock(return_value=mock_sender)
        mock_sender.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_sender.return_value = mock_sender

        with (
            patch("app.events.get_servicebus_client", return_value=mock_client),
            patch("app.events.ServiceBusMessage") as mock_msg_cls,
        ):
            mock_msg_cls.return_value = MagicMock()

            from app.events import publish_order_created

            event = _make_event()
            await publish_order_created(event)

            call_kwargs = mock_msg_cls.call_args[1]
            body = json.loads(call_kwargs["body"])
            assert body["data"]["order_id"] == "order-123"
            assert body["data"]["currency"] == "USD"
            assert body["data"]["amount"] == 5000
            assert call_kwargs["content_type"] == "application/json"
            assert call_kwargs["subject"] == "OrderCreated"
            props = call_kwargs["application_properties"]
            assert props["event_type"] == "OrderCreated"
            assert props["order_id"] == "order-123"
            assert props["currency"] == "USD"


class TestCheckServicebusHealth:
    """Tests for check_servicebus_health()."""

    @pytest.mark.asyncio
    async def test_returns_false_when_client_is_none(self):
        """Should return False when no client is available."""
        with patch("app.events.get_servicebus_client", return_value=None):
            from app.events import check_servicebus_health

            result = await check_servicebus_health()
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_receiver_opens_successfully(self):
        """Should return True when receiver opens without error."""
        mock_client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver

        with patch("app.events.get_servicebus_client", return_value=mock_client):
            from app.events import check_servicebus_health

            result = await check_servicebus_health()
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_servicebus_error(self):
        """Should return False when ServiceBusError occurs."""
        mock_client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(side_effect=ServiceBusError("Connection failed"))
        mock_client.get_queue_receiver.return_value = mock_receiver

        with patch("app.events.get_servicebus_client", return_value=mock_client):
            from app.events import check_servicebus_health

            result = await check_servicebus_health()
            assert result is False


class TestCloseServicebusClient:
    """Tests for close_servicebus_client()."""

    def test_does_nothing_when_client_is_none(self):
        """Should not raise when _client is None."""
        with patch("app.events._client", None):
            from app.events import close_servicebus_client

            close_servicebus_client()

    def test_closes_client_and_sets_to_none(self):
        """Should close the client and reset _client to None."""
        import app.events

        mock_client = MagicMock()
        with patch.object(app.events, "_client", mock_client):
            app.events.close_servicebus_client()
            mock_client.close.assert_called_once()
            assert app.events._client is None

    def test_handles_exception_during_close(self):
        """Should handle exceptions during close gracefully and still reset _client."""
        import app.events

        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close failed")
        with patch.object(app.events, "_client", mock_client):
            app.events.close_servicebus_client()
            mock_client.close.assert_called_once()
            assert app.events._client is None
