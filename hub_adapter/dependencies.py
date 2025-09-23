"""Dependency methods for endpoints."""

import logging
import pickle
import ssl
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import flame_hub
import httpx
import truststore
from fastapi import Body, Depends, HTTPException
from flame_hub import HubAPIError
from flame_hub._auth_flows import RobotAuth
from flame_hub._core_client import Node
from starlette import status

from hub_adapter import node_id_pickle_path
from hub_adapter.conf import Settings
from hub_adapter.errors import HubConnectError, catch_hub_errors

_node_type_cache = None

logger = logging.getLogger(__name__)


@lru_cache
def get_settings():
    return Settings()


@lru_cache
def get_ssl_context(hub_adapter_settings: Annotated[Settings, Depends(get_settings)]) -> ssl.SSLContext:
    """Check if there are additional certificates present and if so, load them."""
    cert_path = hub_adapter_settings.EXTRA_CA_CERTS
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if cert_path and Path(cert_path).exists():
        ctx.load_verify_locations(cafile=cert_path)
    return ctx


def get_flame_hub_auth_flow(
    ssl_ctx: Annotated[ssl.SSLContext, Depends(get_ssl_context)],
    hub_adapter_settings: Annotated[Settings, Depends(get_settings)],
) -> RobotAuth:
    """Automated method for getting a robot token from the central Hub service."""
    robot_id, robot_secret = (
        hub_adapter_settings.HUB_ROBOT_USER,
        hub_adapter_settings.HUB_ROBOT_SECRET,
    )

    if not robot_id or not robot_secret:
        logger.error("Missing robot ID or secret. Check env vars")
        raise ValueError("Missing Hub robot credentials, check that the environment variables are set properly")

    try:
        uuid.UUID(robot_id)

    except ValueError:
        err_msg = f"Invalid robot ID: {robot_id}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": err_msg,
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from ValueError

    auth = RobotAuth(
        robot_id=robot_id,
        robot_secret=robot_secret,
        client=httpx.Client(
            base_url=hub_adapter_settings.HUB_AUTH_SERVICE_URL,
            verify=ssl_ctx,
        ),
    )
    return auth


def get_core_client(
    hub_robot: Annotated[
        RobotAuth,
        Depends(get_flame_hub_auth_flow),
    ],
    ssl_ctx: Annotated[ssl.SSLContext, Depends(get_ssl_context)],
    hub_adapter_settings: Annotated[Settings, Depends(get_settings)],
):
    return flame_hub.CoreClient(
        client=httpx.Client(base_url=hub_adapter_settings.HUB_SERVICE_URL, auth=hub_robot, verify=ssl_ctx)
    )


@catch_hub_errors
async def get_node_id(
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
    hub_adapter_settings: Annotated[Settings, Depends(get_settings)],
    debug: bool = False,
) -> str | None:
    """Uses the robot ID to obtain the associated node ID, sets it in the env vars, and returns it.

    An empty string node_id indicates no node is associated with the provided robot username.

    If None is returned, no filtering will be applied, which is useful for debugging.
    """
    if debug:
        return None

    robot_id = hub_adapter_settings.HUB_ROBOT_USER

    node_cache = {}
    if node_id_pickle_path.is_file():
        with open(node_id_pickle_path, "rb") as f:
            node_cache = pickle.load(f)

    # Returns None if key not in dict or '' if no Node ID was found
    # Need to default to an intentionally wrong nodeId if nothing found otherwise Hub will return all resources

    node_id = node_cache.get(robot_id) or "nothingFound"

    if robot_id not in node_cache:  # Node ID may be None since not every robot is associated with a node
        logger.info("NODE_ID not set for ROBOT_USER, retrieving from Hub")

        try:
            node_id_resp = core_client.find_nodes(filter={"robot_id": robot_id}, fields="id")

        except httpx.ConnectError as e:
            err = "Connection Error - Hub is currently unreachable"
            logger.error(err)
            raise HubConnectError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": err,
                    "service": "Hub",
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        if node_id_resp and len(node_id_resp) == 1:
            node_id = str(node_id_resp[0].id)  # convert UUID type to string
            node_cache[robot_id] = node_id

            with open(node_id_pickle_path, "wb") as f:
                pickle.dump(node_cache, f)

    return node_id


@catch_hub_errors
async def get_node_type_cache(
    hub_adapter_settings: Annotated[Settings, Depends(get_settings)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    global _node_type_cache

    if _node_type_cache is None:
        node_id = await get_node_id(core_client=core_client, hub_adapter_settings=hub_adapter_settings)

        try:
            node_resp = core_client.get_node(node_id=node_id)
            _node_type_cache = {"type": node_resp.type}

        except httpx.ConnectError as e:
            err = "Connection Error - Hub is currently unreachable"
            logger.error(err)
            raise HubConnectError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": err,
                    "service": "Hub",
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    return _node_type_cache


def get_node_metadata_for_url(
    node_id: Annotated[uuid.UUID | str, Body(description="Node UUID")],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    node_metadata: Node = core_client.get_node(node_id=node_id)

    if not node_metadata.registry_project_id:
        err_msg = f"No registry project associated with node {node_id}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": err_msg,
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return node_metadata


def get_registry_metadata_for_url(
    node_metadata: Annotated[Node, Depends(get_node_metadata_for_url)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """Get registry metadata for a given UUID to be used in creating analysis image URL."""
    registry_metadata = dict()

    try:
        registry_metadata = core_client.get_registry_project(
            node_metadata.registry_project_id,
            fields=("account_id", "account_name", "account_secret"),
        )

    except HubAPIError as err:
        err_msg = f"Registry Project {node_metadata.registry_project_id} not found"
        logger.error(err_msg)
        if err.error_response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Hub",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from err

    if not registry_metadata.external_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No external name for node found",
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not registry_metadata.account_name or not registry_metadata.account_secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Unable to retrieve robot name or secret from the registry",
                "service": "Hub",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    registry_project_external_name = registry_metadata.external_name
    registry_id = registry_metadata.registry_id

    if not registry_id:
        err = f"No registry is associated with node {registry_project_external_name}"
        logger.error(err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": err,
                "service": "Hub",
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    host = registry_metadata.registry.host
    user = registry_metadata.account_name
    pwd = registry_metadata.account_secret

    return host, registry_project_external_name, user, pwd


def compile_analysis_pod_data(
    analysis_id: Annotated[uuid.UUID | str, Body(description="Analysis UUID")],
    project_id: Annotated[uuid.UUID | str, Body(description="Project UUID")],
    compiled_info: Annotated[tuple, Depends(get_registry_metadata_for_url)],
    kong_token: Annotated[str, Body(description="Analysis keyauth kong token")] = None,
):
    """Put all the data together for passing on to the PO."""
    host, registry_project_external_name, registry_user, registry_sec = compiled_info
    compiled_response = {
        "image_url": f"{host}/{registry_project_external_name}/{analysis_id}",
        "analysis_id": str(analysis_id),
        "project_id": str(project_id),
        "kong_token": kong_token,
        "registry_url": host,
        "registry_user": registry_user,
        "registry_password": registry_sec,
    }
    return compiled_response
