"""Handle the authorization and authentication of services."""
from urllib.parse import urljoin

import requests
from fastapi import Security, HTTPException, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JOSEError
from starlette import status

from gateway.conf import gateway_settings
from gateway.models import AuthConfiguration, User

IDP_ISSUER_URL = urljoin(gateway_settings.IDP_URL, "/".join(["realms", gateway_settings.IDP_REALM]))

# IDP i.e. Keycloak
idp_settings = AuthConfiguration(
    server_url=gateway_settings.IDP_URL,
    # Take last part of issuer URL for realm
    realm=gateway_settings.IDP_REALM,
    client_id=gateway_settings.UI_CLIENT_ID,
    client_secret=gateway_settings.UI_CLIENT_SECRET,
    authorization_url=IDP_ISSUER_URL + "/protocol/openid-connect/auth",
    token_url=IDP_ISSUER_URL + "/protocol/openid-connect/token",
    issuer_url=IDP_ISSUER_URL,
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=idp_settings.authorization_url,
    tokenUrl=idp_settings.token_url,
)


# Debugging methods
async def get_idp_public_key() -> str:
    """Get the public key."""
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{requests.get(idp_settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
    )


async def get_token(token: str = Security(oauth2_scheme)) -> dict:
    """Decode the auth token using keycloak's public key."""
    try:
        return jwt.decode(
            token,
            key=await get_idp_public_key(),
            options={"verify_signature": True, "verify_aud": False, "exp": True},
        )

    except JOSEError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_info(payload: dict = Depends(get_token)) -> User:
    """Return User info from the IDP. Mostly for debugging."""
    try:
        return User(
            id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            first_name=payload.get("given_name"),
            last_name=payload.get("family_name"),
            realm_roles=payload.get("realm_access", {}).get("roles", []),
            client_roles=payload.get("realm_access", {}).get("roles", []),
        )

    except JOSEError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
