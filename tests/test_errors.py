"""Unit tests for errors.py log_event integration."""

import logging
from unittest.mock import ANY, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from flame_hub import HubAPIError
from starlette import status

from hub_adapter.errors import (
    BucketError,
    FhirEndpointError,
    HubConnectError,
    HubTimeoutError,
    KongConsumerApiKeyError,
    KongError,
    KongGatewayError,
    KongServiceError,
    KongTimeoutError,
    catch_hub_errors,
    catch_kong_errors,
)


class TestErrorClassLogging:
    """Tests that each error class calls log_event on instantiation."""

    @patch("hub_adapter.errors.log_event")
    def test_bucket_error_logs(self, mock_log_event):
        """BucketError logs the correct event on instantiation."""
        BucketError()
        mock_log_event.assert_called_once_with(
            "storage.bucket.forbidden",
            event_description="Bucket does not exist or is set to private",
            level=logging.ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            service="MinIO",
        )

    @patch("hub_adapter.errors.log_event")
    def test_kong_gateway_error_logs(self, mock_log_event):
        """KongGatewayError logs the correct event on instantiation."""
        server = "TestServer"
        KongGatewayError(server_type=server)
        mock_log_event.assert_called_once_with(
            "kong.gateway.error",
            event_description=f"Unable to contact the {server} service, likely an incorrect port",
            level=logging.ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            service=server,
        )

    @patch("hub_adapter.errors.log_event")
    def test_kong_service_error_logs(self, mock_log_event):
        """KongServiceError logs the correct event on instantiation."""
        server = "TestServer"
        KongServiceError(server_type=server)
        mock_log_event.assert_called_once_with(
            "kong.service.resolution_failed",
            event_description=f"{server} server name resolution failed",
            level=logging.ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            service=server,
        )

    @patch("hub_adapter.errors.log_event")
    def test_fhir_endpoint_error_logs(self, mock_log_event):
        """FhirEndpointError logs the correct event on instantiation."""
        FhirEndpointError()
        mock_log_event.assert_called_once_with(
            "fhir.endpoint.not_found",
            event_description="FHIR endpoint not found, check the data path",
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="FHIR",
        )

    @patch("hub_adapter.errors.log_event")
    def test_kong_consumer_api_key_error_logs(self, mock_log_event):
        """KongConsumerApiKeyError logs the correct event on instantiation."""
        KongConsumerApiKeyError()
        mock_log_event.assert_called_once_with(
            "kong.consumer.api_key.not_found",
            event_description="Unable to obtain API key for health consumer",
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="Kong",
        )


