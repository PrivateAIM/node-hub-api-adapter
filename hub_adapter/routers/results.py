"""EPs for Results service."""
import uuid

from fastapi import APIRouter, UploadFile, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import verify_idp_token, idp_oauth2_scheme_pass, httpbearer
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.core import route
from hub_adapter.models.results import ResultsUploadResponse

results_router = APIRouter(
    dependencies=[Security(verify_idp_token), Security(idp_oauth2_scheme_pass), Security(httpbearer)],
    tags=["Results"],
    responses={404: {"description": "Not found"}},
)


@route(
    request_method=results_router.get,
    path="/local/{object_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=None,
    file_response=True,
)
async def retrieve_intermediate_result_from_local(
        object_id: uuid.UUID,
        request: Request,
        response: Response,
):
    """Get a local result as file from local storage."""
    pass


@route(
    request_method=results_router.put,
    path="/local",
    status_code=status.HTTP_202_ACCEPTED,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=ResultsUploadResponse,
    file_params=["file"],
)
async def submit_intermediate_result_to_local(
        file: UploadFile,
        request: Request,
        response: Response,
):
    pass


@route(
    request_method=results_router.get,
    path="/intermediate/{object_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=None,
    file_response=True,
)
async def retrieve_intermediate_result_from_hub(
        object_id: uuid.UUID,
        request: Request,
        response: Response,
):
    """Get an intermediate result as file from the FLAME Hub."""
    pass


@route(
    request_method=results_router.put,
    path="/intermediate",
    status_code=status.HTTP_202_ACCEPTED,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=ResultsUploadResponse,
    file_params=["file"],
)
async def submit_intermediate_result_to_hub(
        file: UploadFile,
        request: Request,
        response: Response,
):
    """Upload a file as an intermediate result to the FLAME Hub. Returns a 202 on success.

    This endpoint returns immediately and submits the file in the background."""
    pass


@route(
    request_method=results_router.put,
    path="/final",
    status_code=status.HTTP_204_NO_CONTENT,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=None,
    file_params=["file"],
)
async def submit_final_result_to_hub(
        file: UploadFile,
        request: Request,
        response: Response,
):
    """Upload final results to FLAME Hub"""
    pass
