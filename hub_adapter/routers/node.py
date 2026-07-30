"""Endpoints for setting and getting node configuration options."""

import logging
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Security
from pydantic import ValidationError
from starlette import status
from starlette.concurrency import run_in_threadpool

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.conf import UserSettings
from hub_adapter.constants import ServiceTag
from hub_adapter.user_settings import load_persistent_settings, update_settings

node_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=[ServiceTag.NODE],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


@node_router.post(
    "/node/settings",
    response_model=UserSettings,
    status_code=status.HTTP_202_ACCEPTED,
    name="node.settings.update",
)
async def update_node_settings(
        node_settings: Annotated[UserSettings, Body(description="Partial settings to update")],
) -> UserSettings:
    """Update the node configuration settings with partial data.

    Raises
    ------
    HTTPException
        422: If unknown settings keys are provided.
    """
    try:
        patch_payload = node_settings.model_dump(exclude_unset=True)
        # Writes to Postgres and the JSON cache, so it runs in a worker thread
        result = await run_in_threadpool(update_settings, patch_payload)

        # Update autostart state if any autostart settings changed
        if "autostart" in node_settings.model_fields_set:
            from hub_adapter.managers import autostart_manager

            await autostart_manager.update()

        # Restart Kong consumer cleanup if its interval changed
        if "kong_cleanup" in node_settings.model_fields_set:
            from hub_adapter.managers import kong_cleanup_manager

            await kong_cleanup_manager.start()

        # Restart service health monitoring if its interval or retention changed
        if "service_health" in node_settings.model_fields_set:
            from hub_adapter.managers import service_health_monitor

            await service_health_monitor.start()

        return result

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": f"Invalid settings - {e.error_count()} error(s) found: "
                           f"{[err['loc'][0] for err in e.errors()]}",
                "service": "Node",
                "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            },
        ) from e


@node_router.get(
    "/node/settings",
    response_model=UserSettings,
    status_code=status.HTTP_200_OK,
    name="node.settings.get",
)
async def get_node_settings() -> UserSettings:
    """Get the node configuration settings"""
    # Reads from Postgres with a JSON fallback, so it runs in a worker thread
    return await run_in_threadpool(load_persistent_settings)
