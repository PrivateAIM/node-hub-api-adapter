"""Handle the authorization and authentication of services."""

import logging
import time
import uuid
from functools import lru_cache

import httpx
import jwt
from fastapi import HTTPException, Security
from fastapi.security import (
    HTTPBearer,
    OAuth2AuthorizationCodeBearer,
)
from jwt import PyJWKClient
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import OIDCConfiguration, Token

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def fetch_openid_config(oidc_url: str, max_retries: int = 6) -> OIDCConfiguration:
    """Fetch the openid configuration from the OIDC URL. Tries until it reaches max_retries."""
    provided_url = oidc_url
    if not oidc_url.endswith(".well-known/openid-configuration"):
        oidc_url = oidc_url.rstrip("/") + "/.well-known/openid-configuration"

    attempt_num = 0
    while attempt_num <= max_retries:
        try:
            response = httpx.get(oidc_url)
            response.raise_for_status()
            oidc_config = response.json()
            return OIDCConfiguration(**oidc_config)

        except httpx.ConnectError:  # OIDC Service not up yet
            attempt_num += 1
            wait_time = 10 * (2 ** (attempt_num - 1))  # 10s, 20s, 40s, 80s, 160s, 320s
            logger.warning(f"Unable to contact the IDP at {oidc_url}, retrying in {wait_time} seconds")
            time.sleep(wait_time)

        except httpx.HTTPStatusError:
            err_msg = (
                f"HTTP error occurred while trying to contact the IDP: {provided_url}, is this the correct issuer URL?"
            )
            logger.error(err_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Auth",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            )

    logger.error(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")
    raise httpx.ConnectError(f"Failed to connect after {max_retries} attempts.")


user_oidc_config = fetch_openid_config(hub_adapter_settings.IDP_URL)
svc_oidc_config = (
    fetch_openid_config(hub_adapter_settings.NODE_SVC_OIDC_URL)
    if hub_adapter_settings.NODE_SVC_OIDC_URL != hub_adapter_settings.IDP_URL
    else user_oidc_config
)

idp_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=user_oidc_config.authorization_endpoint,
    tokenUrl=user_oidc_config.token_endpoint,
)

jwtbearer = HTTPBearer(
    scheme_name="JWT",
    description="Pass a valid JWT here for authentication. Can be obtained from /token endpoint.",
)


async def get_hub_public_key() -> dict:
    """Get the central hub service public key."""
    hub_jwks_ep = hub_adapter_settings.HUB_AUTH_SERVICE_URL.rstrip("/") + "/jwks"
    return httpx.get(hub_jwks_ep).json()


async def verify_idp_token(token: str = Security(idp_oauth2_scheme)) -> dict:
    """Decode the auth token using keycloak's public key."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode just to get issuer
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified_claims.get("iss")

        if hub_adapter_settings.OVERRIDE_JWKS:  # Override the fetched URIs
            jwk_client = PyJWKClient(hub_adapter_settings.OVERRIDE_JWKS)
        # If the issuer is the user's OIDC, use the user's public key, otherwise use the node's internal public key
        elif issuer == user_oidc_config.issuer:
            jwk_client = PyJWKClient(user_oidc_config.jwks_uri)

        else:
            jwk_client = PyJWKClient(svc_oidc_config.jwks_uri)

        signing_key = jwk_client.get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            key=signing_key,
            options={"verify_signature": True, "verify_aud": False, "exp": True},
        )

    except jwt.DecodeError as e:
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.ExpiredSignatureError:
        err_msg = "Authorization token expired"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(status_code=401, detail=err_msg)

    except jwt.MissingRequiredClaimError:
        err_msg = "Incorrect claims, check the audience and issuer."
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(status_code=401, detail=err_msg)

    except Exception:
        err_msg = "Unable to parse authentication token"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(
            status_code=401,
            detail=err_msg,
        )


async def get_hub_token() -> dict:
    """Automated method for getting a robot token from the central Hub service."""
    robot_id, robot_secret = (
        hub_adapter_settings.HUB_ROBOT_USER,
        hub_adapter_settings.HUB_ROBOT_SECRET,
    )

    payload = {
        "grant_type": "robot_credentials",
        "id": robot_id,
        "secret": robot_secret,
    }

    if not robot_id or not robot_secret:
        logger.error("Missing robot ID or secret. Check env vars")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided for the hub robot. Check that the environment variables are set properly",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        uuid.UUID(robot_id)

    except ValueError:
        logger.error(f"Invalid robot ID: {robot_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Robot ID is not a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_route = hub_adapter_settings.HUB_AUTH_SERVICE_URL.rstrip("/") + "/token"

    try:
        resp = httpx.post(token_route, data=payload)

    except httpx.ConnectTimeout:
        logger.error("Connection Timeout - Hub is currently unreacheable")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Connection Timeout - Hub is currently unreacheable",  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )

    except httpx.ConnectError:
        err = "Connection Error - Hub is currently unreacheable"
        logger.error(err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if resp.status_code != httpx.codes.OK:
        logger.error(f"Failed to retrieve JWT from Hub - {resp.text}")
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.text,  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = resp.json()
    token = Token(**token_data)
    return {"Authorization": f"Bearer {token.access_token}"}


async def add_hub_jwt(request: Request):
    """Add a Hub JWT to the request header."""
    hub_token = await get_hub_token()
    updated_headers = MutableHeaders(request._headers)
    updated_headers.update(hub_token)
    request._headers = updated_headers
    request.scope.update(headers=request.headers.raw)

    return request
