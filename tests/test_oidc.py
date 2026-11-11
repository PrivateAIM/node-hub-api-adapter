"""Collection of unit tests for testing the oidc module."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx2 import ConnectError, ReadTimeout, Request
from starlette import status

from hub_adapter.oidc import fetch_openid_config, get_oidc_config
from tests.constants import TEST_OIDC, TEST_OIDC_RESPONSE, TEST_URL


class TestOidc:
    @pytest.fixture(autouse=True)
    def _clear_oidc_cache(self):
        """fetch_openid_config is lru_cached, so purge it to keep these tests order independent."""
        fetch_openid_config.cache_clear()
        yield
        fetch_openid_config.cache_clear()

    @patch("hub_adapter.oidc.get_settings")
    def test_basic_oidc_fetching(self, mock_settings, httpx2_mock, test_settings):
        """Test that get_oidc_config fetches the configuration from the IDP_URL."""
        fake_oidc_url = f"{TEST_URL}/.well-known/openid-configuration"
        mock_settings.return_value = test_settings
        httpx2_mock.get(fake_oidc_url).respond(status_code=200, json=TEST_OIDC_RESPONSE)

        assert get_oidc_config() == TEST_OIDC

    @patch("hub_adapter.oidc.logger")
    def test_fetch_openid_config_errors(self, mock_logger, httpx2_mock):
        """Test the fetch_openid_config method for error handling."""
        fake_oidc_url = f"{TEST_URL}/.well-known/openid-configuration"
        oidc_route = httpx2_mock.get(fake_oidc_url)
        oidc_route.respond(status_code=status.HTTP_404_NOT_FOUND)

        with pytest.raises(HTTPException) as status_error:
            fetch_openid_config(fake_oidc_url)

        assert status_error.value.status_code == status.HTTP_404_NOT_FOUND
        assert mock_logger.error.call_count == 1

        # Catch ConnectError
        oidc_route.mock(
            side_effect=ConnectError(
                message="Not Found",
                request=Request("GET", fake_oidc_url),
            )
        )

        with pytest.raises(ConnectError):
            fetch_openid_config(fake_oidc_url, max_retries=0, wait_interval=0)

        assert mock_logger.warning.call_count == 1
        assert mock_logger.error.call_count == 2

        # Catch ReadTimeout
        oidc_route.mock(
            side_effect=ReadTimeout(
                message="Not Found",
                request=Request("GET", fake_oidc_url),
            )
        )

        with pytest.raises(ConnectError):
            fetch_openid_config(fake_oidc_url, max_retries=0, wait_interval=0)

        assert mock_logger.warning.call_count == 2
        assert mock_logger.error.call_count == 3
