"""Endpoints for setting and getting node configuration options."""

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Security
from starlette import status

from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.conf import UserSettings
from hub_adapter.user_settings import load_persistent_settings, update_settings

node_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=["Node"],
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
    node_settings: Annotated[UserSettings, Body(description="Required information to start analysis")],
) -> UserSettings:
    """Update the node configuration settings."""
    return update_settings(node_settings)


@node_router.get(
    "/node/settings",
    response_model=UserSettings,
    status_code=status.HTTP_200_OK,
    name="node.settings.get",
)
async def get_node_settings() -> UserSettings:
    """Get the node configuration settings"""
    return load_persistent_settings()
