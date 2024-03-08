"""EPs for Hub provided information."""

from fastapi import APIRouter

from gateway.models import ImageDataResponse, ContainerResponse

hub_router = APIRouter(
    # dependencies=[Security(oauth2_scheme)],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)


@hub_router.get("/hub/images", response_model=ImageDataResponse)
async def get_images():
    """Return list of images for the frontend."""
    # TODO: replace with data from https://api.privateaim.net/projects
    # TODO: add project specific call / filter?

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


@hub_router.get("/hub/containers", response_model=ContainerResponse)
async def get_containers():
    """Return list of containers for the frontend."""
    # TODO: replace with data from https://api.privateaim.net/analysis-nodes
    # TODO: add project specific call / filter?
    dummy_data = {
        "containers": [
            {
                "id": "d730b955-c476-40db-9dd1-5ea6b1cfe5bc",
                "name": "FooBar",
                "job_id": "4c0e4a1a-795b-4a23-a7ef-0a2473bcb670",
                "image": "4a941577-46ce-4220-8ca0-181cf45abe29",
                "state": "Running",
                "status": "Active",
                "next_tag": "Köln",
                "repo": "/data",
                "train_class_id": "choochoo",
            }
        ]
    }
    return dummy_data


@hub_router.get("/hub/vault/status")
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
