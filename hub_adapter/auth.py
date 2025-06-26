"""Handle the authorization and authentication of services."""

import logging
import time
import uuid
from functools import lru_cache

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

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import OIDCConfiguration

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
        with httpx.Client(mounts=hub_adapter_settings.PROXY_MOUNTS) as client:
            response = client.get(self.uri)
            response.raise_for_status()
            return response.json()


@lru_cache(maxsize=2)
def fetch_openid_config(oidc_url: str, max_retries: int = 6, bypass_proxy: bool = False) -> OIDCConfiguration:
    """Fetch the openid configuration from the OIDC URL. Tries until it reaches max_retries."""
    provided_url = oidc_url
    if not oidc_url.endswith(".well-known/openid-configuration"):
        oidc_url = oidc_url.rstrip("/") + "/.well-known/openid-configuration"

    response = {}
    attempt_num = 0
    while attempt_num <= max_retries:
        try:
            if bypass_proxy:  # For internal k8s/containerized communications
                response = httpx.get(oidc_url)

            else:
                with httpx.Client(mounts=hub_adapter_settings.PROXY_MOUNTS) as client:
                    response = client.get(oidc_url)

            response.raise_for_status()
            oidc_config = response.json()
            return OIDCConfiguration(**oidc_config)

        except (httpx.ConnectError, httpx.ReadTimeout):  # OIDC Service not up yet
            attempt_num += 1
            wait_time = 10 * (2 ** (attempt_num - 1))  # 10s, 20s, 40s, 80s, 160s, 320s
            logger.warning(f"Unable to contact the IDP at {oidc_url}, retrying in {wait_time} seconds")
            time.sleep(wait_time)

        except httpx.HTTPStatusError as e:
            err_msg = (
                f"HTTP error occurred while trying to contact the IDP: {provided_url}, is this the correct issuer URL?"
            )
            logger.error(err_msg + f" - {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Auth",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            ) from e

    logger.error(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")
    raise httpx.ConnectError(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")


def get_user_oidc_config() -> OIDCConfiguration:
    """Lazy-load the user OIDC configuration when first needed."""
    return fetch_openid_config(hub_adapter_settings.IDP_URL)


def get_svc_oidc_config() -> OIDCConfiguration:
    """Lazy-load the service OIDC configuration when first needed."""
    if hub_adapter_settings.NODE_SVC_OIDC_URL != hub_adapter_settings.IDP_URL:
        return fetch_openid_config(
            hub_adapter_settings.NODE_SVC_OIDC_URL, bypass_proxy=hub_adapter_settings.STRICT_INTERNAL
        )
    else:
        return get_user_oidc_config()


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
        if hub_adapter_settings.PROXY_MOUNTS:
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
            base_url=hub_adapter_settings.HUB_AUTH_SERVICE_URL, mounts=hub_adapter_settings.PROXY_MOUNTS
        ),
    )
    return auth


hub_robot = get_hub_token()
core_client = CoreClient(
    client=httpx.Client(
        base_url=hub_adapter_settings.HUB_SERVICE_URL, mounts=hub_adapter_settings.PROXY_MOUNTS, auth=hub_robot
    ),
)
