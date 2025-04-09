"""EPs for Hub provided information."""

import logging
import pickle
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, Form, HTTPException, Path, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter import node_id_pickle_path
from hub_adapter.auth import (
    httpbearer,
    idp_oauth2_scheme_pass,
    verify_idp_token,
)
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.constants import (
    ACCOUNT_NAME,
    ACCOUNT_SECRET,
    CONTENT_LENGTH,
    EXTERNAL_NAME,
    HOST,
    REGISTRY,
    REGISTRY_PROJECT_ID,
)
from hub_adapter.core import route
from hub_adapter.models.hub import (
    AllAnalyses,
    Analysis,
    AnalysisImageUrl,
    AnalysisNode,
    ApprovalStatus,
    Bucket,
    BucketList,
    DetailedAnalysis,
    ListAnalysisNodes,
    ListProjectNodes,
    PartialAnalysisBucketFile,
    PartialBucketFilesList,
    Project,
    ProjectNode,
    RegistryProject,
)

from hub_adapter.auth import core_client, hub_robot

hub_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(idp_oauth2_scheme_pass),
        Security(httpbearer),
        # Depends(add_hub_jwt),
    ],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


async def get_node_id(debug: bool = False) -> str | None:
    """Uses the robot ID to obtain the associated node ID, sets it in the env vars, and returns it.

    An empty string node_id indicates no node is associated with provided robot username.

    If None is returned, no filtering will be applied which is useful for debugging.
    """
    if debug:
        return None

    robot_id = hub_adapter_settings.HUB_ROBOT_USER

    node_cache = {}
    if node_id_pickle_path.is_file():
        with open(node_id_pickle_path, "rb") as f:
            node_cache = pickle.load(f)

    # Returns None if key not in dict or '' if no Node ID was found
    # Need to default to an intentionally wrong nodeId if nothing found otherwise Hub will return all resources

    node_id = node_cache.get(robot_id) or "nothingFound"

    if (
        robot_id not in node_cache
    ):  # Node ID may be None since not every robot is associated with a node
        logger.info("NODE_ID not set for ROBOT_USER, retrieving from Hub")

        hub_auth_header = hub_robot._current_token

        robot_id = hub_adapter_settings.HUB_ROBOT_USER
        core_url = hub_adapter_settings.HUB_SERVICE_URL.rstrip("/")
        node_id_resp = httpx.get(
            f"{core_url}/nodes?filter[robot_id]={robot_id}&fields=id",
            headers=hub_auth_header,
        )

        node_id_resp.raise_for_status()
        node_data = node_id_resp.json()["data"]

        node_id = node_data[0]["id"] if node_data else ""
        node_cache[robot_id] = node_id

        with open(node_id_pickle_path, "wb") as f:
            pickle.dump(node_cache, f)

    return node_id


# TODO make sure a node filter is being applied to project-nodes and analysis-nodes calls
def add_node_id_filter(request: Request, node_id: Annotated[str, Depends(get_node_id)]):
    """Middleware to add node_id filter query param to the request to limit response if node_id is found."""
    if node_id:  # Not an empty string
        query_ps = {k: v for k, v in request.query_params.items()}
        query_ps["filter[node_id]"] = node_id
        request._query_params = query_ps

    return request


@hub_router.get(
    "/projects",
    summary="List all of the projects",
    status_code=status.HTTP_200_OK,
    # response_model=AllProjects,
)
async def list_all_projects():
    """List all projects."""
    return core_client.get_projects()


@hub_router.get(
    "/projects/{project_id}",
    summary="List a specific project",
    status_code=status.HTTP_200_OK,
    # response_model=Project,
)
async def list_specific_project(
    project_id: Annotated[uuid.UUID, Path(description="Project UUID.")],
):
    """List project for a given UUID."""
    return core_client.get_project(project_id=project_id)


@hub_router.get(
    "/project-nodes",
    summary="List all of the project proposals",
    status_code=status.HTTP_200_OK,
    # response_model=ListProjectNodes,
)
async def list_project_proposals():
    """List project proposals."""
    return core_client.get_project_nodes()


