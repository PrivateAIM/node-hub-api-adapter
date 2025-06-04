"""EPs for Hub provided information."""

import logging
import pickle
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Path, Security
from flame_hub import HubAPIError
from flame_hub.models import (
    Analysis,
    AnalysisBucket,
    AnalysisNode,
    AnalysisNodeApprovalStatus,
    Node,
    Project,
    ProjectNode,
    ProjectNodeApprovalStatus,
    RegistryProject,
)
from starlette import status
from starlette.requests import Request

from hub_adapter import node_id_pickle_path
from hub_adapter.auth import core_client, jwtbearer, verify_idp_token
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.errors import catch_hub_errors
from hub_adapter.models.hub import (
    AnalysisImageUrl,
    DetailedAnalysis,
)

hub_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


def parse_query_params(request: Request) -> dict:
    """Format the query params for the hub client."""
    formatted_query_params = {}

    query_params = dict(request.query_params)

    page_params: str = query_params.get("page")
    # filter_params: str = query_params.get("filter")  # TODO: Add filter support
    sort_params: str = query_params.get("sort")
    fields_params: str = query_params.get("fields")

    if fields_params:
        formatted_query_params["fields"] = fields_params.split(",")

    if sort_params:
        sort_order = "descending" if sort_params.startswith("-") else "ascending"
        formatted_query_params["sort"] = {"by": sort_params.lstrip("+-"), "order": sort_order}

    if page_params:
        page_param_dict: dict = eval(page_params)
        limit = page_param_dict.get("limit") or 50
        offset = page_param_dict.get("offset") or 0
        formatted_query_params["page"] = {"limit": limit, "offset": offset}

    return formatted_query_params


