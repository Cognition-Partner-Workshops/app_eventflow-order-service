"""Application configuration loaded from environment variables.

Uses pydantic-settings to load values from environment variables and ``.env`` files.
The ``Settings`` class is instantiated once at module level as a singleton (``settings``)
and imported throughout the application.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Order Service configuration.

    Fields map directly to environment variable names (case-insensitive).
    A ``.env`` file in the project root is loaded automatically if present.

    Attributes:
        azure_servicebus_connection_string: Connection string for Azure Service Bus.
            Leave empty to disable event publishing.
        azure_servicebus_queue_name: Name of the Service Bus queue for order events.
        applicationinsights_connection_string: Connection string for Azure Application
            Insights. Leave empty to disable telemetry.
        log_level: Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        environment: Deployment environment label (e.g., development, production).
        service_name: Identifier used in logs, health checks, and API metadata.
        service_version: Semantic version reported in API metadata.
    """

    # Azure Service Bus
    azure_servicebus_connection_string: str = ""
    azure_servicebus_queue_name: str = "order-events"

    # Azure Monitor
    applicationinsights_connection_string: str = ""

    # Application
    log_level: str = "INFO"
    environment: str = "development"
    service_name: str = "eventflow-order-service"
    service_version: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
