"""EPs for Hub provided information."""
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Query, Path, Depends, HTTPException, Security, Form, Body
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import add_hub_jwt, verify_idp_token, idp_oauth2_scheme_pass, httpbearer
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.constants import REGISTRY_PROJECT_ID, EXTERNAL_NAME, HOST, REGISTRY, CONTENT_LENGTH, ACCOUNT_NAME, \
    ACCOUNT_SECRET
from hub_adapter.core import route
from hub_adapter.models.hub import Project, AllProjects, ProjectNode, ListProjectNodes, \
    AnalysisNode, ListAnalysisNodes, RegistryProject, AnalysisImageUrl, ApprovalStatus, AllAnalyses, BucketList, \
    PartialBucketFilesList, Bucket, PartialAnalysisBucketFile

hub_router = APIRouter(
    dependencies=[
        Security(verify_idp_token), Security(idp_oauth2_scheme_pass), Security(httpbearer),
        Depends(add_hub_jwt),
    ],
    tags=["Hub"],
    responses={404: {"description": "Not found"}},
)


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
    query_params=["filter_realm_id"],
)
async def list_specific_project(
        project_id: Annotated[uuid.UUID, Path(description="Project UUID.")],
        request: Request,
        response: Response,
        filter_realm_id: Annotated[uuid.UUID, Query(description="Filter by realm UUID.")] = None,
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.get,
    path="/project-nodes",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ListProjectNodes,
    query_params=["include", "filter_id", "filter_project_id", "filter_project_realm_id",
                  "filter_node_id", "filter_node_realm_id"],
)
async def list_project_proposals(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Choices: 'node'/'project'",
                pattern="^((^|[,])(project|node))+$",
            ),
        ] = "project,node",
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
    """List project proposals."""
    pass


@route(
    request_method=hub_router.post,
    path="/project-nodes/{proposal_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=ProjectNode,
    form_params=["approval_status"],
)
async def accept_reject_project_proposal(
        request: Request,
        response: Response,
        proposal_id: Annotated[uuid.UUID, Path(description="Proposal object UUID.")],
        approval_status: Annotated[ApprovalStatus, Form(
            description="Set the approval status of project for the node. Either 'rejected' or 'approved'"
        )],
):
    """Set the approval status of a project proposal."""
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
                pattern="^((^|[,])(analysis|node))+$",  # Must be "node" or "analysis" or null,
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
    query_params=["include", "filter_analysis_realm_id"],
)
async def list_specific_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID, Path(description="Analysis UUID.")],
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Can only be 'node'/'analysis'",
                pattern="^((^|[,])(analysis|node))+$",  # Must be "node" and/or "analysis" or null,
            ),
        ] = "analysis",
        filter_analysis_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis realm UUID.",
            ),
        ] = None,
):
    """List project for a given UUID."""
    pass


@route(
    request_method=hub_router.get,
    path="/analyses",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=AllAnalyses,
    query_params=["include", "filter_analysis_realm_id"],
)
async def list_all_analyses(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Can only be 'node'/'analysis'",
                pattern="^((^|[,])(project|master_image))+$",  # Must be "project" and/or "master_image" or null,
            ),
        ] = "project",
        filter_analysis_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis realm UUID.",
            ),
        ] = None,
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
        analysis_id: Annotated[uuid.UUID, Path(description="Analysis object UUID (not analysis_id).")],
        approval_status: Annotated[ApprovalStatus, Form(
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


def get_node_metadata_for_url(
        request: Request,
        node_id: Annotated[uuid.UUID, Body(description="Node UUID")],
):
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    headers = {k: v for k, v in request.headers.items() if (k != HOST and k != CONTENT_LENGTH.lower())}
    node_url = hub_adapter_settings.HUB_SERVICE_URL + f"/nodes/{node_id}?include=registry_project"
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

    if REGISTRY_PROJECT_ID not in node_metadata or not node_metadata[REGISTRY_PROJECT_ID]:
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

    registry_url_prefix = hub_adapter_settings.HUB_SERVICE_URL + f"/registry-projects/{registry_project_id}"
    registry_url = registry_url_prefix + "?include=registry&fields=%2Baccount_id,%2Baccount_name,%2Baccount_secret"
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
    user = registry_metadata[ACCOUNT_NAME] if ACCOUNT_NAME in registry_metadata else None
    pwd = registry_metadata[ACCOUNT_SECRET] if ACCOUNT_SECRET in registry_metadata else None

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
        image_url_resp: AnalysisImageUrl = Depends(synthesize_image_data)
):
    """Build an analysis image URL using its metadata from the Hub."""
    return image_url_resp


@route(
    request_method=hub_router.get,
    path="/analysis-buckets",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=BucketList,
    query_params=["include", "filter_analysis_id", "filter_realm_id"],
)
async def list_all_analysis_buckets(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional registry data. Can only be 'analysis'",
                pattern="^analysis$",  # Must be "analysis" or null,
            ),
        ] = "analysis",
        filter_analysis_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis UUID.",
            ),
        ] = None,
        filter_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by realm UUID.",
            ),
        ] = None,
):
    """List analysis buckets."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-buckets/{bucket_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=Bucket,
    query_params=["include", "filter_analysis_id", "filter_realm_id"],
)
async def list_specific_analysis_buckets(
        request: Request,
        response: Response,
        bucket_id: Annotated[uuid.UUID, Path(description="Bucket UUID.")],
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional registry data. Can only be 'analysis'",
                pattern="^analysis$",  # Must be "analysis" or null,
            ),
        ] = "analysis",
        filter_analysis_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis UUID.",
            ),
        ] = None,
        filter_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by realm UUID.",
            ),
        ] = None,
):
    """List analysis buckets."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-bucket-files",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=PartialBucketFilesList,
    query_params=["include", "filter_analysis_id", "filter_realm_id", "filter_bucket_id"],
)
async def list_all_analysis_bucket_files(
        request: Request,
        response: Response,
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Choices: 'bucket'/'analysis'",
                pattern="^((^|[,])(analysis|bucket))+$",
            ),
        ] = "bucket",
        filter_analysis_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis UUID.",
            ),
        ] = None,
        filter_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by realm UUID.",
            ),
        ] = None,
        filter_bucket_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by bucket UUID.",
            ),
        ] = None,
):
    """List partial analysis bucket files."""
    pass


@route(
    request_method=hub_router.get,
    path="/analysis-bucket-files/{bucket_file_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.HUB_SERVICE_URL,
    response_model=PartialAnalysisBucketFile,
    query_params=["include", "filter_analysis_id", "filter_realm_id", "filter_bucket_id"],
)
async def list_specific_analysis_bucket_file(
        request: Request,
        response: Response,
        bucket_file_id: Annotated[uuid.UUID, Path(description="Bucket file UUID.")],
        include: Annotated[
            str | None,
            Query(
                description="Whether to include additional data for the given parameter. Choices: 'bucket'/'analysis'",
                pattern="^((^|[,])(analysis|bucket))+$",
            ),
        ] = "bucket",
        filter_analysis_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by analysis UUID.",
            ),
        ] = None,
        filter_realm_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by realm UUID.",
            ),
        ] = None,
        filter_bucket_id: Annotated[
            uuid.UUID | None,
            Query(
                description="Filter by bucket UUID.",
            ),
        ] = None,
):
    """List specific partial analysis bucket file."""
    pass
