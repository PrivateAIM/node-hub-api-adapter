"""EPs for Hub provided information."""

import json
import logging
import uuid
from typing import Annotated

import flame_hub
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security
from flame_hub.models import AnalysisNode, Project, ProjectNode
from starlette import status

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_core_client, get_node_id, get_node_type_cache
from hub_adapter.errors import catch_hub_errors
from hub_adapter.schemas.hub import NodeTypeResponse

hub_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=[ServiceTag.HUB],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


def _parse_query_params(
    page: Annotated[str | None, Query(description='Pagination as JSON, e.g. {"limit": 50, "offset": 0}')] = None,
    sort: Annotated[str | None, Query(description="Sort field; prefix with - for descending, + for ascending")] = None,
    fields: Annotated[str | None, Query(description="Comma-separated list of fields to return")] = None,
    include: Annotated[str | None, Query(description="Comma-separated list of nested fields to include")] = None,
) -> dict:
    """Format query params for the hub client."""
    formatted: dict = {}

    if include:
        formatted["include"] = include.split(",")

    if fields:
        formatted["fields"] = fields.split(",")

    if sort:
        formatted["sort"] = {
            "by": sort.lstrip("+-"),
            "order": "descending" if sort.startswith("-") else "ascending",
        }

    if page:
        try:
            page_dict = json.loads(page)

        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Page must be valid JSON"
            ) from e

        if not isinstance(page_dict, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="page must be a JSON object")

        formatted["page"] = {
            "limit": page_dict.get("limit") or 50,
            "offset": page_dict.get("offset") or 0,
        }

    return formatted


@hub_router.get(
    "/projects",
    summary="List all of the projects",
    status_code=status.HTTP_200_OK,
    response_model=list[Project],
    name="hub.project.get",
)
@catch_hub_errors
def list_all_projects(
    query_params: Annotated[dict, Depends(_parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List all projects."""
    return core_client.find_projects(**query_params)


@hub_router.get(
    "/project-nodes",
    summary="List all of the project proposals",
    status_code=status.HTTP_200_OK,
    response_model=list[ProjectNode],
    name="hub.project.node.get",
)
@catch_hub_errors
def list_project_proposals(
    node_id: Annotated[str, Depends(get_node_id)],
    query_params: Annotated[dict, Depends(_parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List project proposals."""
    if node_id:
        return core_client.find_project_nodes(filter={"nodeId": node_id}, **query_params)

    else:
        return core_client.get_project_nodes(**query_params)


@hub_router.get(
    "/analysis-nodes",
    summary="List all of the analysis proposals",
    status_code=status.HTTP_200_OK,
    response_model=list[AnalysisNode],
    name="hub.analysis.node.get",
)
@catch_hub_errors
def list_analysis_nodes(
    node_id: Annotated[str, Depends(get_node_id)],
    query_params: Annotated[dict, Depends(_parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List all analysis nodes for give node."""
    if node_id:
        return core_client.find_analysis_nodes(filter={"nodeId": node_id}, **query_params)

    else:
        return core_client.find_analysis_nodes(**query_params)


@hub_router.get(
    "/analysis-nodes/{analysis_node_id}",
    summary="List a specific analysis node",
    status_code=status.HTTP_200_OK,
    response_model=AnalysisNode,
    name="hub.analysis.node.get",
)
@catch_hub_errors
def list_specific_analysis_node(
    analysis_node_id: Annotated[uuid.UUID | str, Path(description="Analysis Node UUID.")],
    query_params: Annotated[dict, Depends(_parse_query_params)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """List a specific analysis node."""
    return core_client.get_analysis_node(analysis_node_id=analysis_node_id, **query_params)


@hub_router.get(
    "/node-type",
    summary="Return what type of node this API is deployed on",
    status_code=status.HTTP_200_OK,
    response_model=NodeTypeResponse,
    name="hub.node.type.get",
)
@catch_hub_errors
def get_node_type(node_type: Annotated[dict | None, Depends(get_node_type_cache)]):
    """Return what type of node this API is deployed on."""
    return node_type
