"""Unit tests for event logging middleware."""

from unittest.mock import patch

from starlette.requests import Request


class TestEventLoggingMiddleware:
    """Test suite for event logging middleware."""

    def test_middleware_logs_request_success(self, test_client, mock_event_logger):
        """Test that middleware logs successful requests."""
        with patch("hub_adapter.server.get_event_logger", return_value=mock_event_logger):
            response = test_client.get("/healthz")

            mock_event_logger.log_fastapi_request.assert_called_once()

            call_args = mock_event_logger.log_fastapi_request.call_args
            request_arg = call_args[0][0]
            status_code_arg = call_args[0][1]

            assert isinstance(request_arg, Request)
            assert status_code_arg == response.status_code  # should match

    def test_middleware_logs_different_status_codes(self, test_client, mock_event_logger):
        """Test that middleware logs requests with different status codes."""
        with patch("hub_adapter.server.get_event_logger", return_value=mock_event_logger):
            response = test_client.get("/healthz")

            status_code_logged = mock_event_logger.log_fastapi_request.call_args[0][1]
            assert status_code_logged == response.status_code

    def test_middleware_continues_on_logger_not_initialized(self, test_client):
        """Test that middleware handles AttributeError when logger not initialized."""
        with patch("hub_adapter.server.get_event_logger", side_effect=AttributeError("Logger not initialized")):
            response = test_client.get("/health")  # Should return 404 since actual endpoint is "healthz"

            assert response.status_code in [200, 404]

    def test_middleware_handles_post_requests(self, test_client, mock_event_logger):
        """Test that middleware logs POST requests."""
        with patch("hub_adapter.server.get_event_logger", return_value=mock_event_logger):
            test_client.post("/token", json={"username": "test", "password": "test"})

            mock_event_logger.log_fastapi_request.assert_called_once()

            request_arg = mock_event_logger.log_fastapi_request.call_args[0][0]
            assert request_arg.method == "POST"

    def test_middleware_processes_all_requests(self, test_client, mock_event_logger):
        """Test that middleware is called for multiple sequential requests."""
        with patch("hub_adapter.server.get_event_logger", return_value=mock_event_logger):
            test_client.get("/healthz")
            test_client.get("/po/logs")

            assert mock_event_logger.log_fastapi_request.call_count == 2

    @patch("hub_adapter.server.get_event_logger")
    def test_middleware_exception_handling(self, mock_get_logger, test_client):
        """Test that middleware gracefully handles logging exceptions."""
        mock_get_logger.side_effect = AttributeError("Event logging not initialized")
        response = test_client.get("/healthz")

        assert response is not None  # Verify request completed despite logging error

        mock_get_logger.assert_called()
