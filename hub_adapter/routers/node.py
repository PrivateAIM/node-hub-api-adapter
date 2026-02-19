"""Endpoints for setting and getting node configuration options."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Body, Security
from starlette import status

from hub_adapter import cache_dir
from hub_adapter.auth import jwtbearer, verify_idp_token
from hub_adapter.models.node import NodeSettings

node_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=["Node"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

# TODO: Move settings to DB
SETTINGS_PATH = cache_dir.joinpath("nodeConfig")
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_persistent_settings() -> NodeSettings:
    """Get node configuration settings from disk."""
    if SETTINGS_PATH.exists():
        overloaded_defaults = {**NodeSettings().model_dump(), **json.loads(SETTINGS_PATH.read_text())}
        return NodeSettings(**overloaded_defaults)
    return NodeSettings()  # Return defaults if the file is not found


def save_persistent_settings(settings: NodeSettings):
    """Save persistent settings to disk."""
    SETTINGS_PATH.write_text(json.dumps(settings.model_dump(), indent=2))


def update_settings(new_settings: NodeSettings) -> NodeSettings:
    """Update settings on disk."""
    current_settings = load_persistent_settings()
    updated_settings = current_settings.model_copy(update=new_settings.model_dump(exclude_none=True))
    save_persistent_settings(updated_settings)
    return updated_settings


@node_router.post(
    "/node/settings",
    response_model=NodeSettings,
    status_code=status.HTTP_202_ACCEPTED,
    name="node.settings.update",
)
async def update_node_settings(
    node_settings: Annotated[NodeSettings, Body(description="Required information to start analysis")],
) -> NodeSettings:
    """Update the node configuration settings."""
    return update_settings(node_settings)


@node_router.get(
    "/node/settings",
    response_model=NodeSettings,
    status_code=status.HTTP_200_OK,
    name="node.settings.get",
)
async def get_node_settings() -> NodeSettings:
    """Get the node configuration settings"""
    return load_persistent_settings()
