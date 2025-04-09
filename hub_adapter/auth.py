"""Handle the authorization and authentication of services."""

import logging
import uuid

import httpx
from fastapi import HTTPException, Security
from fastapi.security import (
    HTTPBearer,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
)
from flame_hub import CoreClient
from flame_hub._auth_flows import RobotAuth
from jose import ExpiredSignatureError, JOSEError, jwt
from jose.exceptions import JWTClaimsError
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import AuthConfiguration

logger = logging.getLogger(__name__)

IDP_ISSUER_URL = (
    hub_adapter_settings.IDP_URL.rstrip("/")
    + "/"
    + "/".join(["realms", hub_adapter_settings.IDP_REALM])
)

# IDP i.e. Keycloak
realm_idp_settings = AuthConfiguration(
    server_url=hub_adapter_settings.IDP_URL,
    realm=hub_adapter_settings.IDP_REALM,
    client_id=hub_adapter_settings.API_CLIENT_ID,
    client_secret=hub_adapter_settings.API_CLIENT_SECRET,
    authorization_url=IDP_ISSUER_URL + "/protocol/openid-connect/auth",
    token_url=IDP_ISSUER_URL + "/protocol/openid-connect/token",
    user_info=IDP_ISSUER_URL + "/protocol/openid-connect/userinfo",
    issuer_url=IDP_ISSUER_URL,
)

idp_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=realm_idp_settings.authorization_url,
    tokenUrl=realm_idp_settings.token_url,
)

idp_oauth2_scheme_pass = OAuth2PasswordBearer(tokenUrl=realm_idp_settings.token_url)

httpbearer = HTTPBearer(
    scheme_name="JWT",
    description="Pass a valid JWT here for authentication. Can be obtained from /token endpoint.",
)


# Debugging methods
async def get_idp_public_key() -> str:
    """Get the IDP public key."""
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{httpx.get(realm_idp_settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
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
            detail=str("Missing or invalid token"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return jwt.decode(
            token,
            key=await get_idp_public_key(),
            options={"verify_signature": True, "verify_aud": False, "exp": True},
        )

    except JOSEError as e:
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )

    except ExpiredSignatureError:
        err_msg = "Authorization token expired"
        logger.error(f"{status.HTTP_401_UNAUTHORIZED} - {err_msg}")
        raise HTTPException(status_code=401, detail=err_msg)

    except JWTClaimsError:
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


def get_hub_token() -> RobotAuth:
    """Automated method for getting a robot token from the central Hub service."""
    robot_id, robot_secret = (
        hub_adapter_settings.HUB_ROBOT_USER,
        hub_adapter_settings.HUB_ROBOT_SECRET,
    )

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

    # try:
    auth = RobotAuth(robot_id=robot_id, robot_secret=robot_secret)

    # except HubAPIError as err:
    #     httpx_error = err.error_response
    #
    #     if type(httpx_error) is httpx.ConnectTimeout:
    #         logger.error("Connection Timeout - Hub is currently unreachable")
    #         raise HTTPException(
    #             status_code=status.HTTP_408_REQUEST_TIMEOUT,
    #             detail="Connection Timeout - Hub is currently unreacheable",  # Invalid authentication credentials
    #             headers={"WWW-Authenticate": "Bearer"},
    #         )
    #
    #     elif type(httpx_error) is httpx.ConnectError:
    #         err = "Connection Error - Hub is currently unreachable"
    #         logger.error(err)
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail=err,
    #             headers={"WWW-Authenticate": "Bearer"},
    #         )
    #
    #     else:
    #         logger.error("Failed to retrieve JWT from Hub")
    #         raise HTTPException(
    #             status_code=err.error_response.status_code,
    #             detail=err.error_response.message,  # Invalid authentication credentials
    #             headers={"WWW-Authenticate": "Bearer"},
    #         )

    return auth


async def add_hub_jwt(request: Request):
    """Add a Hub JWT to the request header."""
    hub_token = await get_hub_token()
    updated_headers = MutableHeaders(request._headers)
    updated_headers.update(hub_token)
    request._headers = updated_headers
    request.scope.update(headers=request.headers.raw)

    return request


hub_robot = get_hub_token()
core_client = CoreClient(auth=hub_robot)
