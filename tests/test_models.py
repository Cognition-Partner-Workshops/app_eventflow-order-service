"""Tests for Pydantic models and validation logic."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    ZERO_DECIMAL_CURRENCIES,
    CreateOrderRequest,
    Currency,
    OrderCreatedEvent,
    OrderEventData,
    OrderItem,
    OrderResponse,
)


class TestCurrencyEnum:
    """Tests for the Currency enum."""

    def test_all_currency_values(self):
        """All expected currency codes should be valid enum members."""
        expected = {"USD", "EUR", "GBP", "JPY", "KRW", "CHF", "CAD", "AUD", "CNY", "INR"}
        actual = {c.value for c in Currency}
        assert actual == expected

    def test_currency_is_string_enum(self):
        """Currency members should be usable as strings."""
        assert Currency.USD == "USD"
        assert Currency.JPY == "JPY"


class TestZeroDecimalCurrencies:
    """Tests for the ZERO_DECIMAL_CURRENCIES constant."""

    def test_contains_jpy(self):
        assert "JPY" in ZERO_DECIMAL_CURRENCIES

    def test_contains_krw(self):
        assert "KRW" in ZERO_DECIMAL_CURRENCIES

    def test_does_not_contain_usd(self):
        assert "USD" not in ZERO_DECIMAL_CURRENCIES

    def test_is_a_set(self):
        assert isinstance(ZERO_DECIMAL_CURRENCIES, set)


class TestOrderItem:
    """Tests for OrderItem validation."""

    def test_valid_item(self):
        item = OrderItem(product_id="p1", name="Widget", quantity=3, unit_price=500)
        assert item.product_id == "p1"
        assert item.quantity == 3
        assert item.unit_price == 500

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Widget", quantity=0, unit_price=500)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Widget", quantity=-1, unit_price=500)

    def test_zero_unit_price_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Widget", quantity=1, unit_price=0)

    def test_negative_unit_price_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", name="Widget", quantity=1, unit_price=-100)

    def test_missing_product_id(self):
        with pytest.raises(ValidationError):
            OrderItem(name="Widget", quantity=1, unit_price=100)

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            OrderItem(product_id="p1", quantity=1, unit_price=100)


class TestCreateOrderRequest:
    """Tests for CreateOrderRequest validation."""

    def test_valid_request_usd(self):
        req = CreateOrderRequest(
            customer_id="cust-1",
            currency=Currency.USD,
            items=[OrderItem(product_id="p1", name="A", quantity=1, unit_price=100)],
        )
        assert req.currency == Currency.USD

    @pytest.mark.parametrize("currency", list(Currency))
    def test_all_supported_currencies(self, currency: Currency):
        """CreateOrderRequest should accept every Currency enum value."""
        req = CreateOrderRequest(
            customer_id="cust-1",
            currency=currency,
            items=[OrderItem(product_id="p1", name="A", quantity=1, unit_price=100)],
        )
        assert req.currency == currency

    def test_empty_items_rejected(self):
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                customer_id="cust-1",
                currency=Currency.USD,
                items=[],
            )

    def test_missing_customer_id(self):
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                currency=Currency.USD,
                items=[OrderItem(product_id="p1", name="A", quantity=1, unit_price=100)],
            )


class TestOrderCreatedEvent:
    """Tests for OrderCreatedEvent default field generation."""

    def test_default_event_id_is_uuid(self):
        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="o1",
                customer_id="c1",
                currency="USD",
                amount=100,
                items=[],
            )
        )
        # Should be a valid UUID string
        uuid.UUID(event.event_id)

    def test_default_event_type(self):
        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="o1",
                customer_id="c1",
                currency="USD",
                amount=100,
                items=[],
            )
        )
        assert event.event_type == "OrderCreated"

    def test_default_timestamp(self):
        before = datetime.now(UTC)
        event = OrderCreatedEvent(
            data=OrderEventData(
                order_id="o1",
                customer_id="c1",
                currency="USD",
                amount=100,
                items=[],
            )
        )
        after = datetime.now(UTC)
        assert before <= event.timestamp <= after

    def test_unique_event_ids(self):
        data = OrderEventData(
            order_id="o1", customer_id="c1", currency="USD", amount=100, items=[]
        )
        e1 = OrderCreatedEvent(data=data)
        e2 = OrderCreatedEvent(data=data)
        assert e1.event_id != e2.event_id


class TestOrderResponse:
    """Tests for OrderResponse model."""

    def test_valid_response(self):
        resp = OrderResponse(
            order_id="o1",
            customer_id="c1",
            currency="USD",
            amount=5000,
            items=[],
            status="pending",
            created_at=datetime.now(UTC),
        )
        assert resp.order_id == "o1"
        assert resp.status == "pending"
