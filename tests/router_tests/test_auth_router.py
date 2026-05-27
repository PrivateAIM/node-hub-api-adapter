"""Unit tests for the auth router endpoint."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from starlette import status

from hub_adapter.routers.auth import auth_router, get_token
from hub_adapter.schemas.conf import Token
from tests.conftest import check_routes
from tests.constants import TEST_OIDC, TEST_OIDC_RESPONSE, TEST_SVC_OIDC

EXPECTED_AUTH_ROUTE_CONFIG = (
    {
        "path": "/token",
        "name": "get_token",
        "methods": {"POST"},
        "status_code": status.HTTP_200_OK,
        "response_model": Token,
    },
)


class TestAuthRouter:
    """Auth endpoint configuration and behaviour tests."""

    def test_route_configs(self, test_client):
        """Test endpoint configurations for the auth router."""
        check_routes(auth_router, EXPECTED_AUTH_ROUTE_CONFIG, test_client)

    @patch("hub_adapter.routers.auth.get_svc_oidc_config")
    @patch("hub_adapter.routers.auth.httpx.Client")
    def test_get_token_success(self, mock_client_cls, mock_oidc_config, test_settings):
        """get_token returns a Token when the IDP responds with 200."""
        mock_oidc_config.return_value = TEST_OIDC

        token_payload = {
            "access_token": "abc123",
            "token_type": "Bearer",
            "expires_in": 300,
            "refresh_token": "refresh_abc",
            "refresh_expires_in": 1800,
            "scope": "openid",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = httpx.codes.OK
        mock_resp.json.return_value = token_payload

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        ssl_ctx = MagicMock()
        result = get_token(settings=test_settings, username="user", password="pass", ssl_ctx=ssl_ctx)

        assert isinstance(result, Token)
        assert result.access_token == "abc123"

    @patch("hub_adapter.routers.auth.get_svc_oidc_config")
    @patch("hub_adapter.routers.auth.httpx.Client")
    def test_get_token_raises_on_non_200(self, mock_client_cls, mock_oidc_config, test_settings):
        """get_token raises HTTPException when the IDP returns a non-200 status."""
        mock_oidc_config.return_value = TEST_OIDC

        mock_resp = MagicMock()
        mock_resp.status_code = status.HTTP_401_UNAUTHORIZED
        mock_resp.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        ssl_ctx = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            get_token(settings=test_settings, username="bad", password="wrong", ssl_ctx=ssl_ctx)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Unauthorized"
