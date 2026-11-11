"""Handle the authorization and authentication of services."""

import logging
from functools import lru_cache
from typing import Annotated

import httpx2
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import PyJWKClient
from starlette import status

from hub_adapter.conf import Settings
from hub_adapter.dependencies import (
    get_hub_async_client,
    get_idp_client,
    get_settings,
)
from hub_adapter.oidc import get_oidc_config

logger = logging.getLogger(__name__)

jwtbearer = HTTPBearer(
    scheme_name="JWT",
    description="Pass a valid JWT from the IDP for authentication.",
)


class ProxiedPyJWKClient(PyJWKClient):
    """Custom class to override the PyJWKClient to use proxies when available."""

    def fetch_data(self):
        response = get_idp_client().get(self.uri)
        response.raise_for_status()
        jwk_set = response.json()

        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(jwk_set)

        return jwk_set


@lru_cache(maxsize=4)
def get_jwk_client(jwks_uri: str) -> ProxiedPyJWKClient:
    """Return the JWK client for a JWKS URI, reusing it across requests."""
    return ProxiedPyJWKClient(jwks_uri)


async def get_hub_public_key(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get the central hub service public key."""
    hub_jwks_ep = settings.hub_auth_service_url.rstrip("/") + "/jwks"
    resp = await get_hub_async_client().get(hub_jwks_ep)
    return resp.json()


async def verify_idp_token(
    settings: Annotated[Settings, Depends(get_settings)],
    token: HTTPAuthorizationCredentials | None = Security(jwtbearer),
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

    try:
        jwks_uri = settings.override_jwks or get_oidc_config().jwks_uri
        jwk_client = get_jwk_client(jwks_uri)

        signing_key = jwk_client.get_signing_key_from_jwt(token.credentials)

        return jwt.decode(
            token.credentials,
            key=signing_key,
            options={"verify_signature": True, "verify_aud": False, "exp": True},
        )

    except httpx2.ConnectError as e:
        err_msg = f"{status.HTTP_404_NOT_FOUND} - {e}"
        if settings.http_proxy or settings.https_proxy:
            err_msg += f" - Possibly an issue with the forward proxy: {settings.http_proxy}"
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

    except Exception as e:
        err_msg = "Unable to parse authentication token"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": err_msg,
                "service": svc,
                "status_code": status.HTTP_401_UNAUTHORIZED,
            },
        ) from Exception


# RBAC dependencies
def _require_role(
    additional_allowed_role: str | None,
    verified_token: Annotated[dict, Depends(verify_idp_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Dependency to check if token contains the allowed role, otherwise raise 403 error."""
    role_claim_name = settings.role_claim_name
    admin_role = settings.admin_role
    if additional_allowed_role and role_claim_name:
        logger.debug(f"Role claim name and specified role '{role_claim_name}' found. Verifying role in token.")
        role_claim_keys = role_claim_name.split(".")

        has_allowed_role = False
        parsed_claim = verified_token  # Initialize with token data to begin recursive parsing
        for key in role_claim_keys:
            parsed_claim = parsed_claim.get(key, {})

        if not parsed_claim:
            logger.warning(f"No roles found in token using {role_claim_name}")

        if isinstance(parsed_claim, str):
            parsed_claim = [parsed_claim]

        if admin_role in parsed_claim or additional_allowed_role in parsed_claim:
            has_allowed_role = True

        if not has_allowed_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": f"Insufficient permissions, admin or {additional_allowed_role} role not found in token.",
                    "service": "Auth",
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )

    return verified_token


async def require_steward_role(
    verified_token: Annotated[dict, Depends(verify_idp_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Dependency to check if the user has the ADMIN_ROLE or STEWARD_ROLE."""
    steward_role = settings.steward_role
    return _require_role(steward_role, verified_token, settings)


async def require_researcher_role(
    verified_token: Annotated[dict, Depends(verify_idp_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Dependency to check if the user has the ADMIN_ROLE or RESEARCHER_ROLE."""
    researcher_role = settings.researcher_role
    return _require_role(researcher_role, verified_token, settings)


async def require_admin_role(
    verified_token: Annotated[dict, Depends(verify_idp_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Dependency to check if the user has the ADMIN_ROLE."""
    role_claim_name = settings.role_claim_name
    admin_role = settings.admin_role

    if not role_claim_name:
        return verified_token

    if not admin_role:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Insufficient permissions, admin role not found in token or not configured.",
                "service": "Auth",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
        )

    if role_claim_name:
        role_claim_keys = role_claim_name.split(".")
        parsed_claim = verified_token
        for key in role_claim_keys:
            parsed_claim = parsed_claim.get(key, {})
        if not parsed_claim:
            logger.warning(f"No roles found in token using {role_claim_name}")
        if isinstance(parsed_claim, str):
            parsed_claim = [parsed_claim]
        if admin_role not in parsed_claim:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Insufficient permissions, admin role not found in token.",
                    "service": "Auth",
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
            )
    return verified_token
