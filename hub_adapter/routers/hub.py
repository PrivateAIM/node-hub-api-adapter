"""EPs for Hub provided information."""

import logging
import uuid
from typing import Annotated

import flame_hub
from fastapi import APIRouter, Body, Depends, Form, Path, Security
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

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.dependencies import compile_analysis_pod_data, get_core_client, get_node_id
from hub_adapter.errors import catch_hub_errors
from hub_adapter.models.hub import (
    AnalysisImageUrl,
    DetailedAnalysis,
    NodeTypeResponse,
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
    """Extract and format the query params for the hub client."""
    query_params = dict(request.query_params)
    return format_query_params(query_params)


def format_query_params(query_params: dict) -> dict:
    """Format the query params for the hub client."""
    formatted_query_params = {}

    page_params: str = query_params.get("page")
    # filter_params: str = query_params.get("filter")  # TODO: Add filter support
    sort_params: str = query_params.get("sort")
    fields_params: str = query_params.get("fields")

    if fields_params:
        formatted_query_params["fields"] = fields_params.split(",")

    if sort_params:
        sort_order = "descending" if sort_params.startswith("-") else "ascending"
        formatted_query_params["sort"] = {
            "by": sort_params.lstrip("+-"),
            "order": sort_order,
        }

    if page_params:
        page_param_dict: dict = eval(page_params)
        limit = page_param_dict.get("limit") or 50
        offset = page_param_dict.get("offset") or 0
        formatted_query_params["page"] = {"limit": limit, "offset": offset}

    return formatted_query_params


@hub_router.get(
    "/projects",
    summary="List all of the projects",
    status_code=status.HTTP_200_OK,
    response_model=list[Project],
)
@catch_hub_errors
async def list_all_projects(
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    node_id: Annotated[str, Depends(get_node_id)],
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    node_id: Annotated[str, Depends(get_node_id)],
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
async def list_all_analyses(
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List a specific analysis."""
    return core_client.get_analysis(analysis_id=analysis_id)


@hub_router.get(
    "/nodes",
    summary="List all of the nodes",
    status_code=status.HTTP_200_OK,
    response_model=list[Node],
)
@catch_hub_errors
async def list_all_nodes(
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List all nodes."""
    return core_client.get_nodes(**query_params)


@hub_router.get(
    "/nodes/{node_id}",
    summary="List a specific node",
    status_code=status.HTTP_200_OK,
    response_model=Node,
)
@catch_hub_errors
async def list_specific_node(
    node_id: Annotated[uuid.UUID | str, Path(description="Node UUID.")],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List a specific node."""
    return core_client.get_node(node_id=node_id)


@hub_router.get(
    "/node-type",
    summary="Return what type of node this API is deployed on",
    status_code=status.HTTP_200_OK,
    response_model=NodeTypeResponse,
)
@catch_hub_errors
async def get_node_type(core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)]):
    """Return what type of node this API is deployed on."""
    global _node_type_cache

    if _node_type_cache is None:
        node_id = await get_node_id()
        node_resp = core_client.get_node(node_id=node_id)
        _node_type_cache = {"type": node_resp.type}

    return _node_type_cache


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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List registry data for a project."""

    return core_client.get_registry_project(registry_project_id=registry_project_id)


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
async def list_all_analysis_buckets(
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
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
async def list_all_analysis_bucket_files(
    query_params: Annotated[dict, Depends(parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
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
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List specific partial analysis bucket file."""
    return core_client.get_analysis_bucket_file(analysis_bucket_file_id=analysis_bucket_file_id)
