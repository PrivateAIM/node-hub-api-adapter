"""EPs for retrieving logged events."""

import datetime
import json
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from starlette import status

from hub_adapter.conf import Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings, make_log_hook

logger = logging.getLogger(__name__)

logs_router = APIRouter(
    # dependencies=[
    #     Security(verify_idp_token),
    #     Security(jwtbearer),
    # ],
    tags=[ServiceTag.LOGS],
    responses={404: {"description": "Not found"}},
)


def query_logs(query: str, params: dict | None = None):
    """Retrieve a selection of logs."""
    _fields = (
        "_msg",
        "_time",
        "kubernetes.container_image",
        "kubernetes.container_name",
        "kubernetes.pod_labels.component",
        "level",
        "log.service",
        "log.timestamp",
        "log.user_id",
    )
    settings = get_settings()

    logsql_query = f"{query} | fields {', '.join(_fields)}"
    query_data = {"query": logsql_query, **params}

    with httpx.Client(event_hooks={"response": [make_log_hook(ServiceTag.LOGS)]}) as client:
        resp = client.post(
            f"{settings.victoria_logs_url}/select/logsql/query",
            data=query_data,
        )
        resp.raise_for_status()

    logs = []
    for line in resp.text.strip().splitlines():
        if line:
            entry = json.loads(line)
            logs.append({k: v for k, v in entry.items() if k in _fields})

    return logs


@logs_router.get(
    "/events",
    status_code=status.HTTP_200_OK,
    name="logs.events.get",
)
async def get_events(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int | None, Query(description="Maximum number of events to return")] = None,
    offset: Annotated[int | None, Query(description="Number of events to offset by")] = 0,
    service_tag: Annotated[ServiceTag | None, Query(description="Filter events by service tag")] = None,
    username: Annotated[str | None, Query(description="Filter events by username")] = None,
    start_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter events by start date using ISO8601 format"),
    ] = None,
    end_date: Annotated[
        datetime.datetime | None,
        Query(description="Filter events by end date using ISO8601 format"),
    ] = None,
):
    """Retrieve a selection of logged events."""
    query_parts = ["*"] if not start_date and not end_date else ["_time:1h"]
    if service_tag:
        query_parts.append(f'log.service:"{service_tag}"')

    if username:
        query_parts.append(f'log.user_id:"{username}"')

    query = " AND ".join(query_parts)
    params = {"limit": limit or 100}

    if start_date:
        params["start"] = start_date.isoformat()

    if end_date:
        params["end"] = end_date.isoformat()

    return query_logs(query, params)


@logs_router.post(
    "/events/signin",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signin",
    response_model=None,
)
async def log_user_signin():
    """Create a log event that a user signed in. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED


@logs_router.post(
    "/events/signout",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signout",
    response_model=None,
)
async def log_user_signout():
    """Create a log event that a user signed out. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED
