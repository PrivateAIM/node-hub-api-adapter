"""EPs for the pod orchestrator."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import (
    add_internal_token_if_missing,
    jwtbearer,
    require_researcher_role,
    verify_idp_token,
)
from hub_adapter.core import route
from hub_adapter.dependencies import compile_analysis_pod_data, get_settings
from hub_adapter.models.podorc import (
    CleanupPodResponse,
    CleanUpType,
    CreateAnalysis,
    LogResponse,
    PodResponse,
    StatusResponse,
)

po_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
        Depends(add_internal_token_if_missing),
        Depends(require_researcher_role),
    ],
    tags=["PodOrc"],
    responses={404: {"description": "Not found"}},
    prefix="/po",
)

logger = logging.getLogger(__name__)


@route(
    request_method=po_router.post,
    path="",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().PODORC_SERVICE_URL,
    response_model=StatusResponse,
    pre_processing_func="extract_po_params",
    body_params=[
        "analysis_id",
        "project_id",
        "registry_url",
        "registry_user",
        "registry_password",
        "image_url",
        "kong_token",
    ],
)
async def create_analysis(
    request: Request,
    response: Response,
    image_url_resp: Annotated[CreateAnalysis, Depends(compile_analysis_pod_data)],
):
    """Gather the image URL for the requested analysis container and send information to the PO."""
    pass


@route(
    request_method=po_router.get,
    path="/logs",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().PODORC_SERVICE_URL,
    response_model=LogResponse,
)
async def get_all_analysis_logs(
    request: Request,
    response: Response,
):
    """Get all analysis pod logs."""
    pass


@route(
    request_method=po_router.get,
    path="/logs/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().PODORC_SERVICE_URL,
    response_model=LogResponse,
)
async def get_analysis_logs(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID, Path(description="UUID of the analysis.")],
):
    """Get the analysis pod logs."""
    pass


@route(
    request_method=po_router.get,
    path="/history",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().PODORC_SERVICE_URL,
    response_model=LogResponse,
)
async def get_all_analysis_log_history(
    request: Request,
    response: Response,
):
    """Get all previous analysis pod logs."""
    pass


@route(
    request_method=po_router.get,
    path="/history/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().PODORC_SERVICE_URL,
    response_model=LogResponse,
)
async def get_analysis_log_history(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get the previous analysis pod logs."""
    pass


@route(
    request_method=po_router.get,
    path="/status",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def get_all_analysis_status(
    request: Request,
    response: Response,
):
    """Get all analysis run statuses."""
    pass


@route(
    request_method=po_router.get,
    path="/status/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def get_analysis_status(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get a specific analysis pod run status."""

    pass


@route(
    request_method=po_router.get,
    path="/pods",
    status_code=status.HTTP_200_OK,
    response_model=PodResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def get_all_analysis_pods(
    request: Request,
    response: Response,
):
    """Get all running pods in the k8s cluster."""
    pass


@route(
    request_method=po_router.get,
    path="/pods/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=PodResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def get_analysis_pods(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get information on a specific running analysis pod in the k8s cluster."""
    pass


@route(
    request_method=po_router.put,
    path="/stop",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def stop_all_analyses(
    request: Request,
    response: Response,
):
    """Stop all analysis pods."""
    pass


@route(
    request_method=po_router.put,
    path="/stop/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def stop_analysis(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Stop a specific analysis run."""
    pass


@route(
    request_method=po_router.delete,
    path="/delete",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def delete_all_analyses(
    request: Request,
    response: Response,
):
    """Delete all analysis pods."""
    pass


@route(
    request_method=po_router.delete,
    path="/delete/{analysis_id}",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def delete_analysis(
    request: Request,
    response: Response,
    analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Delete a specific analysis run."""
    pass


@route(
    request_method=po_router.delete,
    path="/cleanup/{cleanup_type}",
    status_code=status.HTTP_200_OK,
    response_model=CleanupPodResponse,
    service_url=get_settings().PODORC_SERVICE_URL,
)
async def cleanup_node(
    request: Request,
    response: Response,
    cleanup_type: Annotated[CleanUpType, Path(description="What type of cleanup.")],
):
    """Delete specific types of resources.

    Should be a comma separated combination of the following entries:
    'all', 'analyzes', 'services', 'mb', 'rs', 'keycloak'
    """
    pass
