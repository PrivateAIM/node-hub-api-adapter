"""EPs for Hub provided information."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Security, Query, Body, Path
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from gateway.auth import hub_oauth2_scheme
from gateway.conf import gateway_settings
from gateway.core import route
from gateway.models import ImageDataResponse, ContainerResponse, Project, AllProjects, \
    ApprovalStatus, AnalysisOrProjectNode, ListAnalysisNodes, ListAnalysisOrProjectNodes

hub_router = APIRouter(
    dependencies=[Security(hub_oauth2_scheme)],
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


@route(
    request_method=hub_router.get,
    path="/projects",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.HUB_SERVICE_URL,
    response_model=AllProjects,
    query_params=["filter_id", "filter_realm_id", "filter_user_id", "include"],
)
async def list_all_projects(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data. Can only be 'master_image' or null",
                pattern="^master_image$",  # Must be "master_image",
            ),
        ] = None,
        filter_id: Annotated[uuid.UUID, Query(description="Filter by object UUID.")] = None,
        filter_realm_id: Annotated[uuid.UUID, Query(description="Filter by realm UUID.")] = None,
        filter_user_id: Annotated[uuid.UUID, Query(description="Filter by user UUID.")] = None,
):
    """List all projects."""
    pass


@route(
    request_method=hub_router.get,
    path="/projects/{project_id}",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.HUB_SERVICE_URL,
    response_model=Project,
)
async def list_specific_project(
        project_id: Annotated[uuid.UUID, Path(description="Project UUID.")],
        request: Request,
        response: Response,
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.get,
    path="/project-nodes",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.HUB_SERVICE_URL,
    response_model=ListAnalysisOrProjectNodes,
    query_params=["filter_id", "filter_approval_status", "filter_project_id", "filter_project_realm_id",
                  "filter_node_id", "filter_node_realm_id"],
)
async def list_project_node(
        request: Request,
        response: Response,
        filter_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by ID of returned object.",
            ),
        ] = None,
        filter_approval_status: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by approval status of project.",
            ),
        ] = None,
        filter_project_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by project UUID.",
            ),
        ] = None,
        filter_project_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by project realm UUID.",
            ),
        ] = None,
        filter_node_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by node UUID.",
            ),
        ] = None,
        filter_node_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by node realm UUID.",
            ),
        ] = None,
):
    """List project for a node."""
    pass


@route(
    request_method=hub_router.post,
    path="/project-nodes",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.HUB_SERVICE_URL,
    response_model=AnalysisOrProjectNode,
    body_params=["project_id", "node_id"],
    query_params=["approval_status"],
)
async def create_project_node(
        request: Request,
        response: Response,
        project_id: Annotated[uuid.UUID, Body(description="Project ID as UUID")],
        node_id: Annotated[uuid.UUID, Body(description="Node ID as UUID")],
        approval_status: Annotated[ApprovalStatus, Query(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        )],
):
    """Create a project at a specific node and set the approval status."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-nodes",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.HUB_SERVICE_URL,
    response_model=ListAnalysisNodes,
    query_params=["filter_id", "filter_approval_status", "filter_project_id", "filter_project_realm_id",
                  "filter_node_id", "filter_node_realm_id", "include"],
)
async def list_analyses_of_node(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter",
                pattern="^node$",  # Must be "node",
            ),
        ] = None,
        filter_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by ID of returned object.",
            ),
        ] = None,
        filter_approval_status: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by approval status of project.",
            ),
        ] = None,
        filter_project_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by project UUID.",
            ),
        ] = None,
        filter_project_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by project realm UUID.",
            ),
        ] = None,
        filter_node_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by node UUID.",
            ),
        ] = None,
        filter_node_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by node realm UUID.",
            ),
        ] = None,
        filter_analysis_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis UUID.",
            ),
        ] = None,
        filter_analysis_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis realm UUID.",
            ),
        ] = None,
):
    """List analyses for a node."""
    pass
