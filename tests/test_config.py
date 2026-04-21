"""Tests for application configuration."""

from unittest.mock import patch

from app.config import Settings


class TestSettingsDefaults:
    """Tests for default settings values."""

    def test_default_connection_string_empty(self):
        """Default azure_servicebus_connection_string should be empty."""
        s = Settings(
            _env_file=None,
            azure_servicebus_connection_string="",
        )
        assert s.azure_servicebus_connection_string == ""

    def test_default_queue_name(self):
        """Default queue name should be 'order-events'."""
        s = Settings(_env_file=None)
        assert s.azure_servicebus_queue_name == "order-events"

    def test_default_log_level(self):
        """Default log level should be INFO."""
        s = Settings(_env_file=None)
        assert s.log_level == "INFO"

    def test_default_environment(self):
        """Default environment should be 'development'."""
        s = Settings(_env_file=None)
        assert s.environment == "development"

    def test_default_service_name(self):
        """Default service name should be 'eventflow-order-service'."""
        s = Settings(_env_file=None)
        assert s.service_name == "eventflow-order-service"

    def test_default_service_version(self):
        """Default service version should be '1.0.0'."""
        s = Settings(_env_file=None)
        assert s.service_version == "1.0.0"

    def test_default_appinsights_connection_string_empty(self):
        """Default applicationinsights_connection_string should be empty."""
        s = Settings(_env_file=None)
        assert s.applicationinsights_connection_string == ""


class TestSettingsFromEnv:
    """Tests for loading settings from environment variables."""

    @patch.dict(
        "os.environ",
        {
            "AZURE_SERVICEBUS_CONNECTION_STRING": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=abc=",
            "AZURE_SERVICEBUS_QUEUE_NAME": "my-queue",
            "LOG_LEVEL": "DEBUG",
            "ENVIRONMENT": "production",
        },
    )
    def test_settings_from_env_vars(self):
        """Settings should load values from environment variables."""
        s = Settings(_env_file=None)
        assert s.azure_servicebus_connection_string == (
            "Endpoint=sb://test.servicebus.windows.net/;"
            "SharedAccessKeyName=test;SharedAccessKey=abc="
        )
        assert s.azure_servicebus_queue_name == "my-queue"
        assert s.log_level == "DEBUG"
        assert s.environment == "production"
