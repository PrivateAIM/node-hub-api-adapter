"""Handle the authorization and authentication of services."""

import logging
import uuid

import httpx
import jwt
from fastapi import HTTPException, Security
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from flame_hub import CoreClient
from flame_hub._auth_flows import RobotAuth
from jwt import PyJWKClient
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import Token
from hub_adapter.oidc import check_oidc_configs_match, get_svc_oidc_config, get_user_oidc_config

logger = logging.getLogger(__name__)


jwtbearer = HTTPBearer(
    scheme_name="JWT",
    description="Pass a valid JWT here for authentication. Can be obtained from /token endpoint.",
)


class ProxiedPyJWKClient(PyJWKClient):
    """Custom class to override the PyJWKClient to use proxies when available."""

    def __init__(self, url):
        super().__init__(url)

    def fetch_data(self):
        with httpx.Client() as client:
            response = client.get(self.uri)
            response.raise_for_status()
            return response.json()


async def get_hub_public_key() -> dict:
    """Get the central hub service public key."""
    hub_jwks_ep = hub_adapter_settings.HUB_AUTH_SERVICE_URL.rstrip("/") + "/jwks"
    return httpx.get(hub_jwks_ep).json()


async def verify_idp_token(
    token: HTTPAuthorizationCredentials = Security(jwtbearer),
) -> dict:
    """Decode the auth token using keycloak's public key."""
    svc = "Auth"
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Missing or invalid token",
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_oidc_config = get_user_oidc_config()
    svc_oidc_config = get_svc_oidc_config()

    try:
        # Decode just to get issuer
        unverified_claims = jwt.decode(token.credentials, options={"verify_signature": False})
        issuer = unverified_claims.get("iss")

        if hub_adapter_settings.OVERRIDE_JWKS:  # Override the fetched URIs
            jwk_client = ProxiedPyJWKClient(hub_adapter_settings.OVERRIDE_JWKS)
        # If the issuer is the user's OIDC, use the user's public key, otherwise use the node's internal public key
        elif issuer == user_oidc_config.issuer:
            jwk_client = ProxiedPyJWKClient(user_oidc_config.jwks_uri)

        else:
            jwk_client = ProxiedPyJWKClient(svc_oidc_config.jwks_uri)

        signing_key = jwk_client.get_signing_key_from_jwt(token.credentials)

        return jwt.decode(
            token.credentials,
            key=signing_key,
            options={"verify_signature": True, "verify_aud": False, "exp": True},
        )

    except httpx.ConnectError as e:
        err_msg = f"{status.HTTP_404_NOT_FOUND} - {e}"
        if hub_adapter_settings.HTTP_PROXY or hub_adapter_settings.HTTPS_PROXY:
            err_msg += f" - Possibly an issue with the forward proxy: {hub_adapter_settings.HTTP_PROXY}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"{status.HTTP_404_NOT_FOUND} - {err_msg}",
                "service": svc,
                "status_code": status.HTTP_404_NOT_FOUND,
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except jwt.DecodeError as e:
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": f"{status.HTTP_401_UNAUTHORIZED} - {e}",
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except jwt.ExpiredSignatureError:
        err_msg = "Authorization token expired"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": err_msg,
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
        ) from jwt.ExpiredSignatureError

    except jwt.MissingRequiredClaimError:
        err_msg = "Incorrect claims, check the audience and issuer."
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": err_msg,
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
        ) from jwt.MissingRequiredClaimError

    except Exception:
        err_msg = "Unable to parse authentication token"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": err_msg,
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
        ) from Exception


def get_internal_token() -> dict | None:
    """If the Hub Adapter is set up tp use an external IDP, it needs to retrieve a JWT from the internal keycloak
    to make requests to the PO."""
    configs_match, oidc_config = check_oidc_configs_match()

    if not configs_match:
        logger.debug("External IDP different from internal, retrieving JWT from internal keycloak")
        payload = {
            "grant_type": "client_credentials",
            "client_id": hub_adapter_settings.API_CLIENT_ID,
            "client_secret": hub_adapter_settings.API_CLIENT_SECRET,
        }

        with httpx.Client() as client:
            resp = client.post(oidc_config.token_endpoint, data=payload)
            resp.raise_for_status()
            token_data = resp.json()

        token = Token(**token_data)
        return {"Authorization": f"Bearer {token.access_token}"}

    return None


async def add_internal_token_if_missing(request: Request) -> Request:
    """Adds a JWT from the internal IDP is not present in the request."""
    internal_token = get_internal_token()
    if internal_token:
        updated_headers = MutableHeaders(request.headers)
        updated_headers.update(internal_token)
        logger.debug("Added Hub JWT to request headers")
        request._headers = updated_headers
        request.scope.update(headers=request.headers.raw)

    return request


def get_hub_token() -> RobotAuth:
    """Automated method for getting a robot token from the central Hub service."""
    robot_id, robot_secret = (
        hub_adapter_settings.HUB_ROBOT_USER,
        hub_adapter_settings.HUB_ROBOT_SECRET,
    )

    if not robot_id or not robot_secret:
        logger.error("Missing robot ID or secret. Check env vars")
        raise ValueError("Missing Hub robot credentials, check that the environment variables are set properly")

    try:
        uuid.UUID(robot_id)

    except ValueError:
        logger.error(f"Invalid robot ID: {robot_id}")
        raise ValueError(f"Invalid robot ID: {robot_id}") from ValueError

    auth = RobotAuth(
        robot_id=robot_id,
        robot_secret=robot_secret,
        client=httpx.Client(
            base_url=hub_adapter_settings.HUB_AUTH_SERVICE_URL,
        ),
    )
    return auth


hub_robot = get_hub_token()
core_client = CoreClient(
    client=httpx.Client(
        base_url=hub_adapter_settings.HUB_SERVICE_URL,
        auth=hub_robot,
    ),
)
