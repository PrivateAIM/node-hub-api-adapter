"""Handle the authorization and authentication of services."""
from urllib.parse import urljoin

import requests
from fastapi import Security, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JOSEError
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from gateway.conf import gateway_settings
from gateway.models.conf import AuthConfiguration, Token

IDP_ISSUER_URL = urljoin(gateway_settings.IDP_URL, "/".join(["realms", gateway_settings.IDP_REALM]))

# IDP i.e. Keycloak
realm_idp_settings = AuthConfiguration(
    server_url=gateway_settings.IDP_URL,
    realm=gateway_settings.IDP_REALM,
    client_id=gateway_settings.API_CLIENT_ID,
    client_secret=gateway_settings.API_CLIENT_SECRET,
    authorization_url=IDP_ISSUER_URL + "/protocol/openid-connect/auth",
    token_url=IDP_ISSUER_URL + "/protocol/openid-connect/token",
    issuer_url=IDP_ISSUER_URL,
)

idp_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=realm_idp_settings.authorization_url,
    tokenUrl=realm_idp_settings.token_url,
)


# Debugging methods
async def get_idp_public_key() -> str:
    """Get the IDP public key."""
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{requests.get(realm_idp_settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
    )


async def get_hub_public_key() -> dict:
    """Get the central hub service public key."""
    hub_jwks_ep = urljoin(gateway_settings.HUB_AUTH_SERVICE_URL, "/jwks")
    return requests.get(hub_jwks_ep).json()


async def verify_idp_token(token: str = Security(idp_oauth2_scheme)) -> dict:
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


async def get_hub_token() -> dict:
    """Automated method for getting a token from the central Hub service."""
    hub_user, hub_pwd = gateway_settings.HUB_USERNAME, gateway_settings.HUB_PASSWORD
    payload = {"username": hub_user, "password": hub_pwd}
    token_route = urljoin(gateway_settings.HUB_AUTH_SERVICE_URL, "/token")
    resp = requests.post(token_route, data=payload)

    if not resp.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=resp.json(),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    token = Token(**token_data)
    # return {b"Authorization": bytes(bearer.encode())}
    return {"Authorization": f"Bearer {token.access_token}"}


async def add_hub_jwt(request: Request):
    """Add a Hub JWT to the request header."""
    hub_token = await get_hub_token()
    updated_headers = MutableHeaders(request._headers)
    updated_headers.update(hub_token)
    request._headers = updated_headers
    request.scope.update(headers=request.headers.raw)

    return request
