"""Azure Service Bus event publisher."""

import json
import logging

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError

from app.config import settings
from app.models import OrderCreatedEvent

logger = logging.getLogger(__name__)

_client: ServiceBusClient | None = None
_sender = None


def get_servicebus_client() -> ServiceBusClient | None:
    """Get or create the Service Bus client singleton."""
    global _client
    if _client is None and settings.azure_servicebus_connection_string:
        try:
            _client = ServiceBusClient.from_connection_string(
                settings.azure_servicebus_connection_string
            )
            logger.info("Service Bus client initialized")
        except Exception:
            logger.exception("Failed to initialize Service Bus client")
            _client = None
    return _client


async def publish_order_created(event: OrderCreatedEvent) -> bool:
    """Publish an OrderCreated event to Azure Service Bus.

    Args:
        event: The order created event to publish.

    Returns:
        True if the event was published successfully, False otherwise.
    """
    client = get_servicebus_client()
    if client is None:
        logger.warning(
            "Service Bus client not available — event will not be published",
            extra={"event_id": event.event_id},
        )
        return False

    try:
        sender = client.get_queue_sender(queue_name=settings.azure_servicebus_queue_name)
        message_body = json.dumps(event.model_dump(), default=str)
        message = ServiceBusMessage(
            body=message_body,
            content_type="application/json",
            subject=event.event_type,
            application_properties={
                "event_type": event.event_type,
                "event_id": event.event_id,
                "currency": event.data.currency,
                "order_id": event.data.order_id,
            },
        )

        with sender:
            sender.send_messages(message)

        logger.info(
            "Published OrderCreated event",
            extra={
                "event_id": event.event_id,
                "order_id": event.data.order_id,
                "currency": event.data.currency,
                "amount": event.data.amount,
            },
        )
        return True

    except ServiceBusError:
        logger.exception(
            "Failed to publish event to Service Bus",
            extra={"event_id": event.event_id},
        )
        return False


async def check_servicebus_health() -> bool:
    """Check if Service Bus connection is healthy."""
    client = get_servicebus_client()
    if client is None:
        return False
    try:
        receiver = client.get_queue_receiver(
            queue_name=settings.azure_servicebus_queue_name,
            max_wait_time=1,
        )
        with receiver:
            # Just opening the receiver validates connectivity
            pass
        return True
    except ServiceBusError:
        logger.exception("Service Bus health check failed")
        return False


def close_servicebus_client() -> None:
    """Close the Service Bus client."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            logger.exception("Error closing Service Bus client")
        finally:
            _client = None
