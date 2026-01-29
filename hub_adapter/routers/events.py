"""EPs for retrieving logged events."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from node_event_logging import EventLog, bind_to
from starlette import status

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.conf import Settings
from hub_adapter.dependencies import get_settings
from hub_adapter.event_logging import get_event_logger
from hub_adapter.models.events import EventLogResponse

event_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=["Events"],
    responses={404: {"description": "Not found"}},
)


@event_router.get(
    "/events",
    response_model=EventLogResponse,
    status_code=status.HTTP_200_OK,
    name="events.get",
)
async def get_events(
        settings: Annotated[Settings, Depends(get_settings)],
        limit: Annotated[int | None, Query(description="Maximum number of events to return")] = 100,
        offset: Annotated[int | None, Query(description="Number of events to offset by")] = 0,
        service_tag: Annotated[str | None, Query(description="Filter events by service name")] = None,
        event_name: Annotated[str | None, Query(description="Filter events by event name")] = None,
        username: Annotated[str | None, Query(description="Filter events by username")] = None,
        start_date: Annotated[
            datetime.datetime | None, Query(description="Filter events by start date using ISO8601 format")
        ] = None,
        end_date: Annotated[
            datetime.datetime | None, Query(description="Filter events by end date using ISO8601 format")
        ] = None,
):
    """Retrieve a selection of logged events."""
    event_logger = get_event_logger()
    if not event_logger or not event_logger.event_db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Failed to connect to postgres database "
                           f"at {settings.POSTGRES_EVENT_HOST}, unable to retrieve events",
                "service": "Hub Adapter",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
        )

    with bind_to(event_logger.event_db):
        events = EventLog.select().order_by(EventLog.timestamp.desc()).limit(limit).offset(offset)
        total = EventLog.select().count()

        metadata = {
            "count": len(events),
            "limit": limit,
            "offset": offset,
            "total": total,
        }

        if username:
            events = events.where(EventLog.attributes["user"]["username"] == username)

        if start_date:
            events = events.where(EventLog.timestamp >= start_date)

        if end_date:
            events = events.where(EventLog.timestamp <= end_date)

        if service_tag:
            events = events.where(EventLog.attributes.tags << service_tag)

        if event_name:
            events = events.where(EventLog.event_name == event_name)

    return {"data": [event for event in events.dicts()], "meta": metadata}


@event_router.post(
    "/events/signin",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signin",
)
async def log_user_signin():
    """Create a log event that a user signed in. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED


@event_router.post(
    "/events/signout",
    status_code=status.HTTP_201_CREATED,
    name="auth.user.signout",
)
async def log_user_signout():
    """Create a log event that a user signed out. Username is extracted from the JWT required to call this endpoint."""
    return status.HTTP_201_CREATED
