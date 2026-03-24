# EventFlow Order Service

**System 1** in the EventFlow event-driven architecture demo.

A FastAPI service that accepts customer orders via REST API and publishes `OrderCreated` events to Azure Service Bus for downstream processing by the Payment Service (System 2).

## Architecture Role

The Order Service is the entry point for the EventFlow pipeline. It receives order requests from clients, validates them, persists them in an in-memory store, and publishes `OrderCreated` events to an Azure Service Bus queue. The downstream **Payment Service** (System 2) subscribes to these events and processes payments accordingly.

```
Client ──▶ [Order Service (System 1)] ──▶ Azure Service Bus ──▶ [Payment Service (System 2)]
                     │
              Application Insights
```

- **Order Service** is responsible for order creation, validation, and event publishing.
- **Payment Service** is responsible for interpreting the order amount based on the currency's decimal places and processing the payment.

## Features

- REST API for order creation, retrieval, listing, and status updates
- Event publishing to Azure Service Bus (`OrderCreated` events)
- International currency support (USD, EUR, GBP, JPY, KRW, CHF, CAD, AUD, CNY, INR)
- Health check (`/health`) and readiness (`/ready`) endpoints
- Structured logging with correlation IDs
- OpenTelemetry instrumentation for Azure Monitor
- Pydantic v2 request/response validation

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async web framework
- **Azure Service Bus SDK** — event publishing
- **OpenTelemetry + Azure Monitor** — distributed tracing and telemetry
- **Pydantic v2 / pydantic-settings** — data validation and configuration
- **structlog** — structured logging
- **Poetry** — dependency management
- **Ruff** — linting and formatting
- **pytest** — testing

## Project Structure

```
app/
├── __init__.py
├── main.py            # FastAPI entry point: lifespan management, CORS middleware,
│                      #   health and readiness endpoints
├── config.py          # Pydantic Settings for loading configuration from
│                      #   environment variables and .env files
├── models.py          # Pydantic models: Currency enum, OrderItem,
│                      #   CreateOrderRequest, OrderResponse, OrderCreatedEvent,
│                      #   OrderEventData
├── events.py          # Azure Service Bus client singleton, event publishing
│                      #   (publish_order_created), and health checks
└── routers/
    ├── __init__.py
    └── orders.py      # Order CRUD endpoints with in-memory store;
                       #   publishes OrderCreated events on order creation

tests/
├── __init__.py
├── conftest.py        # Shared pytest fixtures: TestClient, sample order
│                      #   payloads (USD, EUR, JPY)
└── test_orders.py     # Tests for order creation, retrieval, listing,
                       #   validation, and health endpoints
```

## Local Development

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management

### Setup

```bash
# Install Poetry (if not already installed)
pip install poetry

# Install all dependencies (including dev dependencies)
poetry install

# Copy the example environment file and fill in your values
cp .env.example .env
# Edit .env with your Azure Service Bus and Application Insights connection strings
```

### Running the Service

```bash
# Start the development server with auto-reload
poetry run uvicorn app.main:app --reload --port 8001
```

The API will be available at `http://localhost:8001`. Interactive API docs are served at `http://localhost:8001/docs` (Swagger UI) and `http://localhost:8001/redoc` (ReDoc).

> **Note:** The service will start even without a valid Azure Service Bus connection string, but event publishing will be disabled and the `/ready` endpoint will report `degraded` status.

## Configuration

Configuration is managed by `pydantic-settings` via the `Settings` class in `app/config.py`. Values are loaded in this priority order (highest wins):

