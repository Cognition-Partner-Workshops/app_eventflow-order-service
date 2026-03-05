"""Shared test fixtures for the Order Service."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_order_payload() -> dict:
    """A valid order creation payload using USD."""
    return {
        "customer_id": "cust-001",
        "currency": "USD",
        "items": [
            {
                "product_id": "prod-101",
                "name": "Wireless Mouse",
                "quantity": 2,
                "unit_price": 2999,
            },
            {
                "product_id": "prod-102",
                "name": "USB-C Hub",
                "quantity": 1,
                "unit_price": 4999,
            },
        ],
    }


@pytest.fixture
def sample_jpy_order_payload() -> dict:
    """A valid order creation payload using JPY (zero-decimal currency).

    This order passes validation in the Order Service because the Order Service
    correctly treats the amount as the smallest currency unit.
    The downstream Payment Service is responsible for interpreting the currency.
    """
    return {
        "customer_id": "cust-002",
        "currency": "JPY",
        "items": [
            {
                "product_id": "prod-201",
                "name": "Mechanical Keyboard",
                "quantity": 1,
                "unit_price": 15800,
            },
        ],
    }


@pytest.fixture
def sample_eur_order_payload() -> dict:
    """A valid order creation payload using EUR."""
    return {
        "customer_id": "cust-003",
        "currency": "EUR",
        "items": [
            {
                "product_id": "prod-301",
                "name": "Monitor Stand",
                "quantity": 1,
                "unit_price": 8999,
            },
        ],
    }
