"""Pydantic models for orders and events.

Defines the data structures used for API request/response validation and for the
``OrderCreated`` events published to Azure Service Bus. All monetary values are
represented as integers in the smallest currency unit (e.g., cents for USD, yen
for JPY) to avoid floating-point precision issues.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Currency(str, Enum):
    """Supported ISO 4217 currency codes.

    Zero-decimal currencies (JPY, KRW) are tracked in ``ZERO_DECIMAL_CURRENCIES``.
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


#: Currencies where the smallest unit is the base unit (no fractional cents).
#: For these currencies, an amount of ``15800`` means 15,800 JPY, not 158.00.
ZERO_DECIMAL_CURRENCIES: set[str] = {"JPY", "KRW"}


class OrderItem(BaseModel):
    """A single line item in an order.

    Attributes:
        product_id: Unique product identifier.
        name: Human-readable product name.
        quantity: Number of units ordered (must be > 0).
        unit_price: Price per unit in the smallest currency unit (must be > 0).
    """

    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price: int = Field(..., gt=0, description="Price per unit in smallest currency unit")


class CreateOrderRequest(BaseModel):
    """Request body for ``POST /api/orders``.

    Attributes:
        customer_id: Identifier of the customer placing the order.
        currency: ISO 4217 currency code from the ``Currency`` enum.
        items: One or more line items (at least one required).
    """

    customer_id: str = Field(..., description="Customer identifier")
    currency: Currency = Field(..., description="ISO 4217 currency code")
    items: list[OrderItem] = Field(..., min_length=1, description="Order items")


class OrderResponse(BaseModel):
    """Response body returned for all order endpoints.

    Attributes:
        order_id: Unique identifier assigned on creation (UUID).
        customer_id: Identifier of the customer who placed the order.
        currency: ISO 4217 currency code.
        amount: Total amount in the smallest currency unit, computed as the sum
            of ``unit_price * quantity`` for each item.
        items: The line items in the order.
        status: Current order status (e.g., ``pending``, ``paid``).
        created_at: UTC timestamp of when the order was created.
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

    Attributes:
        event_id: Unique event identifier (auto-generated UUID).
        event_type: Always ``"OrderCreated"``.
        timestamp: UTC timestamp of when the event was generated.
        data: The order data payload.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="OrderCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: "OrderEventData"


class OrderEventData(BaseModel):
    """Data payload nested inside an ``OrderCreatedEvent``.

    Attributes:
        order_id: Unique order identifier.
        customer_id: Identifier of the customer who placed the order.
        currency: ISO 4217 currency code.
        amount: Total amount in the smallest currency unit.
        items: The line items in the order.
    """

    order_id: str
    customer_id: str
    currency: str
    amount: int
    items: list[OrderItem]
