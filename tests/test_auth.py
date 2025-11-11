"""Collection of unit tests for testing the auth methods."""

from unittest.mock import patch

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from hub_adapter.auth import add_internal_token_if_missing, get_hub_public_key, get_internal_token, verify_idp_token
from tests.constants import TEST_JWKS_RESPONSE, TEST_JWT, TEST_OIDC


class TestAuth:
    @pytest.mark.asyncio
    async def test_get_hub_public_key(self, httpx_mock, test_settings):
        """Test that the public key is returned."""
        fake_key_ep = test_settings.HUB_AUTH_SERVICE_URL.rstrip("/") + "/jwks"
        httpx_mock.add_response(url=fake_key_ep, json=TEST_JWKS_RESPONSE, status_code=200)

        data = await get_hub_public_key(test_settings)
        assert isinstance(data, dict)
        assert data == TEST_JWKS_RESPONSE

    @pytest.mark.asyncio
    async def test_verify_idp_token_missing(self, test_settings):
        """Test that verify_idp_token handles a missing token."""
        with pytest.raises(HTTPException) as missingError:
            await verify_idp_token(test_settings, token=None)

            assert missingError.type == HTTPException

    @patch("hub_adapter.auth.get_svc_oidc_config")
    @patch("hub_adapter.auth.get_user_oidc_config")
    @patch("hub_adapter.auth.jwt.decode")
    @pytest.mark.asyncio
    async def test_verify_idp_token_errors(self, mock_decode, mock_user_oidc, mock_svc_oidc, test_settings):
        """Test that verify_idp_token handles decode errors."""
        fake_token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        mock_user_oidc.return_value = ""
        mock_svc_oidc.return_value = ""

        mock_decode.side_effect = httpx.ConnectError("Can't connect to server")
        with pytest.raises(HTTPException) as connect_error:
            await verify_idp_token(test_settings, token=fake_token)
            assert connect_error.value.status_code == status.HTTP_404_NOT_FOUND

        mock_decode.side_effect = jwt.DecodeError("Test error")
        with pytest.raises(HTTPException) as decode_error:
            await verify_idp_token(test_settings, token=fake_token)
            assert decode_error.value.status_code == status.HTTP_401_UNAUTHORIZED

        mock_decode.side_effect = jwt.ExpiredSignatureError()
        with pytest.raises(HTTPException) as expired_sig_error:
            await verify_idp_token(test_settings, token=fake_token)
            assert expired_sig_error.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert expired_sig_error.value.detail["message"] == "Authorization token expired"

        mock_decode.side_effect = jwt.MissingRequiredClaimError(claim="iat")
        with pytest.raises(HTTPException) as missing_claim_error:
            await verify_idp_token(test_settings, token=TEST_JWT)
            assert missing_claim_error.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert missing_claim_error.value.detail["message"] == "Incorrect claims, check the audience and issuer."

        mock_decode.side_effect = ValueError  # Some other random error
        with pytest.raises(HTTPException) as random_error:
            await verify_idp_token(test_settings, token=fake_token)
            assert random_error.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert missing_claim_error.value.detail["message"] == "Unable to parse authentication token"

    @pytest.mark.asyncio
    async def test_get_internal_token(self, httpx_mock, test_settings):
        """Test the get_internal_token method."""
        fake_token_resp = {
            "access_token": TEST_JWT,
            "token_type": "Bearer",
            "expires_in": 7200,
            "refresh_token": TEST_JWT,
            "refresh_expires_in": 1800,
        }
        httpx_mock.add_response(url=TEST_OIDC.token_endpoint, json=fake_token_resp, status_code=200)
        assert await get_internal_token(TEST_OIDC, test_settings) == {"Authorization": f"Bearer {TEST_JWT}"}

    @patch("hub_adapter.auth.get_internal_token")
    @patch("hub_adapter.auth.check_oidc_configs_match")
    @pytest.mark.asyncio
    async def test_add_internal_token_if_missing(self, mock_config_check, mock_internal_token):
        """Test the add_internal_token_if_missing method."""
        req_scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        }
        fake_request = Request(req_scope)
        fake_token_header = {"Authorization": f"Bearer {TEST_JWT}"}
        assert not fake_request.headers

        # Add nothing
        mock_config_check.return_value = (True, TEST_OIDC)
        unmodified_resp = await add_internal_token_if_missing(fake_request)
        assert isinstance(unmodified_resp, Request)
        assert not unmodified_resp.headers

        # Add header
        mock_config_check.return_value = (False, TEST_OIDC)
        mock_internal_token.return_value = fake_token_header
        modified_resp = await add_internal_token_if_missing(fake_request)
        assert isinstance(modified_resp, Request)
        assert modified_resp.headers == MutableHeaders(fake_token_header)