1. **Environment variables** — set directly in the shell or container
2. **`.env` file** — loaded automatically from the project root (see `.env.example`)
3. **Defaults** — defined in the `Settings` class

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AZURE_SERVICEBUS_CONNECTION_STRING` | Azure Service Bus connection string | `""` *(empty — event publishing disabled)* |
| `AZURE_SERVICEBUS_QUEUE_NAME` | Queue name for order events | `order-events` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Application Insights connection string | `""` *(optional — telemetry disabled)* |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` |
| `ENVIRONMENT` | Deployment environment label (e.g., `development`, `production`) | `development` |
| `SERVICE_NAME` | Service name used in logs and health checks | `eventflow-order-service` |
| `SERVICE_VERSION` | Service version reported in API metadata | `1.0.0` |

## API Endpoints

### `POST /api/orders` — Create a New Order

Creates an order, stores it in memory, and publishes an `OrderCreated` event to Azure Service Bus.

**Request:**

```json
{
  "customer_id": "cust-001",
  "currency": "USD",
  "items": [
    {
      "product_id": "prod-101",
      "name": "Wireless Mouse",
      "quantity": 2,
      "unit_price": 2999
    },
    {
      "product_id": "prod-102",
      "name": "USB-C Hub",
      "quantity": 1,
      "unit_price": 4999
    }
  ]
}
```

**Response (`201 Created`):**

```json
{
  "order_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "customer_id": "cust-001",
  "currency": "USD",
  "amount": 10997,
  "items": [
    {
      "product_id": "prod-101",
      "name": "Wireless Mouse",
      "quantity": 2,
      "unit_price": 2999
    },
    {
      "product_id": "prod-102",
      "name": "USB-C Hub",
      "quantity": 1,
      "unit_price": 4999
    }
  ],
  "status": "pending",
  "created_at": "2026-01-15T10:30:00Z"
}
```

The `amount` field is automatically calculated as the sum of `unit_price * quantity` for each item.

### `GET /api/orders/{order_id}` — Get Order by ID

Retrieves a single order by its unique identifier.

**Response (`200 OK`):**

```json
{
  "order_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "customer_id": "cust-001",
  "currency": "USD",
  "amount": 10997,
  "items": [ ... ],
  "status": "pending",
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Error (`404 Not Found`):**

```json
{
  "detail": "Order a1b2c3d4-e5f6-7890-abcd-ef1234567890 not found"
}
```

### `GET /api/orders` — List Recent Orders

Returns the most recent orders, sorted by creation time (newest first).

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `50` | Maximum number of orders to return |

**Response (`200 OK`):**

```json
[
  {
    "order_id": "...",
    "customer_id": "cust-001",
    "currency": "USD",
    "amount": 10997,
    "items": [ ... ],
    "status": "pending",
    "created_at": "2026-01-15T10:30:00Z"
  }
]
```

### `PATCH /api/orders/{order_id}/status` — Update Order Status

Updates the status of an existing order. Typically called by the Payment Service after processing.

**Request:**

```json
{
  "status": "paid"
}
```

**Response (`200 OK`):** Returns the updated order object.

**Error (`404 Not Found`):** Returned if the order ID does not exist.

### `GET /health` — Health Check

Basic liveness probe. Always returns healthy if the service is running.

**Response (`200 OK`):**

```json
{
  "status": "healthy",
  "service": "eventflow-order-service"
}
```

### `GET /ready` — Readiness Check

Readiness probe that verifies connectivity to Azure Service Bus.

**Response (`200 OK`):**

```json
{
  "status": "ready",
  "service": "eventflow-order-service",
  "servicebus_connected": true
}
```

When Service Bus is not configured or unreachable, `status` will be `"degraded"` and `servicebus_connected` will be `false`.

## Currencies

The service supports the following ISO 4217 currencies:

| Code | Currency | Decimal Places |
|---|---|---|
| `USD` | US Dollar | 2 |
| `EUR` | Euro | 2 |
| `GBP` | British Pound | 2 |
| `JPY` | Japanese Yen | 0 |
| `KRW` | South Korean Won | 0 |
| `CHF` | Swiss Franc | 2 |
| `CAD` | Canadian Dollar | 2 |
| `AUD` | Australian Dollar | 2 |
| `CNY` | Chinese Yuan | 2 |
| `INR` | Indian Rupee | 2 |

**Important:** All monetary amounts (`unit_price`, `amount`) are expressed in the **smallest currency unit**:
- For currencies with 2 decimal places: cents (e.g., `2999` = $29.99 USD)
- For zero-decimal currencies (JPY, KRW): the base unit (e.g., `15800` = 15,800 JPY)

The downstream Payment Service is responsible for interpreting the amount based on the currency's decimal places.

## Event Schema

When an order is created, an `OrderCreated` event is published to the configured Azure Service Bus queue as a JSON message:

```json
{
  "event_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "event_type": "OrderCreated",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": {
    "order_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "customer_id": "cust-001",
    "currency": "USD",
    "amount": 10997,
    "items": [
      {
        "product_id": "prod-101",
        "name": "Wireless Mouse",
        "quantity": 2,
        "unit_price": 2999
      }
    ]
  }
}
```

The Service Bus message also includes application properties for filtering and routing:
- `event_type` — always `"OrderCreated"`
- `event_id` — unique event identifier (UUID)
- `currency` — the order's currency code
- `order_id` — the order's unique identifier

## Testing

The test suite uses **pytest** with the **pytest-asyncio** plugin and is located in the `tests/` directory.

### Running Tests

```bash
# Run all tests with verbose output
poetry run pytest -v --tb=short

