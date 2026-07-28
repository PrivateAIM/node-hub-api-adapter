"""Collection of unit tests for testing the oidc module."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx2 import ConnectError, ReadTimeout, Request
from starlette import status

from hub_adapter.oidc import check_oidc_configs_match, fetch_openid_config
from tests.constants import TEST_OIDC, TEST_OIDC_RESPONSE, TEST_OIDC_SVC_RESPONSE, TEST_SVC_OIDC, TEST_SVC_URL, TEST_URL


class TestOidc:
    @pytest.fixture(autouse=True)
    def _clear_oidc_cache(self):
        """fetch_openid_config is lru_cached, so purge it to keep these tests order independent."""
        fetch_openid_config.cache_clear()
        yield
        fetch_openid_config.cache_clear()

    @patch("hub_adapter.oidc.get_settings")
    def test_basic_oidc_fetching(self, mock_settings, httpx2_mock, test_settings):
        """Test that the correct OIDC config is returned.

        This tests check_oidc_configs_match, get_svc_oidc_config, get_user_oidc_config, and partly
        fetch_openid_config."""

        fake_oidc_url = f"{TEST_URL}/.well-known/openid-configuration"
        fake_oidc_svc_url = f"{TEST_SVC_URL}/.well-known/openid-configuration"
        mock_settings.return_value = test_settings  # Initializes with different URLs
        httpx2_mock.get(fake_oidc_url).respond(status_code=200, json=TEST_OIDC_RESPONSE)
        httpx2_mock.get(fake_oidc_svc_url).respond(status_code=200, json=TEST_OIDC_SVC_RESPONSE)

        # Different OIDC URLs
        diff_check, diff_config = check_oidc_configs_match()
        assert not diff_check
        assert diff_config == TEST_SVC_OIDC

        # Same OIDC
        matching_oidc_settings = test_settings.model_copy(update={"node_svc_oidc_url": fake_oidc_url})
        mock_settings.return_value = matching_oidc_settings

        match_check, match_config = check_oidc_configs_match()
        assert match_check
        assert match_config == TEST_OIDC

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
