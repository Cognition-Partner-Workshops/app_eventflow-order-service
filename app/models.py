"""Pydantic models for orders and events."""

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Currency(str, Enum):
    """Supported currencies with their decimal place counts."""

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


# Currencies that have zero decimal places (amount is already in the base unit)
ZERO_DECIMAL_CURRENCIES: set[str] = {"JPY", "KRW"}


class OrderItem(BaseModel):
    """A single item in an order."""

    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price: int = Field(..., gt=0, description="Price per unit in smallest currency unit")


class CreateOrderRequest(BaseModel):
    """Request body for creating a new order."""

    customer_id: str = Field(..., description="Customer identifier")
    currency: Currency = Field(..., description="ISO 4217 currency code")
    items: list[OrderItem] = Field(..., min_length=1, description="Order items")


class OrderResponse(BaseModel):
    """Response body for an order."""

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Customer identifier")
    currency: str = Field(..., description="ISO 4217 currency code")
    amount: int = Field(..., description="Total amount in smallest currency unit")
    items: list[OrderItem] = Field(..., description="Order items")
    status: str = Field(..., description="Order status")
    created_at: datetime = Field(..., description="Order creation timestamp")


class OrderCreatedEvent(BaseModel):
    """Event published when an order is created."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="OrderCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: "OrderEventData"


class OrderEventData(BaseModel):
    """Data payload of the OrderCreated event."""

    order_id: str
    customer_id: str
    currency: str
    amount: int
    items: list[OrderItem]