# Run with coverage reporting
poetry run pytest --cov=app --cov-report=term-missing

# Run a specific test class
poetry run pytest tests/test_orders.py::TestCreateOrder -v
```

### Test Structure

- **`tests/conftest.py`** — Shared fixtures used across all test files:
  - `client` — a `FastAPI TestClient` instance for making HTTP requests
  - `sample_order_payload` — a valid USD order with two items
  - `sample_jpy_order_payload` — a valid JPY order (zero-decimal currency)
  - `sample_eur_order_payload` — a valid EUR order

- **`tests/test_orders.py`** — Tests organized by endpoint:
  - `TestCreateOrder` — order creation with various currencies, validation errors (empty items, invalid currency, negative quantity), and event publish failure handling
  - `TestGetOrder` — retrieving existing and nonexistent orders
  - `TestListOrders` — listing orders
  - `TestHealthEndpoints` — health and readiness endpoint behavior

Azure Service Bus calls are mocked using `unittest.mock.patch` so that tests run without any external dependencies.

## Docker

### Building the Image

```bash
docker build -t eventflow-order-service .
```

The Dockerfile uses a multi-stage build: the first stage installs dependencies with Poetry, and the second stage copies only the installed packages and application code for a smaller final image.

### Running the Container

```bash
# Using an .env file
docker run -p 8001:8001 --env-file .env eventflow-order-service

# Or pass environment variables individually
docker run -p 8001:8001 \
  -e AZURE_SERVICEBUS_CONNECTION_STRING="Endpoint=sb://..." \
  -e AZURE_SERVICEBUS_QUEUE_NAME="order-events" \
  -e APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..." \
  -e LOG_LEVEL="INFO" \
  -e ENVIRONMENT="production" \
  eventflow-order-service
```

The container exposes port **8001** and sets `ENVIRONMENT=production` and `LOG_LEVEL=INFO` by default.

## Development

### Linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting, configured in `pyproject.toml`:

```bash
# Check for lint errors
poetry run ruff check app/ tests/

# Auto-fix fixable issues
poetry run ruff check --fix app/ tests/
```

Ruff is configured to target Python 3.11 with a line length of 100 characters. Enabled rule sets: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `N` (pep8-naming), `W` (pycodestyle warnings), `UP` (pyupgrade).

### Code Style

- All monetary values use `int` in the smallest currency unit (no floating-point)
- Pydantic models use `Field(...)` with descriptions for API documentation
- Structured logging with `extra` dictionaries for contextual data
- Type hints on all function signatures
