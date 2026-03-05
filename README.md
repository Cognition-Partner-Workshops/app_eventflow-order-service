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

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/orders` | Create a new order |
| `GET` | `/api/orders/{order_id}` | Get order by ID |
| `GET` | `/api/orders` | List recent orders |
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
