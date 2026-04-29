"""Order API endpoints."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.events import publish_order_created
from app.models import (
    CreateOrderRequest,
    OrderCreatedEvent,
    OrderEventData,
    OrderResponse,
)

logger = structlog.stdlib.get_logger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])

# In-memory store for demo purposes
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
        "order_created",
        order_id=order_id,
        customer_id=request.customer_id,
        currency=request.currency.value,
        amount=total_amount,
        item_count=len(request.items),
    )

    from app.metrics import metrics_collector

    if metrics_collector is not None:
        metrics_collector.record_order_created()

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
            "order_event_not_published",
            order_id=order_id,
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
        "order_status_updated",
        order_id=order_id,
        new_status=request.status,
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
