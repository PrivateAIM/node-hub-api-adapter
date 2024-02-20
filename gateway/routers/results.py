"""EPs for Results service."""
import uuid

from fastapi import Security, APIRouter
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from gateway.auth import oauth2_scheme
from gateway.conf import gateway_settings
from gateway.session import route

results_router = APIRouter()


@route(
    request_method=results_router.get,
    path="/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    payload_key=None,  # None for GET reqs
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,  # StreamingResponse
)
async def read_from_scratch(
        object_id: uuid.UUID,
        request: Request,
        response: Response,
        token: str = Security(oauth2_scheme),
):
    pass
