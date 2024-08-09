"""EPs for the pod orchestrator."""
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Depends
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import add_hub_jwt
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.core import route
from hub_adapter.models.podorc import LogResponse, StatusResponse, PodResponse, CreatePodResponse
from hub_adapter.routers.hub import synthesize_image_data

po_router = APIRouter(
    dependencies=[
        # Security(verify_idp_token), Security(idp_oauth2_scheme_pass), Security(httpbearer),
    ],
    tags=["PodOrc"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


@route(
    request_method=po_router.post,
    path="/po",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
    dependencies=[Depends(add_hub_jwt)],
    response_model=CreatePodResponse,
    pre_processing_func="extract_po_params",
    body_params=["analysis_id", "project_id", "registry_url", "registry_user", "registry_password"],
)
async def create_analysis(
        request: Request,
        response: Response,
        image_url_resp: Annotated[dict, Depends(synthesize_image_data)],
):
    """Gather the image URL for the requested analysis container and send information to the PO."""
    pass


@route(
    request_method=po_router.get,
    path="/po/{analysis_id}/logs",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
    response_model=LogResponse,
    query_params=["analysis_id"],
)
async def get_analysis_logs(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get the logs for a specific analysis run."""
    pass


@route(
    request_method=po_router.get,
    path="/po/{analysis_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
)
async def get_analysis_status(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get the status for a specific analysis run."""
    pass


@route(
    request_method=po_router.get,
    path="/po/{analysis_id}/pods",
    status_code=status.HTTP_200_OK,
    response_model=PodResponse,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
)
async def get_analysis_pods(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Get the pods for a specific analysis run."""
    pass


@route(
    request_method=po_router.put,
    path="/po/{analysis_id}/stop",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
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
    path="/po/{analysis_id}/delete",
    status_code=status.HTTP_200_OK,
    response_model=StatusResponse,
    service_url=hub_adapter_settings.PODORC_SERVICE_URL,
)
async def delete_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[uuid.UUID | None, Path(description="UUID of the analysis.")],
):
    """Delete a specific analysis run."""
    pass
