"""EPs for Results service."""
import uuid

from fastapi import APIRouter, UploadFile, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from gateway.auth import realm_oauth2_scheme
from gateway.conf import gateway_settings
from gateway.core import route

results_router = APIRouter(
    dependencies=[Security(realm_oauth2_scheme)],
    tags=["Results"],
    responses={404: {"description": "Not found"}},
)


@route(
    request_method=results_router.get,
    path="/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,
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
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,  # StreamingResponse
    form_params=["file"],
)
async def upload_to_scratch(
        file: UploadFile,
        request: Request,
        response: Response,
):
    pass
