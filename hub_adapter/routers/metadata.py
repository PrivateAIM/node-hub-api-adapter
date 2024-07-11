"""EPs for various metadata for the frontend."""

from fastapi import APIRouter

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import KeycloakConfig

metadata_router = APIRouter(
    # dependencies=[Security(oauth2_scheme)],
    tags=["Metadata"],
    responses={404: {"description": "Not found"}},
)


@metadata_router.get("/metadata/keycloakConfig", response_model=KeycloakConfig)
async def get_keycloak_config():
    """Return keycloak metadata for the frontend."""
    return {
        "realm": hub_adapter_settings.IDP_REALM,
        "url": hub_adapter_settings.IDP_URL,
        "clientId": "node-ui",
    }
