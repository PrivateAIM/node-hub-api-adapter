"""EPs for Hub provided information."""

import logging
import pickle
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Path, Depends, HTTPException, Form, Body, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter import node_id_pickle_path
from hub_adapter.auth import (
    add_hub_jwt,
    get_hub_token,
    httpbearer,
    idp_oauth2_scheme_pass,
    verify_idp_token,
)
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.constants import (
    REGISTRY_PROJECT_ID,
    EXTERNAL_NAME,
    HOST,
    REGISTRY,
    CONTENT_LENGTH,
    ACCOUNT_NAME,
    ACCOUNT_SECRET,
)
from hub_adapter.core import route
from hub_adapter.models.hub import (
    Project,
    AllProjects,
    ProjectNode,
    ListProjectNodes,
    AnalysisNode,
    ListAnalysisNodes,
    RegistryProject,
    AnalysisImageUrl,
    ApprovalStatus,
    AllAnalyses,
    BucketList,
    PartialBucketFilesList,
    Bucket,
    PartialAnalysisBucketFile,
    DetailedAnalysis,
    Analysis,
)

hub_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(idp_oauth2_scheme_pass),
        Security(httpbearer),
        Depends(add_hub_jwt),
    ],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


async def get_node_id() -> str:
    """Uses the robot ID to obtain the associated node ID, sets it in the env vars, and returns it.

    An empty string node_id indicates no node is associated with provided robot username.
    """
    robot_user = hub_adapter_settings.HUB_ROBOT_USER

    node_cache = {}
    node_id = None
    if node_id_pickle_path.is_file():
        with open(node_id_pickle_path, "rb") as f:
            node_cache = pickle.load(f)

        node_id = node_cache.get(
            robot_user
        )  # Returns None if key not in dict or '' if no Node ID was found

    if (
        robot_user not in node_cache
    ):  # Node ID may be None since not every robot is associated with a node
        logger.info("NODE_ID not set for ROBOT_USER, retrieving from Hub")

        hub_auth_header = await get_hub_token()

        robot_user = hub_adapter_settings.HUB_ROBOT_USER
        core_url = hub_adapter_settings.HUB_SERVICE_URL.rstrip("/")
        node_id_resp = httpx.get(
            f"{core_url}/nodes?filter[robot_id]={robot_user}&fields=id",
            headers=hub_auth_header,
        )

        node_id_resp.raise_for_status()
        node_data = node_id_resp.json()["data"]

        node_id = node_data[0]["id"] if node_data else ""
        node_cache[robot_user] = node_id

        with open(node_id_pickle_path, "wb") as f:
            pickle.dump(node_cache, f)

    return node_id


def add_node_id_filter(request: Request, node_id: Annotated[str, Depends(get_node_id)]):
    """Middleware to add node_id filter query param to the request to limit response if node_id is found."""
    if node_id:  # Not an empty string
        query_ps = {k: v for k, v in request.query_params.items()}
        query_ps["filter[node_id]"] = node_id
        request._query_params = query_ps

    return request


@route(
    request_method=hub_router.get,
    path="/projects",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AllProjects,
    all_query_params=True,
)
async def list_all_projects(
    request: Request,
    response: Response,
):
    """List all projects."""
    pass


@route(
    request_method=hub_router.get,
    path="/projects/{project_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=Project,
    all_query_params=True,
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
    response_model=ListProjectNodes,
    all_query_params=True,
    dependencies=[Depends(add_node_id_filter)],
)
async def list_project_proposals(
    request: Request,
    response: Response,
):
    """List project proposals."""
    pass


@route(
    request_method=hub_router.post,
    path="/project-nodes/{proposal_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ProjectNode,
    form_params=["approval_status"],
    dependencies=[Depends(add_node_id_filter)],
)
async def accept_reject_project_proposal(
    request: Request,
    response: Response,
    proposal_id: Annotated[uuid.UUID, Path(description="Proposal object UUID.")],
    approval_status: Annotated[
        ApprovalStatus,
        Form(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        ),
    ],
):
    """Set the approval status of a project proposal."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-nodes",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ListAnalysisNodes,
    all_query_params=True,
    dependencies=[Depends(add_node_id_filter)],
)
async def list_analyses_of_nodes(
    request: Request,
    response: Response,
):
    """List analyses for a node."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-nodes/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AnalysisNode,
    all_query_params=True,
    dependencies=[Depends(add_node_id_filter)],
)
async def list_specific_analysis_node(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID, Path(description="Analysis Node UUID.")],
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.post,
    path="/analysis-nodes/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AnalysisNode,
    form_params=["approval_status"],
)
async def accept_reject_analysis_node(
    request: Request,
    response: Response,
    analysis_id: Annotated[
        uuid.UUID, Path(description="Analysis Node UUID (not analysis_id).")
    ],
    approval_status: Annotated[
        ApprovalStatus,
        Form(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        ),
    ],
):
    """Set the approval status of a analysis."""
    pass


@route(
    request_method=hub_router.get,
    path="/analyses",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AllAnalyses,
    all_query_params=True,
)
async def list_all_analyses(
    request: Request,
    response: Response,
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.get,
    path="/analyses/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=Analysis,
    all_query_params=True,
)
async def list_specific_analysis(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID, Path(description="Analysis UUID.")],
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.post,
    path="/analyses/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=DetailedAnalysis,
)
async def update_specific_analysis(
    request: Request,
    response: Response,
    body: Annotated[Analysis, Body(description="Analysis UUID.")],
):
    """Update analysis with a given UUID."""
    pass


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
        node_metadata["message"] = "Not authorized to access the Hub/"
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
    node_results: Annotated[dict, Depends(get_node_metadata_for_url)]
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


@route(
    request_method=hub_router.get,
    path="/analysis-buckets",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=BucketList,
    all_query_params=True,
)
async def list_all_analysis_buckets(
    request: Request,
    response: Response,
):
    """List analysis buckets."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-buckets/{bucket_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=Bucket,
    all_query_params=True,
)
async def list_specific_analysis_buckets(
    request: Request,
    response: Response,
    bucket_id: Annotated[uuid.UUID, Path(description="Bucket UUID.")],
):
    """List analysis buckets."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-bucket-files",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=PartialBucketFilesList,
    all_query_params=True,
)
async def list_all_analysis_bucket_files(
    request: Request,
    response: Response,
):
    """List partial analysis bucket files."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-bucket-files/{bucket_file_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=PartialAnalysisBucketFile,
    all_query_params=True,
)
async def list_specific_analysis_bucket_file(
    request: Request,
    response: Response,
    bucket_file_id: Annotated[uuid.UUID, Path(description="Bucket file UUID.")],
):
    """List specific partial analysis bucket file."""
    pass
