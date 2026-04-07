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

from hub_adapter.auth import (
    _add_internal_token_if_missing,
    _get_internal_token,
    get_hub_public_key,
    require_researcher_role,
    require_steward_role,
    verify_idp_token,
)
from hub_adapter.conf import Settings
from tests.constants import (
    ADMIN_ROLE,
    RESEARCHER_ROLE,
    STEWARD_ROLE,
    TEST_JWKS_RESPONSE,
    TEST_JWT,
    TEST_OIDC,
    TEST_RESEARCHER_DECRYPTED_JWT,
    TEST_STEWARD_DECRYPTED_JWT,
)


class TestAuth:
    @pytest.mark.asyncio
    async def test_get_hub_public_key(self, httpx_mock, test_settings):
        """Test that the public key is returned."""
        fake_key_ep = test_settings.hub_auth_service_url.rstrip("/") + "/jwks"
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
        assert await _get_internal_token(TEST_OIDC, test_settings) == {"Authorization": f"Bearer {TEST_JWT}"}

    @patch("hub_adapter.auth._get_internal_token")
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
        unmodified_resp = await _add_internal_token_if_missing(fake_request)
        assert isinstance(unmodified_resp, Request)
        assert not unmodified_resp.headers

        # Add header
        mock_config_check.return_value = (False, TEST_OIDC)
        mock_internal_token.return_value = fake_token_header
        modified_resp = await _add_internal_token_if_missing(fake_request)
        assert isinstance(modified_resp, Request)
        assert modified_resp.headers == MutableHeaders(fake_token_header)

    @patch("hub_adapter.auth.logger")
    @pytest.mark.asyncio
    async def test_check_rbac_rules(self, mock_logger):
        """Test the add_internal_token_if_missing method."""
        correct_role_claim_name = "resource_access.node-ui.roles"

        mock_settings = Settings()
        assert mock_settings.steward_role is None
        assert mock_settings.researcher_role is None

        # No steward or researcher role set - auto pass
        await require_steward_role(TEST_STEWARD_DECRYPTED_JWT, mock_settings)
        await require_researcher_role(TEST_RESEARCHER_DECRYPTED_JWT, mock_settings)

        # Set role names and check
        mock_settings_with_correct_roles = Settings(
            role_claim_name=correct_role_claim_name,
            admin_role=ADMIN_ROLE,
            steward_role=STEWARD_ROLE,
            researcher_role=RESEARCHER_ROLE,
        )
        assert mock_settings_with_correct_roles.steward_role == STEWARD_ROLE
        assert mock_settings_with_correct_roles.researcher_role == RESEARCHER_ROLE

        await require_steward_role(TEST_STEWARD_DECRYPTED_JWT, mock_settings_with_correct_roles)
        await require_researcher_role(TEST_RESEARCHER_DECRYPTED_JWT, mock_settings_with_correct_roles)

        # Mismatch role names and expect fail
        mock_settings_with_mismatched_roles = Settings(
            role_claim_name=correct_role_claim_name,
            steward_role="foo",
            researcher_role="bar",
        )
        assert mock_settings_with_mismatched_roles.steward_role == "foo"
        assert mock_settings_with_mismatched_roles.researcher_role == "bar"

        with pytest.raises(HTTPException) as steward_error:
            await require_steward_role(TEST_STEWARD_DECRYPTED_JWT, mock_settings_with_mismatched_roles)
            assert steward_error.value.status_code == status.HTTP_403_FORBIDDEN
            assert (
                steward_error.value.detail["message"]
                == f"Insufficient permissions, admin or {STEWARD_ROLE} role not found in token."
            )

        with pytest.raises(HTTPException) as researcher_error:
            await require_researcher_role(TEST_RESEARCHER_DECRYPTED_JWT, mock_settings_with_mismatched_roles)
            assert researcher_error.value.status_code == status.HTTP_403_FORBIDDEN
            assert (
                researcher_error.value.detail["message"]
                == f"Insufficient permissions, admin or {RESEARCHER_ROLE} role not found in token."
            )

        # Wrong claim name
        wrong_claim_name = "foo"
        mock_settings_with_wrong_claim_name = Settings(
            role_claim_name=wrong_claim_name,
            steward_role=STEWARD_ROLE,
        )
        assert mock_settings_with_wrong_claim_name.steward_role == STEWARD_ROLE

        with pytest.raises(HTTPException) as steward_error:
            await require_steward_role(TEST_STEWARD_DECRYPTED_JWT, mock_settings_with_wrong_claim_name)
            assert mock_logger.warning.call_count == 1
            mock_logger.warning.assert_any_call(f"No roles found in token using {wrong_claim_name}")
            assert steward_error.value.status_code == status.HTTP_403_FORBIDDEN
            assert (
                steward_error.value.detail["message"]
                == f"Insufficient permissions, admin or {STEWARD_ROLE} role not found in token."
            )
