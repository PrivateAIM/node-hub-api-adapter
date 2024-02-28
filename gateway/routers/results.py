"""EPs for Results service."""
import uuid

from fastapi import APIRouter, UploadFile
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from gateway.conf import gateway_settings
from gateway.core import route

results_router = APIRouter(
    # dependencies=[Security(oauth2_scheme)],
    tags=["Results"],
    responses={404: {"description": "Not found"}},
)


@route(
    request_method=results_router.get,
    path="/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    payload_key=None,  # None for GET reqs
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,
    response_stream=True,  # Required if response is a binary stream e.g. a file
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
    payload_key=None,  # TODO update
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,  # StreamingResponse
)
async def upload_to_scratch(
        file: UploadFile,
        request: Request,
        response: Response,
):
    pass


@route(
    request_method=results_router.put,
    path="/put",
    status_code=status.HTTP_200_OK,
    payload_key=None,  # TODO update
    service_url="https://httpbin.org",
    response_model=None,  # StreamingResponse
    form_params=["file"],  # Must match param name
)
async def put_test(
        file: UploadFile,
        request: Request,
        response: Response,
):
    """Testing put."""
    pass
