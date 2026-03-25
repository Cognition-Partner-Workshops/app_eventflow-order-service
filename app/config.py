"""Application configuration loaded from environment variables.

All settings can be overridden by setting the corresponding environment
variable (case-insensitive) or by adding an entry to a `.env` file in
the project root.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Order Service configuration.

    Attributes:
        azure_servicebus_connection_string: Connection string for Azure Service
            Bus.  When empty the service operates in "offline" mode and events
            are logged but not published.
        azure_servicebus_queue_name: Name of the Service Bus queue that
            receives OrderCreated events.
        applicationinsights_connection_string: Optional Azure Monitor
            connection string for distributed tracing.
        log_level: Python log level name (DEBUG, INFO, WARNING, ERROR).
        environment: Deployment environment label (development, staging, production).
        service_name: Logical service name surfaced in health checks and logs.
        service_version: Semantic version reported in the OpenAPI spec.
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
