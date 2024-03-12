"""EPs for various metadata for the frontend."""

from fastapi import APIRouter

from gateway.conf import gateway_settings
from gateway.models.conf import KeycloakConfig

metadata_router = APIRouter(
    # dependencies=[Security(oauth2_scheme)],
    tags=["Metadata"],
    responses={404: {"description": "Not found"}},
)


@metadata_router.get("/metadata/keycloakConfig", response_model=KeycloakConfig)
async def get_keycloak_config():
    """Return keycloak metadata for the frontend."""
    return {
        "realm": gateway_settings.IDP_REALM,
        "url": gateway_settings.IDP_URL,
        "clientId": "node-ui-app",
    }


@metadata_router.get("/metadata/version")
async def get_node_version():
    """Return version of the node software/API."""
    # TODO: move version definition to frontend
    return {"appVersion": "0.1.0-gatewayapi"}