@catch_hub_errors
async def get_node_id(debug: bool = False) -> str | None:
    """Uses the robot ID to obtain the associated node ID, sets it in the env vars, and returns it.

    An empty string node_id indicates no node is associated with the provided robot username.

    If None is returned, no filtering will be applied, which is useful for debugging.
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

    if robot_id not in node_cache:  # Node ID may be None since not every robot is associated with a node
        logger.info("NODE_ID not set for ROBOT_USER, retrieving from Hub")

        node_id_resp = core_client.find_nodes(filter={"robot_id": robot_id}, fields="id")

        if node_id_resp and len(node_id_resp) == 1:
            node_id = str(node_id_resp[0].id)  # convert UUID type to string
            node_cache[robot_id] = node_id

            with open(node_id_pickle_path, "wb") as f:
                pickle.dump(node_cache, f)

    return node_id


@hub_router.get(
    "/projects",
    summary="List all of the projects",
    status_code=status.HTTP_200_OK,
    response_model=list[Project],
)
@catch_hub_errors
async def list_all_projects(query_params: Annotated[dict, Depends(parse_query_params)]):
    """List all projects."""
    return core_client.find_projects(**query_params)


@hub_router.get(
    "/projects/{project_id}",
    summary="List a specific project",
    status_code=status.HTTP_200_OK,
    response_model=Project,
)
@catch_hub_errors
async def list_specific_project(
    project_id: Annotated[uuid.UUID | str, Path(description="Project UUID.")],
):
    """List project for a given UUID."""
    return core_client.get_project(project_id=project_id)


@hub_router.get(
    "/project-nodes",
    summary="List all of the project proposals",
    status_code=status.HTTP_200_OK,
    response_model=list[ProjectNode],
)
@catch_hub_errors
async def list_project_proposals(
    node_id: Annotated[str, Depends(get_node_id)], query_params: Annotated[dict, Depends(parse_query_params)]
):
    """List project proposals."""
    if node_id:
        return core_client.find_project_nodes(filter={"node_id": node_id}, **query_params)

    else:
        return core_client.get_project_nodes(**query_params)


@hub_router.get(
    "/project-nodes/{project_node_id}",
    summary="List a specific project proposal",
    status_code=status.HTTP_200_OK,
    response_model=ProjectNode,
)
@catch_hub_errors
async def list_project_proposal(
    project_node_id: Annotated[uuid.UUID | str, Path(description="Proposal object UUID.")],
):
    """Set the approval status of a project proposal."""
    return core_client.get_project_node(project_node_id=project_node_id)


@hub_router.post(
    "/project-nodes/{project_node_id}",
    summary="Update a specific project proposal",
    status_code=status.HTTP_200_OK,
    response_model=ProjectNode,
)
@catch_hub_errors
async def accept_reject_project_proposal(
    project_node_id: Annotated[uuid.UUID | str, Path(description="Proposal object UUID.")],
    approval_status: Annotated[
        ProjectNodeApprovalStatus,
        Form(description="Set the approval status of project for the node. Either 'rejected' or 'approved'"),
    ],
):
    """Set the approval status of a project proposal."""
    return core_client.update_project_node(project_node_id=project_node_id, approval_status=approval_status)


@hub_router.get(
    "/analysis-nodes",
    summary="List all of the analysis proposals",
    status_code=status.HTTP_200_OK,
    response_model=list[AnalysisNode],
)
@catch_hub_errors
async def list_analysis_nodes(
    node_id: Annotated[str, Depends(get_node_id)], query_params: Annotated[dict, Depends(parse_query_params)]
):
    """List all analysis nodes for give node."""
    if node_id:
        return core_client.find_analysis_nodes(filter={"node_id": node_id}, **query_params)

    else:
        return core_client.find_analysis_nodes(**query_params)


@hub_router.get(
    "/analysis-nodes/{analysis_node_id}",
    summary="List a specific analysis node",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisNode,
)
@catch_hub_errors
async def list_specific_analysis_node(
    analysis_node_id: Annotated[uuid.UUID | str, Path(description="Analysis Node UUID.")],
):
    """List a specific analysis node."""
    return core_client.get_analysis_node(analysis_node_id=analysis_node_id)


@hub_router.post(
    "/analysis-nodes/{analysis_node_id}",
    summary="Update a specific analysis proposal",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisNode,
)
@catch_hub_errors
async def accept_reject_analysis_node(
    analysis_node_id: Annotated[uuid.UUID | str, Path(description="Analysis Node UUID (not analysis_id).")],
    approval_status: Annotated[
        AnalysisNodeApprovalStatus,
        Form(description="Set the approval status of project for the node. Either 'rejected' or 'approved'"),
    ],
):
    """Set the approval status of an analysis proposal."""
    return core_client.update_analysis_node(analysis_node_id=analysis_node_id, approval_status=approval_status)


@hub_router.get(
    "/analyses",
    summary="List all of the analysis proposals",
    status_code=status.HTTP_200_OK,
    response_model=list[Analysis],
)
@catch_hub_errors
async def list_all_analyses(query_params: Annotated[dict, Depends(parse_query_params)]):
    """List all registered analyses."""
    return core_client.get_analyses(**query_params)


@hub_router.get(
    "/analyses/{analysis_id}",
    summary="List a specific analysis",
    status_code=status.HTTP_200_OK,
    response_model=Analysis,
)
@catch_hub_errors
async def list_specific_analysis(
    analysis_id: Annotated[uuid.UUID | str, Path(description="Analysis UUID.")],
):
    """List a specific analysis."""
    return core_client.get_analysis(analysis_id=analysis_id)


@hub_router.post(
    "/analyses/{analysis_id}",
    summary="Update a specific analysis proposal",
    status_code=status.HTTP_200_OK,
    response_model=DetailedAnalysis,
)
@catch_hub_errors
async def update_specific_analysis(
    analysis_id: Annotated[uuid.UUID | str, Path(description="Analysis UUID.")],
    name: Annotated[str, Body(description="New analysis name.")],
):
    """Update analysis with a given UUID."""
    return core_client.update_analysis(analysis_id=analysis_id, name=name)


@hub_router.get(
    "/registry-projects/{registry_project_id}",
    summary="Get registry project",
    status_code=status.HTTP_200_OK,
    response_model=RegistryProject,
)
@catch_hub_errors
async def get_registry_metadata_for_project(
    registry_project_id: Annotated[uuid.UUID | str, Path(description="Registry project UUID.")],
):
    """List registry data for a project."""

    return core_client.get_registry_project(registry_project_id=registry_project_id)


def get_node_metadata_for_url(
    node_id: Annotated[uuid.UUID | str, Body(description="Node UUID")],
):
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    node_metadata: Node = core_client.get_node(node_id=node_id)

    if not node_metadata.registry_project_id:
        err_msg = f"No registry project associated with node {node_id}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": err_msg,
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return node_metadata


def get_registry_metadata_for_url(
    node_metadata: Annotated[Node, Depends(get_node_metadata_for_url)],
):
    """Get registry metadata for a given UUID to be used in creating analysis image URL."""
    registry_metadata = dict()

    try:
        registry_metadata = core_client.get_registry_project(
            node_metadata.registry_project_id,
            fields=("account_id", "account_name", "account_secret"),
        )

    except HubAPIError as err:
        err_msg = f"Registry Project {node_metadata.registry_project_id} not found"
        logger.error(err_msg)
        if err.error_response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Hub",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from err

    if not registry_metadata.external_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No external name for node found",
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not registry_metadata.account_name or registry_metadata.account_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Unable to retrieve robot name or secret from the registry",
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    registry_project_external_name = registry_metadata.external_name
    registry_id = registry_metadata.registry_id

    if not registry_id:
        err = f"No registry is associated with node {registry_project_external_name}"
        logger.error(err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": err,
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    host = registry_metadata.registry.host
    user = registry_metadata.account_name
    pwd = registry_metadata.account_secret

    return host, registry_project_external_name, user, pwd


def compile_analysis_pod_data(
    analysis_id: Annotated[uuid.UUID | str, Body(description="Analysis UUID")],
    project_id: Annotated[uuid.UUID | str, Body(description="Project UUID")],
    compiled_info: Annotated[tuple, Depends(get_registry_metadata_for_url)],
    kong_token: Annotated[str, Body(description="Analysis keyauth kong token")] = None,
):
    """Put all the data together for passing on to the PO."""
    host, registry_project_external_name, registry_user, registry_sec = compiled_info
    compiled_response = {
        "image_url": f"{host}/{registry_project_external_name}/{analysis_id}",
        "analysis_id": str(analysis_id),
        "project_id": str(project_id),
        "kong_token": kong_token,
        "registry_url": host,
        "registry_user": registry_user,
        "registry_password": registry_sec,
    }
    return compiled_response


@hub_router.post("/analysis/image", response_model=AnalysisImageUrl)
@catch_hub_errors
async def get_analysis_image_url(
    image_url_resp: Annotated[AnalysisImageUrl, Depends(compile_analysis_pod_data)],
):
    """Build an analysis image URL using its metadata from the Hub."""
    return image_url_resp


@hub_router.get(
    "/analysis-buckets",
    summary="List a specific analysis bucket",
    status_code=status.HTTP_200_OK,
    # response_model=BucketList,
)
@catch_hub_errors
async def list_all_analysis_buckets(query_params: Annotated[dict, Depends(parse_query_params)]):
    """List all analysis buckets."""
    return core_client.find_analysis_buckets(**query_params)


@hub_router.get(
    "/analysis-buckets/{analysis_bucket_id}",
    summary="List a specific analysis bucket",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisBucket,
)
@catch_hub_errors
async def list_specific_analysis_buckets(
    analysis_bucket_id: Annotated[uuid.UUID | str, Path(description="Bucket UUID.")],
):
    """List a specific analysis bucket."""
    return core_client.get_analysis_bucket(analysis_bucket_id=analysis_bucket_id)


@hub_router.get(
    "/analysis-bucket-files",
    summary="List partial analysis bucket files.",
    status_code=status.HTTP_200_OK,
    # response_model=PartialBucketFilesList,
)
@catch_hub_errors
async def list_all_analysis_bucket_files(query_params: Annotated[dict, Depends(parse_query_params)]):
    """List partial analysis bucket files."""
    return core_client.get_analysis_bucket_files(**query_params)


@hub_router.get(
    "/analysis-bucket-files/{analysis_bucket_file_id}",
    summary="List partial analysis bucket files.",
    status_code=status.HTTP_200_OK,
    # response_model=PartialAnalysisBucketFile,
)
@catch_hub_errors
async def list_specific_analysis_bucket_file(
    analysis_bucket_file_id: Annotated[uuid.UUID | str, Path(description="Bucket file UUID.")],
):
    """List specific partial analysis bucket file."""
    return core_client.get_analysis_bucket_file(analysis_bucket_file_id=analysis_bucket_file_id)
