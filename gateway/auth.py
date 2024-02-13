import requests
from fastapi import Security, HTTPException, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JOSEError
from starlette import status

from models import AuthConfiguration, User

settings = AuthConfiguration(
    server_url="http://localhost:8080",
    realm="flame",
    client_id="test-client",
    client_secret="lhjYYgU5e1GQtfrs3YsTiESGpzqE8YSb",
    authorization_url="http://localhost:8080/realms/flame/protocol/openid-connect/auth",
    token_url="http://localhost:8080/realms/flame/protocol/openid-connect/token",
    issuer_url="http://localhost:8080/realms/flame",
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.authorization_url,
    tokenUrl=settings.token_url,
)


async def get_idp_public_key() -> str:
    """Get the public key."""
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{requests.get(settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
    )


# Get the payload/token from keycloak
async def get_payload(token: str = Security(oauth2_scheme)) -> dict:
    """Return the full auth token."""
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


# Get user info from the payload
async def get_user_info(payload: dict = Depends(get_payload)) -> User:
    """Return User info."""
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
