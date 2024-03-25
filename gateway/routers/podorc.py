"""EPs for the pod orchestrator."""
import logging
from typing import Annotated

from fastapi import APIRouter, Path, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from gateway.auth import verify_idp_token, idp_oauth2_scheme_pass, httpbearer
from gateway.conf import gateway_settings
from gateway.core import route

po_router = APIRouter(
    dependencies=[Security(verify_idp_token), Security(idp_oauth2_scheme_pass), Security(httpbearer)],
    tags=["PodOrc"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)


@route(
    request_method=po_router.post,
    path="/{analysis_id}",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def create_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Get the logs for a specific analysis run."""
    pass


@route(
    request_method=po_router.get,
    path="/{analysis_id}/logs",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def get_analysis_logs(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Get the logs for a specific analysis run."""
    pass


@route(
    request_method=po_router.get,
    path="/{analysis_id}/status",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def get_analysis_status(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Get the status for a specific analysis run."""
    pass


@route(
    request_method=po_router.get,
    path="/{analysis_id}/pods",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def get_analysis_pods(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Get the pods for a specific analysis run."""
    pass


@route(
    request_method=po_router.put,
    path="/{analysis_id}/stop",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def stop_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Stop a specific analysis run."""
    pass


@route(
    request_method=po_router.delete,
    path="/{analysis_id}/delete",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.PODORC_SERVICE_URL,
)
async def delete_analysis(
        request: Request,
        response: Response,
        analysis_id: Annotated[str | None, Path(description="UUID of the analysis.")],
):
    """Delete a specific analysis run."""
    pass
