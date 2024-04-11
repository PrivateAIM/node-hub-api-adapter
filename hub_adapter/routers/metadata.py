"""EPs for various metadata for the frontend."""

from fastapi import APIRouter

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.conf import KeycloakConfig
from hub_adapter.models.podorc import ImageDataResponse

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
        "clientId": "node-ui-app",
    }


@metadata_router.get("/metadata/version")
async def get_node_version():
    """Return version of the node software/API."""
    # TODO: move version definition to frontend
    return {"appVersion": "0.1.0-gatewayapi"}


@metadata_router.get("/vault/status")
async def get_vault_status():
    """Spoof vault status."""
    dummy_data = {
        "initialized": True,
        "sealed": False,
        "authenticated": True,
        "config": {
            "stationID": "4c0e4a1a-795b",
            "stationName": "Test FLAME Node Central",
        }
    }
    return dummy_data


@metadata_router.get("/hub/images", response_model=ImageDataResponse)
async def get_images():
    """Return list of images for the frontend."""
    # TODO: replace with data from https://api.privateaim.net/master-images

    dummy_data = {
        "pullImages": [
            {
                "id": "59081687-3dfe-46cf-afb5-07c562a002af",
                "train_class_id": "choochoo",
                "repo_tag": "0.5.23-pull",
                "job_id": "49e79b47-686b-4fb8-9259-fd0035b0b7f6",
                "status": "pulled"
            }
        ],
        "pushImages": [
            {
                "id": "4a941577-46ce-4220-8ca0-181cf45abe29",
                "train_class_id": "choochoo",
                "repo_tag": "latest",
                "job_id": "5efabb71-ba5d-4d00-9ed4-f27eb6a52e8f",
                "status": "waiting_to_push"
            }
        ],
    }
    return dummy_data
