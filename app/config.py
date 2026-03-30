"""Application configuration loaded from environment variables.

Uses pydantic-settings to bind environment variables (and an optional ``.env``
file) to typed Python attributes.  Every setting has a sensible default so the
service can start in development mode without any external configuration.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Order Service configuration.

    Attributes are populated from environment variables whose names match the
    attribute name (case-insensitive).  A ``.env`` file in the project root is
    also read when present.
    """

    # Azure Service Bus — required for event publishing; leave blank to run in
    # degraded mode (orders are accepted but events are not published).
    azure_servicebus_connection_string: str = ""
    azure_servicebus_queue_name: str = "order-events"

    # Azure Monitor / Application Insights — optional; when set, OpenTelemetry
    # traces and metrics are exported to Application Insights.
    applicationinsights_connection_string: str = ""

    # Application-level settings used for logging, health checks, and
    # OpenTelemetry resource attributes.
    log_level: str = "INFO"
    environment: str = "development"  # e.g. "development", "staging", "production"
    service_name: str = "eventflow-order-service"
    service_version: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Module-level singleton so every module imports the same instance.
settings = Settings()