@hub_router.get(
    "/project-nodes/{project_node_id}",
    summary="List a specific project proposal",
    status_code=status.HTTP_200_OK,
    # response_model=ProjectNode,
)
async def list_project_proposal(
    project_node_id: Annotated[uuid.UUID, Path(description="Proposal object UUID.")],
):
    """Set the approval status of a project proposal."""
    return core_client.get_project_node(project_node_id=project_node_id)


@hub_router.post(
    "/project-nodes/{project_node_id}",
    summary="Update a specific project proposal",
    status_code=status.HTTP_200_OK,
    # response_model=ProjectNode,
)
async def accept_reject_project_proposal(
    project_node_id: Annotated[uuid.UUID, Path(description="Proposal object UUID.")],
    approval_status: Annotated[
        ApprovalStatus,
        Form(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        ),
    ],
):
    """Set the approval status of a project proposal."""
    return core_client.update_project_node(
        project_node_id=project_node_id, approval_status=approval_status
    )


@hub_router.get(
    "/analysis-nodes",
    summary="List all of the analysis proposals",
    status_code=status.HTTP_200_OK,
    # response_model=ListAnalysisNodes,
)
async def list_analysis_nodes():
    """List all analysis nodes."""
    return core_client.get_analysis_nodes()


@hub_router.get(
    "/analysis-nodes/{analysis_node_id}",
    summary="List a specific analysis node",
    status_code=status.HTTP_200_OK,
    # response_model=AnalysisNode,
)
async def list_specific_analysis_node(
    analysis_node_id: Annotated[uuid.UUID, Path(description="Analysis Node UUID.")],
):
    """List a specific analysis node."""
    return core_client.get_analysis_node(analysis_node_id=analysis_node_id)


@hub_router.post(
    "/analysis-nodes/{analysis_node_id}",
    summary="Update a specific analysis proposal",
    status_code=status.HTTP_200_OK,
    # response_model=AnalysisNode,
)
async def accept_reject_analysis_node(
    analysis_node_id: Annotated[
        uuid.UUID, Path(description="Analysis Node UUID (not analysis_id).")
    ],
    approval_status: Annotated[
        ApprovalStatus,
        Form(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        ),
    ],
):
    """Set the approval status of an analysis proposal."""
    return core_client.update_analysis_node(
        analysis_node_id=analysis_node_id, approval_status=approval_status
    )


@hub_router.get(
    "/analyses",
    summary="List all of the analysis proposals",
    status_code=status.HTTP_200_OK,
    # response_model=AllAnalyses,
)
async def list_all_analyses():
    """List all registered analyses."""
    return core_client.get_analyses()


@hub_router.get(
    "/analyses/{analysis_id}",
    summary="List a specific analysis",
    status_code=status.HTTP_200_OK,
    # response_model=Analysis,
)
async def list_specific_analysis(
    analysis_id: Annotated[uuid.UUID, Path(description="Analysis UUID.")],
):
    """List a specific analysis."""
    return core_client.get_analysis(analysis_id=analysis_id)


@hub_router.post(
    "/analyses/{analysis_id}",
    summary="Update a specific analysis proposal",
    status_code=status.HTTP_200_OK,
    # response_model=DetailedAnalysis,
)
async def update_specific_analysis(
    analysis_id: Annotated[uuid.UUID, Path(description="Analysis UUID.")],
    name: Annotated[str, Body(description="New analysis name.")],
):
    """Update analysis with a given UUID."""
    return core_client.update_analysis(analysis_id=analysis_id, name=name)


@route(
    request_method=hub_router.get,
    path="/registry-projects/{registry_project_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=RegistryProject,
    all_query_params=True,
)
async def get_registry_metadata_for_project(
    request: Request,
    response: Response,
):
    """List registry data for a project."""
    pass


