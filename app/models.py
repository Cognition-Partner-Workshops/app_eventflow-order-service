"""Pydantic models for orders and events.

Defines the request/response schemas used by the Order API as well as the
event payloads published to Azure Service Bus.  All monetary values are
represented as integers in the smallest currency unit (e.g. cents for USD,
yen for JPY) to avoid floating-point rounding issues.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Currency(str, Enum):
    """ISO 4217 currency codes accepted by the Order Service.

    Only a curated subset of currencies is supported.  The ``str`` mixin
    allows Pydantic to serialise enum members as plain strings.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    KRW = "KRW"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    CNY = "CNY"
    INR = "INR"


# Currencies whose smallest unit equals the base unit (i.e. zero decimal
# places).  For these currencies the integer amount IS the display amount.
# The downstream Payment Service uses this set when formatting charges.
ZERO_DECIMAL_CURRENCIES: set[str] = {"JPY", "KRW"}


class OrderItem(BaseModel):
    """A single line item within an order.

    ``unit_price`` is always expressed in the smallest currency unit so that
    all arithmetic can be performed with integers.
    """

    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price: int = Field(..., gt=0, description="Price per unit in smallest currency unit")


class CreateOrderRequest(BaseModel):
    """Request body for ``POST /api/orders``.

    The total order amount is computed server-side from the item prices and
    quantities, so it is not included in the request.
    """

    customer_id: str = Field(..., description="Customer identifier")
    currency: Currency = Field(..., description="ISO 4217 currency code")
    items: list[OrderItem] = Field(..., min_length=1, description="Order items")


class OrderResponse(BaseModel):
    """Response body returned by all order endpoints.

    Includes the server-computed ``amount`` (sum of each item's
    ``unit_price * quantity``) and the current ``status``.
    """

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Customer identifier")
    currency: str = Field(..., description="ISO 4217 currency code")
    amount: int = Field(..., description="Total amount in smallest currency unit")
    items: list[OrderItem] = Field(..., description="Order items")
    status: str = Field(..., description="Order status")
    created_at: datetime = Field(..., description="Order creation timestamp")


class OrderCreatedEvent(BaseModel):
    """Event envelope published to Azure Service Bus when an order is created.

    ``event_id`` and ``timestamp`` are auto-generated so callers only need to
    supply the ``data`` payload.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="OrderCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: "OrderEventData"


class OrderEventData(BaseModel):
    """Data payload nested inside an ``OrderCreatedEvent``.

    Contains the information the downstream Payment Service needs to initiate
    a charge: customer, currency, amount, and the ordered items.
    """

    order_id: str
    customer_id: str
    currency: str
    amount: int
    items: list[OrderItem]
