"""Order API endpoints.

Implements CRUD-style operations for orders.  Created orders are persisted in
an in-memory dictionary (suitable for demos) and an ``OrderCreated`` event is
published to Azure Service Bus so downstream services can react.
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

# In-memory order store keyed by ``order_id``.  Suitable for single-instance
# demos; a real deployment would use a persistent database.
_orders: dict[str, OrderResponse] = {}


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
)
async def create_order(request: CreateOrderRequest) -> OrderResponse:
    """Create a new order and publish an OrderCreated event.

    The total ``amount`` is calculated as the sum of ``unit_price * quantity``
    for every item in the request.  All monetary values are in the smallest
    currency unit (e.g. cents for USD, yen for JPY).

    If the event cannot be published to Service Bus the order is still
    persisted locally but downstream services will **not** be notified.
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

    _orders[order_id] = order  # persist before publishing to avoid data loss

    logger.info(
        "Order created",
        extra={
            "order_id": order_id,
            "customer_id": request.customer_id,
            "currency": request.currency.value,
            "amount": total_amount,
        },
    )

    # Publish event to Service Bus so the Payment Service can initiate a charge.
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
        logger.warning(
            "Order created but event not published — downstream services will not process it",
            extra={"order_id": order_id},
        )

    return order


class UpdateOrderStatusRequest(BaseModel):
    """Request body for ``PATCH /api/orders/{order_id}/status``."""

    status: str = Field(..., description="New order status (e.g. 'paid', 'failed')")


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
)
async def update_order_status(order_id: str, request: UpdateOrderStatusRequest) -> OrderResponse:
    """Update the status of an existing order.

    Typically called by the Payment Service callback after a charge has been
    processed (e.g. setting status to ``"paid"`` or ``"failed"``).
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
    """Retrieve a single order by its unique identifier.

    Raises:
        HTTPException: 404 if the order does not exist.
    """
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
    """List the most recent orders, newest first.

    Args:
        limit: Maximum number of orders to return (default 50).
    """
    orders = list(_orders.values())
    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders[:limit]
