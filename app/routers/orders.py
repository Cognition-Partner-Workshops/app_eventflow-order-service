"""Order API endpoints.

Provides CRUD operations for orders and publishes ``OrderCreated`` events
to Azure Service Bus for downstream processing by the payment service.

All monetary values are expressed in the smallest currency unit
(e.g. cents for USD, yen for JPY).
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

# In-memory store — sufficient for demos; swap with a database for production.
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

    # Publish event to Service Bus for downstream processing
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
    """Request body for updating order status."""
    status: str = Field(..., description="New order status")


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
)
async def update_order_status(order_id: str, request: UpdateOrderStatusRequest) -> OrderResponse:
    """Update the status of an order (called by payment service after processing)."""
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
    """List the most recent orders, sorted newest-first.

    Args:
        limit: Maximum number of orders to return (default 50).
    """
    orders = list(_orders.values())
    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders[:limit]
