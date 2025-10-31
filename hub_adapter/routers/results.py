"""EPs for Results service."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Security
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.core import route
from hub_adapter.dependencies import get_settings

results_router = APIRouter(
    dependencies=[Security(verify_idp_token), Security(jwtbearer)],
    tags=["Results"],
    responses={404: {"description": "Not found"}},
)


@route(
    request_method=results_router.delete,
    path="/local/{project_id}",
    status_code=status.HTTP_200_OK,
    service_url=get_settings().RESULTS_SERVICE_URL,
)
async def delete_local_results(
    project_id: Annotated[uuid.UUID | str, Path(description="UUID of the associated project.")],
    request: Request,
    response: Response,
):
    """Delete all objects in MinIO and all Postgres database entries related to the specified project.

    Returns a 200 on success, a 400 if the project is still available on the Hub and a 403 if it is not the
    Hub Adapter client that sends the request. In both error cases nothing is deleted at all."""
    pass
