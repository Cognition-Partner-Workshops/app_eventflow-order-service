"""Azure Service Bus event publisher.

Provides a thin abstraction over the Azure Service Bus SDK for publishing
domain events.  A module-level singleton client is lazily created on first
use and reused for the lifetime of the process, avoiding the overhead of
re-establishing AMQP connections on every publish call.

The singleton is intentionally module-scoped (rather than injected) to keep
the router layer simple — call ``publish_order_created`` directly without
needing to thread a client through FastAPI's dependency system.
"""

import json
import logging

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError

from app.config import settings
from app.models import OrderCreatedEvent

logger = logging.getLogger(__name__)

# Module-level singleton: lazily initialised by get_servicebus_client().
# Using a singleton avoids opening a new AMQP connection per request while
# still deferring creation until the connection string is actually available.
_client: ServiceBusClient | None = None
_sender = None


def get_servicebus_client() -> ServiceBusClient | None:
    """Get or create the Service Bus client singleton.

    Returns ``None`` when no connection string is configured, allowing the
    application to start in a degraded mode (useful for local development
    without an Azure subscription).
    """
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

        # Serialize the full Pydantic model to JSON; `default=str` handles
        # datetime and UUID fields that aren't natively JSON-serializable.
        message_body = json.dumps(event.model_dump(), default=str)

        # application_properties are Service Bus metadata exposed to consumers
        # *without* deserializing the body — useful for filtering, routing, and
        # dead-letter diagnostics.
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

        # The context manager ensures the sender link is closed promptly,
        # releasing the AMQP session back to the connection pool.
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
    """Check if Service Bus connection is healthy.

    Opens a short-lived receiver to validate end-to-end connectivity
    (authentication, network, queue existence).  Used by the /ready
    endpoint so orchestrators can detect degraded state.
    """
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
    """Close the Service Bus client and release the AMQP connection.

    Called during application shutdown (see ``lifespan`` in main.py).
    Errors are logged but never propagated so shutdown is never blocked.
    """
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            logger.exception("Error closing Service Bus client")
        finally:
            _client = None