class TestCatchHubErrorsLogging:
    """Tests that catch_hub_errors calls log_event for each error branch."""

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_proxy_error_logs(self, mock_log_event):
        """catch_hub_errors logs hub.proxy.error on httpx.ProxyError."""
        import httpx

        @catch_hub_errors
        async def raise_proxy():
            raise httpx.ProxyError("proxy down")

        with pytest.raises(Exception):
            await raise_proxy()

        mock_log_event.assert_called_once_with(
            "hub.proxy.error",
            event_description="Proxy Error - Unable to contact the Hub",
            level=logging.ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            service="Proxy",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_read_timeout_logs(self, mock_log_event):
        """catch_hub_errors logs hub.read.timeout on httpx.ReadTimeout."""
        import httpx

        @catch_hub_errors
        async def raise_timeout():
            raise httpx.ReadTimeout("timed out", request=None)

        with pytest.raises(Exception):
            await raise_timeout()

        mock_log_event.assert_called_once_with(
            "hub.read.timeout",
            event_description="ReadTimeout Error - Hub is offline or undergoing maintenance",
            level=logging.ERROR,
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            service="Hub",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_connect_error_logs(self, mock_log_event):
        """catch_hub_errors logs hub.connect.error on httpx.ConnectError."""
        import httpx

        @catch_hub_errors
        async def raise_connect():
            raise httpx.ConnectError("cannot connect")

        with pytest.raises(Exception):
            await raise_connect()

        mock_log_event.assert_called_once_with(
            "hub.connect.error",
            event_description="ConnectError - CoreClient is unable to get token from Hub",
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="CoreClient",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_validation_error_logs(self, mock_log_event):
        """catch_hub_errors logs hub.validation.error on pydantic.ValidationError."""
        from pydantic import BaseModel

        class M(BaseModel):
            x: int

        @catch_hub_errors
        async def raise_validation():
            M(x="not_an_int")  # triggers pydantic.ValidationError

        with pytest.raises(Exception):
            await raise_validation()

        assert mock_log_event.call_args[0][0] == "hub.validation.error"
        assert mock_log_event.call_args[1]["level"] == logging.ERROR
        assert mock_log_event.call_args[1]["status_code"] == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCatchKongErrorsLogging:
    """Tests that catch_kong_errors calls log_event correctly."""

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_api_exception_conflict_logs(self, mock_log_event):
        """catch_kong_errors logs kong.consumer.conflict on 409 ApiException."""
        from kong_admin_client.exceptions import ApiException

        @catch_kong_errors
        async def raise_conflict():
            raise ApiException(status=409, reason="Conflict")

        with pytest.raises(Exception):
            await raise_conflict()

        mock_log_event.assert_called_once_with(
            "kong.consumer.conflict",
            event_description="Kong consumer conflict",
            level=logging.ERROR,
            status_code=409,
            service="Kong",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_api_exception_not_found_logs(self, mock_log_event):
        """catch_kong_errors logs kong.service.not_found on 404 ApiException."""
        from kong_admin_client.exceptions import ApiException

        @catch_kong_errors
        async def raise_not_found():
            raise ApiException(status=404, reason="Not Found")

        with pytest.raises(Exception):
            await raise_not_found()

        mock_log_event.assert_called_once_with(
            "kong.service.not_found",
            event_description="Kong service not found",
            level=logging.ERROR,
            status_code=404,
            service="Kong",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_max_retry_error_logs(self, mock_log_event):
        """catch_kong_errors logs kong.service.unavailable on MaxRetryError."""
        from urllib3.exceptions import MaxRetryError

        @catch_kong_errors
        async def raise_max_retry():
            raise MaxRetryError(pool=None, url="/", reason="exhausted")

        with pytest.raises(Exception):
            await raise_max_retry()

        mock_log_event.assert_called_once_with(
            "kong.service.unavailable",
            event_description="Kong service unavailable",
            level=logging.ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            service="Kong",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_http_exception_reraise_does_not_double_log(self, mock_log_event):
        """BucketError (HTTPException subclass) should log once via __init__, not again on re-raise."""
        @catch_kong_errors
        async def raise_bucket():
            raise BucketError()

        with pytest.raises(BucketError):
            await raise_bucket()

        assert mock_log_event.call_count == 1
        assert mock_log_event.call_args[0][0] == "storage.bucket.forbidden"


class TestCatchHubErrorsHubAPIError:
    """Tests for HubAPIError branches inside catch_hub_errors."""

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_hub_api_error_connect_timeout_raises_hub_timeout_error(self, mock_log_event):
        """HubAPIError with ConnectTimeout error_response raises HubTimeoutError."""
        fake_request = httpx.Request("GET", "http://hub")
        connect_timeout = httpx.ConnectTimeout("timed out", request=fake_request)

        @catch_hub_errors
        async def raise_hub_error():
            raise HubAPIError("timeout", request=fake_request, error=connect_timeout)

        with pytest.raises(HubTimeoutError) as exc_info:
            await raise_hub_error()

        assert exc_info.value.status_code == status.HTTP_408_REQUEST_TIMEOUT
        mock_log_event.assert_called_once_with(
            "hub.connection.timeout",
            event_description="Connection Timeout - Hub is currently unreachable",
            level=logging.ERROR,
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            service="Hub",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_hub_api_error_connect_error_raises_hub_connect_error(self, mock_log_event):
        """HubAPIError with ConnectError error_response raises HubConnectError."""
        fake_request = httpx.Request("GET", "http://hub")
        connect_error = httpx.ConnectError("refused")

        @catch_hub_errors
        async def raise_hub_error():
            raise HubAPIError("connect error", request=fake_request, error=connect_error)

        with pytest.raises(HubConnectError) as exc_info:
            await raise_hub_error()

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        mock_log_event.assert_called_once_with(
            "hub.connection.error",
            event_description="Connection Error - Hub is currently unreachable",
            level=logging.ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            service="Hub",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_hub_api_error_other_raises_http_exception(self, mock_log_event):
        """HubAPIError with any other error_response raises a plain HTTPException."""
        fake_request = httpx.Request("GET", "http://hub")
        error_resp = MagicMock()
        error_resp.status_code = status.HTTP_403_FORBIDDEN
        error_resp.message = "Forbidden by hub"

        @catch_hub_errors
        async def raise_hub_error():
            raise HubAPIError("auth error", request=fake_request, error=error_resp)

        with pytest.raises(HTTPException) as exc_info:
            await raise_hub_error()

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail["message"] == "Forbidden by hub"
        assert exc_info.value.detail["service"] == "Hub"
        assert exc_info.value.detail["status_code"] == status.HTTP_403_FORBIDDEN
        mock_log_event.assert_called_once_with(
            "hub.auth.error",
            event_description="Failed to retrieve JWT from Hub",
            level=logging.ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            service="Hub",
        )


class TestCatchKongErrorsMissingBranches:
    """Tests for catch_kong_errors branches not yet covered."""

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_api_exception_other_status_raises_kong_error(self, mock_log_event):
        """catch_kong_errors raises KongError for ApiException with status != 409 and != 404."""
        from kong_admin_client.exceptions import ApiException

        @catch_kong_errors
        async def raise_other():
            raise ApiException(status=500, reason="Internal Server Error")

        with pytest.raises(KongError) as exc_info:
            await raise_other()

        assert exc_info.value.status_code == 500
        mock_log_event.assert_called_once_with(
            "kong.api.error",
            event_description=ANY,
            level=logging.ERROR,
            status_code=500,
            service="Kong",
        )

    @patch("hub_adapter.errors.log_event")
    @pytest.mark.asyncio
    async def test_generic_exception_raises_http_500(self, mock_log_event):
        """catch_kong_errors wraps any unexpected Exception into HTTP 500."""
        @catch_kong_errors
        async def raise_generic():
            raise RuntimeError("something unexpected")

        with pytest.raises(HTTPException) as exc_info:
            await raise_generic()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_log_event.assert_called_once_with(
            "kong.service.error",
            event_description=ANY,
            level=logging.ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            service="Kong",
        )
