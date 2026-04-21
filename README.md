# EventFlow Order Service

**System 1** in the EventFlow event-driven architecture demo.

A FastAPI service that accepts customer orders via REST API and publishes `OrderCreated` events to Azure Service Bus for downstream processing.

## Architecture Role

```
User → [Order Service] → Azure Service Bus → [Payment Service]
              ↓
       Application Insights
```

## Features

- REST API for order creation and retrieval
- Event publishing to Azure Service Bus
- International currency support (USD, EUR, GBP, JPY, etc.)
- Health check and readiness endpoints
- Structured logging with correlation IDs
- OpenTelemetry instrumentation for Azure Monitor

## Tech Stack

- Python 3.11+
- FastAPI
- Azure Service Bus SDK
- OpenTelemetry + Azure Monitor
- Pydantic v2 for data validation

## Local Development

```bash
# Install dependencies
pip install poetry
poetry install

# Set environment variables
cp .env.example .env
# Edit .env with your values

# Run the service
poetry run uvicorn app.main:app --reload --port 8001

# Run tests
poetry run pytest -v
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AZURE_SERVICEBUS_CONNECTION_STRING` | Service Bus connection string | *(required)* |
| `AZURE_SERVICEBUS_QUEUE_NAME` | Queue name for order events | `order-events` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection string | *(optional)* |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Deployment environment | `development` |

## Testing

```bash
# Run all tests
poetry run pytest -v --tb=short

# Run linter
poetry run ruff check app/ tests/
```

### Test Coverage (54 tests)

| Test File | Class | Tests | Description |
|---|---|---|---|
| `test_orders.py` | `TestCreateOrder` | 7 | USD/EUR/JPY creation, empty items, invalid currency, negative quantity, publish failure |
| `test_orders.py` | `TestGetOrder` | 2 | Get existing order, get nonexistent order (404) |
| `test_orders.py` | `TestUpdateOrderStatus` | 3 | Successful update, nonexistent order (404), multiple status updates |
| `test_orders.py` | `TestListOrders` | 3 | List orders, limit parameter, reverse chronological ordering |
| `test_orders.py` | `TestCreateOrderAdditionalCurrencies` | 7 | GBP, KRW, CHF, CAD, AUD, CNY, INR order creation |
| `test_orders.py` | `TestCreateOrderEdgeCases` | 3 | Single item, UUID format validation, timestamp check |
| `test_orders.py` | `TestHealthEndpoints` | 2 | Health check, readiness check (no Service Bus) |
| `test_events.py` | `TestPublishOrderCreated` | 2 | Publish when client is None, ServiceBusError handling |
| `test_events.py` | `TestCheckServicebusHealth` | 1 | Health check returns false when client is None |
| `test_events.py` | `TestCloseServicebusClient` | 2 | Close when client is None, close when client.close() raises |
| `test_events.py` | `TestGetServicebusClient` | 2 | Empty connection string, from_connection_string raises |
| `test_models.py` | `TestOrderItemValidation` | 3 | Zero quantity rejected, zero unit_price rejected, valid item |
| `test_models.py` | `TestCreateOrderRequestValidation` | 4 | Valid serialization, missing customer_id/currency/items |
| `test_models.py` | `TestCurrencyEnum` | 2 | All 10 values valid, invalid value rejected |
| `test_models.py` | `TestOrderCreatedEvent` | 2 | Default event_id is UUID, default event_type is "OrderCreated" |
| `test_models.py` | `TestOrderResponse` | 1 | All fields present after construction |
| `test_config.py` | `TestSettingsDefaults` | 7 | Default values for all settings fields |
| `test_config.py` | `TestSettingsFromEnv` | 1 | Settings loaded from environment variables |

All Azure Service Bus interactions are mocked — no real Azure calls are made during testing.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/orders` | Create a new order |
| `GET` | `/api/orders/{order_id}` | Get order by ID |
| `PATCH` | `/api/orders/{order_id}/status` | Update order status |
| `GET` | `/api/orders` | List recent orders (supports `?limit=N`) |
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check (verifies Service Bus connectivity) |

## Event Schema

Published to Azure Service Bus as JSON:

```json
{
  "event_id": "uuid",
  "event_type": "OrderCreated",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": {
    "order_id": "uuid",
    "customer_id": "cust-123",
    "currency": "USD",
    "amount": 4999,
    "items": [
      {
        "product_id": "prod-456",
        "name": "Widget",
        "quantity": 2,
        "unit_price": 2499
      }
    ]
  }
}
```

**Note:** `amount` is always in the smallest currency unit (cents for USD/EUR, yen for JPY). The downstream Payment Service is responsible for interpreting the amount based on the currency's decimal places.

## Docker

```bash
docker build -t eventflow-order-service .
docker run -p 8001:8001 --env-file .env eventflow-order-service
```
