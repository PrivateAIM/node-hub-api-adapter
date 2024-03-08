"""Handle the authorization and authentication of services."""
from urllib.parse import urljoin

import requests
from fastapi import Security, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from jose import jwt, JOSEError
from starlette import status

from gateway.conf import gateway_settings
from gateway.models import AuthConfiguration

IDP_ISSUER_URL = urljoin(gateway_settings.IDP_URL, "/".join(["realms", gateway_settings.IDP_REALM]))

# IDP i.e. Keycloak
realm_idp_settings = AuthConfiguration(
    server_url=gateway_settings.IDP_URL,
    # Take last part of issuer URL for realm
    realm=gateway_settings.IDP_REALM,
    client_id=gateway_settings.UI_CLIENT_ID,
    client_secret=gateway_settings.UI_CLIENT_SECRET,
    authorization_url=IDP_ISSUER_URL + "/protocol/openid-connect/auth",
    token_url=IDP_ISSUER_URL + "/protocol/openid-connect/token",
    issuer_url=IDP_ISSUER_URL,
)

realm_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=realm_idp_settings.authorization_url,
    tokenUrl=realm_idp_settings.token_url,
)

hub_oauth2_scheme = OAuth2PasswordBearer(
    # authorizationUrl=gateway_settings.HUB_AUTH_SERVICE_URL + "/authorize",
    tokenUrl=gateway_settings.HUB_AUTH_SERVICE_URL + "/token",
)


# Debugging methods
async def get_idp_public_key() -> str:
    """Get the public key."""
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{requests.get(realm_idp_settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
    )


async def verify_realm_idp_token(token: str = Security(realm_oauth2_scheme)) -> dict:
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

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail='Authorization token expired')

    except jwt.JWTClaimsError:
        raise HTTPException(
            status_code=401,
            detail='Incorrect claims, check the audience and issuer.')

    except Exception:
        raise HTTPException(
            status_code=401,
            detail='Unable to parse authentication token')


async def get_hub_token():
    """Get a JWT from the Hub."""
    resp = requests.post(
        gateway_settings.HUB_AUTH_SERVICE_URL + "/token",
        data={"username": "admin", "password": "start123"}
    )
    token_data = resp.json()
    return token_data
