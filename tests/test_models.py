"""Tests for Pydantic model validation."""

import uuid

import pytest
from pydantic import ValidationError

from app.models import (
    CreateOrderRequest,
    Currency,
    OrderCreatedEvent,
    OrderEventData,
    OrderItem,
    OrderResponse,
)


class TestOrderItemValidation:
    """Tests for OrderItem model validation."""

    def test_zero_quantity_rejected(self):
        """OrderItem should reject quantity of 0 (gt=0)."""
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Test", quantity=0, unit_price=100)

    def test_zero_unit_price_rejected(self):
        """OrderItem should reject unit_price of 0 (gt=0)."""
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Test", quantity=1, unit_price=0)

    def test_valid_order_item(self):
        """OrderItem should accept valid positive values."""
        item = OrderItem(product_id="p1", name="Widget", quantity=5, unit_price=999)
        assert item.product_id == "p1"
        assert item.name == "Widget"
        assert item.quantity == 5
        assert item.unit_price == 999


class TestCreateOrderRequestValidation:
    """Tests for CreateOrderRequest model validation."""

    def test_valid_request_serialization(self):
        """A valid CreateOrderRequest should serialize correctly."""
        request = CreateOrderRequest(
            customer_id="cust-001",
            currency=Currency.USD,
            items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=100)],
        )
        assert request.customer_id == "cust-001"
        assert request.currency == Currency.USD
        assert len(request.items) == 1

    def test_missing_customer_id_rejected(self):
        """CreateOrderRequest should reject missing customer_id."""
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                currency=Currency.USD,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=100)],
            )

    def test_missing_currency_rejected(self):
        """CreateOrderRequest should reject missing currency."""
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                customer_id="cust-001",
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=100)],
            )

    def test_missing_items_rejected(self):
        """CreateOrderRequest should reject missing items."""
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                customer_id="cust-001",
                currency=Currency.USD,
            )


class TestCurrencyEnum:
    """Tests for the Currency enum."""

    def test_all_ten_currency_values_valid(self):
        """All 10 supported currency codes should be valid."""
        expected = {"USD", "EUR", "GBP", "JPY", "KRW", "CHF", "CAD", "AUD", "CNY", "INR"}
        actual = {c.value for c in Currency}
        assert actual == expected

    def test_invalid_currency_rejected(self):
        """Invalid currency code should raise ValueError."""
        with pytest.raises(ValueError):
            Currency("XYZ")


class TestOrderCreatedEvent:
    """Tests for OrderCreatedEvent model defaults."""

    def test_default_event_id_is_uuid(self):
        """event_id should default to a valid UUID string."""
        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="o1",
                customer_id="c1",
                currency="USD",
                amount=100,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=100)],
            )
        )
        parsed = uuid.UUID(event.event_id)
        assert str(parsed) == event.event_id

    def test_default_event_type_is_order_created(self):
        """event_type should default to 'OrderCreated'."""
        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="o1",
                customer_id="c1",
                currency="USD",
                amount=100,
                items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=100)],
            )
        )
        assert event.event_type == "OrderCreated"


class TestOrderResponse:
    """Tests for OrderResponse model."""

    def test_all_fields_present(self):
        """OrderResponse should have all required fields after construction."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        response = OrderResponse(
            order_id="order-abc",
            customer_id="cust-001",
            currency="USD",
            amount=5000,
            items=[OrderItem(product_id="p1", name="Test", quantity=1, unit_price=5000)],
            status="pending",
            created_at=now,
        )
        assert response.order_id == "order-abc"
        assert response.customer_id == "cust-001"
        assert response.currency == "USD"
        assert response.amount == 5000
        assert len(response.items) == 1
        assert response.status == "pending"
        assert response.created_at == now
