"""Pydantic models for orders and events."""

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Currency(str, Enum):
    """Supported currencies."""

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
    VND = "VND"
    BHD = "BHD"
    KWD = "KWD"
    OMR = "OMR"


# ISO 4217 minor-unit exponents keyed by currency code.
# Exponent 0 → amount is already in the base unit (e.g. JPY, KRW).
# Exponent 2 → 100 minor units per base unit (e.g. USD, EUR).
# Exponent 3 → 1000 minor units per base unit (e.g. BHD, KWD, OMR).
CURRENCY_EXPONENTS: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CHF": 2,
    "CAD": 2,
    "AUD": 2,
    "CNY": 2,
    "INR": 2,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
}

# Convenience set retained for backwards compatibility.
ZERO_DECIMAL_CURRENCIES: set[str] = {
    code for code, exp in CURRENCY_EXPONENTS.items() if exp == 0
}


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