def get_node_metadata_for_url(
    request: Request,
    node_id: Annotated[uuid.UUID, Body(description="Node UUID")],
):
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    headers = {
        k: v
        for k, v in request.headers.items()
        if (k != HOST and k != CONTENT_LENGTH.lower())
    }
    node_url = (
        hub_adapter_settings.HUB_SERVICE_URL
        + f"/nodes/{node_id}?include=registry_project"
    )
    node_resp = httpx.get(node_url, headers=headers)
    node_metadata = node_resp.json()

    if node_resp.status_code == status.HTTP_404_NOT_FOUND:
        node_metadata["message"] = "UUID not found"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=node_metadata,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if node_resp.status_code == status.HTTP_401_UNAUTHORIZED:
        node_metadata["message"] = "Not authorized to access the Hub"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=node_metadata,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if (
        REGISTRY_PROJECT_ID not in node_metadata
        or not node_metadata[REGISTRY_PROJECT_ID]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registry associated with node for the analysis UUID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return node_metadata, headers


def get_registry_metadata_for_url(
    node_results: Annotated[dict, Depends(get_node_metadata_for_url)],
):
    """Get registry metadata for a given UUID to be used in creating analysis image URL."""
    node_metadata, headers = node_results
    registry_project_id = node_metadata[REGISTRY_PROJECT_ID]

    registry_url_prefix = (
        hub_adapter_settings.HUB_SERVICE_URL
        + f"/registry-projects/{registry_project_id}"
    )
    registry_url = (
        registry_url_prefix
        + "?include=registry&fields=%2Baccount_id,%2Baccount_name,%2Baccount_secret"
    )
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

    registry_project_external_name = registry_metadata[EXTERNAL_NAME]

    if REGISTRY not in registry_metadata or HOST not in registry_metadata[REGISTRY]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No registry is associated with node {registry_project_external_name}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    host = registry_metadata[REGISTRY][HOST]
    user = (
        registry_metadata[ACCOUNT_NAME] if ACCOUNT_NAME in registry_metadata else None
    )
    pwd = (
        registry_metadata[ACCOUNT_SECRET]
        if ACCOUNT_SECRET in registry_metadata
        else None
    )

    return host, registry_project_external_name, user, pwd


def synthesize_image_data(
    analysis_id: Annotated[uuid.UUID, Body(description="Analysis UUID")],
    project_id: Annotated[uuid.UUID, Body(description="Project UUID")],
    compiled_info: Annotated[tuple, Depends(get_registry_metadata_for_url)],
):
    """Put all the data together for passing on to the PO."""
    host, registry_project_external_name, registry_user, registry_sec = compiled_info
    compiled_response = {
        "image_url": f"{host}/{registry_project_external_name}/{analysis_id}",
        "analysis_id": str(analysis_id),
        "project_id": str(project_id),
        "registry_url": host,
        "registry_user": registry_user,
        "registry_password": registry_sec,
    }
    return compiled_response


@hub_router.post(
    "/analysis/image",
    # response_model=AnalysisImageUrl
)
async def get_analysis_image_url(
    image_url_resp: AnalysisImageUrl = Depends(synthesize_image_data),
):
    """Build an analysis image URL using its metadata from the Hub."""
    return image_url_resp


@hub_router.get(
    "/analysis-buckets",
    summary="List a specific analysis bucket",
    status_code=status.HTTP_200_OK,
    # response_model=BucketList,
)
async def list_all_analysis_buckets():
    """List all analysis buckets."""
    return core_client.get_analysis_buckets()


@hub_router.get(
    "/analysis-buckets/{analysis_bucket_id}",
    summary="List a specific analysis bucket",
    status_code=status.HTTP_200_OK,
    # response_model=Bucket,
)
async def list_specific_analysis_buckets(
    analysis_bucket_id: Annotated[uuid.UUID, Path(description="Bucket UUID.")],
):
    """List a specific analysis bucket."""
    return core_client.get_analysis_bucket(analysis_bucket_id=analysis_bucket_id)


@hub_router.get(
    "/analysis-bucket-files",
    summary="List partial analysis bucket files.",
    status_code=status.HTTP_200_OK,
    # response_model=PartialBucketFilesList,
)
async def list_all_analysis_bucket_files():
    """List partial analysis bucket files."""
    return core_client.get_analysis_bucket_files()


@hub_router.get(
    "/analysis-bucket-files/{analysis_bucket_file_id}",
    summary="List partial analysis bucket files.",
    status_code=status.HTTP_200_OK,
    # response_model=PartialAnalysisBucketFile,
)
async def list_specific_analysis_bucket_file(
    analysis_bucket_file_id: Annotated[
        uuid.UUID, Path(description="Bucket file UUID.")
    ],
):
    """List specific partial analysis bucket file."""
    return core_client.get_analysis_bucket_file(
        analysis_bucket_file_id=analysis_bucket_file_id
    )
