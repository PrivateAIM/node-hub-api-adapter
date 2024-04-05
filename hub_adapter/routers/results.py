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
    path="/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=None,
    file_response=True,
)
async def read_from_scratch(
        object_id: uuid.UUID,
        request: Request,
        response: Response,
):
    pass


@route(
    request_method=results_router.put,
    path="/scratch",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=ResultsUploadResponse,
    file_params=["file"],
)
async def upload_to_scratch(
        file: UploadFile,
        request: Request,
        response: Response,
):
    pass


@route(
    request_method=results_router.put,
    path="/upload",
    status_code=status.HTTP_200_OK,
    service_url=hub_adapter_settings.RESULTS_SERVICE_URL,
    response_model=ResultsUploadResponse,
    file_params=["file"],
)
async def upload_to_hub(
        file: UploadFile,
        request: Request,
        response: Response,
):
    pass
