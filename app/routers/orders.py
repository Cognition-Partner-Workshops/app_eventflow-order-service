"""Order API endpoints.

This module implements the REST API for order lifecycle management. Orders are
stored in-memory (suitable for demo / single-instance deployments) and published
as events to Azure Service Bus so downstream services (e.g. payment-service)
can react asynchronously.

Flow:
    1. Client POSTs a new order.
    2. This service persists it, then publishes an OrderCreatedEvent.
    3. The payment service consumes the event, processes payment, and calls
       back via PATCH /{order_id}/status to update the order.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.events import publish_order_created
from app.models import (
    CreateOrderRequest,
    OrderCreatedEvent,
    OrderEventData,
    OrderResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])

# In-memory store keyed by order_id.  Deliberately simple: no persistence
# across restarts.  In production this would be backed by a database, but for
# this event-driven demo the store only needs to survive long enough for the
# payment-service callback to arrive.
_orders: dict[str, OrderResponse] = {}


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
)
async def create_order(request: CreateOrderRequest) -> OrderResponse:
    """Create a new order and publish an OrderCreated event.

    The amount is calculated as the sum of (unit_price * quantity) for all items.
    All monetary values are in the smallest currency unit (cents for USD, yen for JPY).

    Event publishing is best-effort: if Service Bus is unreachable the order is
    still created and returned to the caller, but downstream processing (e.g.
    payment) will not be triggered.  The warning log allows operators to detect
    and reconcile missed events.
    """
    order_id = str(uuid.uuid4())
    total_amount = sum(item.unit_price * item.quantity for item in request.items)

    order = OrderResponse(
        order_id=order_id,
        customer_id=request.customer_id,
        currency=request.currency.value,
        amount=total_amount,
        items=request.items,
        status="pending",
        created_at=datetime.now(UTC),
    )

    _orders[order_id] = order

    logger.info(
        "Order created",
        extra={
            "order_id": order_id,
            "customer_id": request.customer_id,
            "currency": request.currency.value,
            "amount": total_amount,
        },
    )

    # Publish event to Service Bus so the payment-service (and any other
    # subscribers) can begin processing.  The event carries a full snapshot of
    # the order so consumers don't need to call back for details.
    event = OrderCreatedEvent(
        data=OrderEventData(
            order_id=order_id,
            customer_id=request.customer_id,
            currency=request.currency.value,
            amount=total_amount,
            items=request.items,
        )
    )
    published = await publish_order_created(event)
    if not published:
        # Graceful degradation: the order exists in our store but no downstream
        # service will know about it until the event is retried or reconciled.
        logger.warning(
            "Order created but event not published — downstream services will not process it",
            extra={"order_id": order_id},
        )

    return order


class UpdateOrderStatusRequest(BaseModel):
    """Request body for updating order status."""
    status: str = Field(..., description="New order status")


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
)
async def update_order_status(order_id: str, request: UpdateOrderStatusRequest) -> OrderResponse:
    """Update the status of an order.

    This endpoint acts as the callback for the payment-service: after it
    processes payment for an OrderCreatedEvent, it PATCHes the order status
    back here (e.g. "paid", "payment_failed").  This closes the async
    communication loop between the two services.
    """
    order = _orders.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    order.status = request.status
    logger.info(
        "Order %s status updated to %s",
        order_id,
        request.status,
    )
    return order


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
)
async def get_order(order_id: str) -> OrderResponse:
    """Retrieve an order by its ID."""
    order = _orders.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return order


@router.get(
    "",
    response_model=list[OrderResponse],
    summary="List recent orders",
)
async def list_orders(limit: int = 50) -> list[OrderResponse]:
    """List the most recent orders."""
    orders = list(_orders.values())
    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders[:limit]
