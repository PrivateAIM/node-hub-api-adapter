"""EPs for Hub provided information."""
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Query, Path, Depends, HTTPException
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.constants import NODE, REGISTRY_PROJECT_ID, EXTERNAL_NAME, HOST, ID, REGISTRY
from hub_adapter.core import route
from hub_adapter.models.hub import Project, AllProjects, ApprovalStatus, AnalysisOrProjectNode, \
    ListAnalysisOrProjectNodes, \
    AnalysisNode, ListAnalysisNodes, RegistryProject, AnalysisImageUrl

hub_router = APIRouter(
    # dependencies=[Security(verify_idp_token), Depends(add_hub_jwt), Security(idp_oauth2_scheme_pass),
    #               Security(httpbearer)],
    # dependencies=[Depends(add_hub_jwt)],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)


# @hub_router.get("/hub/images", response_model=ImageDataResponse)
# async def get_images():
#     """Return list of images for the frontend."""
#     # TODO: replace with data from https://api.privateaim.net/master-images
#
#     dummy_data = {
#         "pullImages": [
#             {
#                 "id": "59081687-3dfe-46cf-afb5-07c562a002af",
#                 "train_class_id": "choochoo",
#                 "repo_tag": "0.5.23-pull",
#                 "job_id": "49e79b47-686b-4fb8-9259-fd0035b0b7f6",
#                 "status": "pulled"
#             }
#         ],
#         "pushImages": [
#             {
#                 "id": "4a941577-46ce-4220-8ca0-181cf45abe29",
#                 "train_class_id": "choochoo",
#                 "repo_tag": "latest",
#                 "job_id": "5efabb71-ba5d-4d00-9ed4-f27eb6a52e8f",
#                 "status": "waiting_to_push"
#             }
#         ],
#     }
#     return dummy_data
#
#
# @hub_router.get("/hub/vault/status")
# async def get_vault_status():
#     """Spoof vault status."""
#     dummy_data = {
#         "initialized": True,
#         "sealed": False,
#         "authenticated": True,
#         "config": {
#             "stationID": "4c0e4a1a-795b",
#             "stationName": "Test FLAME Node Central",
#         }
#     }
#     return dummy_data


@route(
    request_method=hub_router.get,
    path="/projects",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
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
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
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
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ListAnalysisOrProjectNodes,
    query_params=["filter_id", "filter_project_id", "filter_project_realm_id",
                  "filter_node_id", "filter_node_realm_id"],
)
async def list_projects_and_nodes(
        request: Request,
        response: Response,
        filter_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by ID of returned object.",
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
    path="/project-nodes/{project_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AnalysisOrProjectNode,
    body_params=["approval_status"],
)
async def accept_reject_project_node(
        request: Request,
        response: Response,
        project_id: Annotated[uuid.UUID, Path(description="Project object UUID (not project ID).")],
        approval_status: Annotated[ApprovalStatus, Query(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        )],
):
    """Set the approval status of a project."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-nodes",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ListAnalysisNodes,
    query_params=["filter_id", "filter_project_id", "filter_project_realm_id",
                  "filter_node_id", "filter_node_realm_id", "include"],
    # post_processing_func="parse_containers",  # Create new EP for getting containers
)
async def list_analyses_of_nodes(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Can only be 'node'/'analysis'",
                pattern="^(node|analysis)$",  # Must be "node" or "analysis" or null,
            ),
        ] = "analysis",
        filter_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by ID of returned object.",
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


@route(
    request_method=hub_router.get,
    path="/analysis-nodes/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AnalysisNode,
    query_params=["include"],
)
async def list_specific_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID, Path(description="Analysis UUID.")],
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Can only be 'node'/'analysis'",
                pattern="^((^|[,])(analysis|node))+$",  # Must be "node" or "analysis" or null,
            ),
        ] = "analysis",
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.post,
    path="/analysis-nodes/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AnalysisNode,
    body_params=["approval_status"],
)
async def accept_reject_analysis_node(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID, Path(description="Analysis object UUID (not analysis_id).")],
        approval_status: Annotated[ApprovalStatus, Query(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        )],
):
    """Set the approval status of a analysis."""
    pass


@route(
    request_method=hub_router.get,
    path="/registry-projects/{registry_project_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=RegistryProject,
    query_params=["include"],
)
async def get_registry_metadata_for_project(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional registry data. Can only be 'registry'",
                pattern="^registry$",  # Must be "registry" or null,
            ),
        ] = REGISTRY,
):
    """List registry data for a project."""
    pass


def get_analysis_metadata_for_url(
        request: Request,
        analysis_id: uuid.UUID = Path(description="UUID of analysis."),
):
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    headers = {k: v for k, v in request.headers.items() if k != HOST}
    analysis_url = hub_adapter_settings.HUB_SERVICE_URL + f"/analysis-nodes/{analysis_id}?include=analysis,node"
    analysis_resp = httpx.get(analysis_url, headers=headers)
    analysis_metadata = analysis_resp.json()

    if analysis_resp.status_code == status.HTTP_404_NOT_FOUND:
        analysis_metadata["message"] = "UUID not found"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analysis_metadata,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if NODE not in analysis_metadata or not analysis_metadata[NODE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No node associated with analysis UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if REGISTRY_PROJECT_ID not in analysis_metadata[NODE] or not analysis_metadata[NODE][REGISTRY_PROJECT_ID]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registry associated with node for the analysis UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return analysis_metadata, headers


def get_registry_metadata_for_url(
        analysis_results: dict = Depends(get_analysis_metadata_for_url)
):
    """Get registry metadata for a given UUID to be used in creating analysis image URL."""
    analysis_metadata, headers = analysis_results
    registry_project_id = analysis_metadata[NODE][REGISTRY_PROJECT_ID]

    registry_url_prefix = hub_adapter_settings.HUB_SERVICE_URL + f"/registry-projects/{registry_project_id}"
    registry_url = registry_url_prefix + "?include=registry&fields=+account_id,+account_name,+account_secret"
    registry_resp = httpx.get(registry_url, headers=headers)
    registry_metadata = registry_resp.json()

    if registry_resp.status_code == status.HTTP_404_NOT_FOUND:
        registry_metadata["message"] = "Registry Project UUID not found"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=registry_metadata,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if EXTERNAL_NAME not in registry_metadata or not registry_metadata[EXTERNAL_NAME]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No external name for node",
            headers={"WWW-Authenticate": "Bearer"},
        )

    node_external_name = registry_metadata[EXTERNAL_NAME]

    if REGISTRY not in registry_metadata or HOST not in registry_metadata[REGISTRY]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No registry is associated with node {node_external_name}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    host = registry_metadata[REGISTRY][HOST]

    return host, node_external_name, analysis_metadata[ID]


@hub_router.get("/analysis/image/{analysis_id}", response_model=AnalysisImageUrl)
async def get_analysis_image_url(
        compiled_info: tuple = Depends(get_registry_metadata_for_url),
) -> dict:
    """Build an analysis image URL using its metadata from the Hub."""
    host, node_external_name, analysis_id = compiled_info
    compiled_url = {"image_url": f"{host}/{node_external_name}/{analysis_id}"}
    return compiled_url
