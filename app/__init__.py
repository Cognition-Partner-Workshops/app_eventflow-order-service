"""EventFlow Order Service application package.

This package implements a FastAPI service that accepts customer orders via REST API
and publishes OrderCreated events to Azure Service Bus for downstream processing
(e.g. the Payment Service).
"""
