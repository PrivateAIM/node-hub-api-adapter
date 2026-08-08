"""Dependency methods for endpoints."""

import inspect
import logging
import pickle
import ssl
import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import flame_hub
import httpx2
import truststore
from fastapi import Body, Depends, HTTPException
from flame_hub import HubAPIError
from flame_hub._auth_flows import ClientAuth
from flame_hub.models import Node
from starlette import status
from starlette.concurrency import run_in_threadpool

from hub_adapter import node_id_pickle_path
from hub_adapter.conf import Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.errors import HubConnectError, catch_hub_errors
from hub_adapter.middleware import log_event

logger = logging.getLogger(__name__)

_node_type_cache = None

# client close functions to call
_closers: list[Callable[[], Awaitable[None] | None]] = []


def register_closer(close: Callable[[], Awaitable[None] | None]) -> None:
    """Register a teardown callable, sync or async, to be run by close_resources() at shutdown."""
    _closers.append(close)


def _track_client[ClientT: (httpx2.Client, httpx2.AsyncClient)](client: ClientT, forget: Callable[[], None]) -> ClientT:
    """Close this client at shutdown and drop the cached instance, so a later startup builds a fresh one."""
    register_closer(client.aclose if isinstance(client, httpx2.AsyncClient) else client.close)
    register_closer(forget)
    return client


async def close_resources() -> None:
    """Run every registered teardown callable, most recently registered first.

    Reverse order closes a cached client before clearing the cache that holds it, and a failure on one
    teardown must not strand the rest.
    """
    for close in reversed(_closers):  # close client before clearing cache
        try:
            result = close()
            if inspect.isawaitable(result):
                await result

        except Exception as e:
            logger.warning(f"Error during shutdown of {getattr(close, '__qualname__', close)}: {e}")

    _closers.clear()


@lru_cache(maxsize=1)
def get_settings():
    return Settings()


@lru_cache(maxsize=1)
def get_ssl_context(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ssl.SSLContext:
    """Check if there are additional certificates present and if so, load them."""
    cert_path = settings.extra_ca_certs
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if cert_path and Path(cert_path).exists():
        ctx.load_verify_locations(cafile=cert_path)
    return ctx


@lru_cache(maxsize=1)
def get_flame_hub_auth_flow(
    ssl_ctx: Annotated[ssl.SSLContext, Depends(get_ssl_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClientAuth:
    """Automated method for getting a robot token from the central Hub service."""
    hub_node_client_id, hub_node_client_secret = (
        settings.hub_node_client_id,
        settings.hub_node_client_secret,
    )

    if not hub_node_client_id or not hub_node_client_secret:
        logger.error("Missing node client ID or secret. Check env vars")
        raise ValueError("Missing node client credentials, check that the environment variables are set properly")

    try:
        uuid.UUID(hub_node_client_id)

    except ValueError:
        err_msg = f"Invalid node client ID: {hub_node_client_id}"
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

    auth = ClientAuth(
        client_id=hub_node_client_id,
        client_secret=hub_node_client_secret,
        client=_track_client(
            httpx2.Client(
                base_url=settings.hub_auth_service_url,
                verify=ssl_ctx,
                timeout=settings.hub_request_timeout,
                event_hooks={"response": [make_log_hook(ServiceTag.HUB)]},
            ),
            get_flame_hub_auth_flow.cache_clear,
        ),
    )
    return auth


def make_log_hook(service: str, is_async: bool = False, event_name: str | None = None):
    """Return an httpx response event hook that logs with the given service label."""

    def log_response(response: httpx2.Response) -> None:
        request = response.request
        log_level = logging.ERROR if response.status_code >= 400 else logging.INFO
        event = f"{event_name}.response" if event_name else f"{service.lower()}.http.response"
        log_event(
            event,
            event_description=f"HTTP {request.method} {request.url} {response.http_version} {response.status_code}",
            level=log_level,
            status_code=response.status_code,
            service=service,
        )

    async def async_log_response(response: httpx2.Response) -> None:
        log_response(response)

    return async_log_response if is_async else log_response


@lru_cache(maxsize=1)
def get_core_client(
    hub_auth: Annotated[
        ClientAuth,
        Depends(get_flame_hub_auth_flow),
    ],
    ssl_ctx: Annotated[ssl.SSLContext, Depends(get_ssl_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> flame_hub.CoreClient:
    """Return the shared Hub client."""
    return flame_hub.CoreClient(
        client=_track_client(
            httpx2.Client(
                base_url=settings.hub_service_url,
                auth=hub_auth,
                verify=ssl_ctx,
                timeout=settings.hub_request_timeout,
                event_hooks={"response": [make_log_hook(ServiceTag.HUB)]},
            ),
            get_core_client.cache_clear,
        )
    )


@lru_cache(maxsize=1)
def get_idp_client() -> httpx2.Client:
    """Shared sync client for the IDP."""
    return _track_client(
        httpx2.Client(
            verify=get_ssl_context(get_settings()),
            event_hooks={"response": [make_log_hook(ServiceTag.IDP)]},
        ),
        get_idp_client.cache_clear,
    )


@lru_cache(maxsize=1)
def get_hub_async_client() -> httpx2.AsyncClient:
    """Shared async client for unauthenticated Hub calls e.g. fetching its public key."""
    return _track_client(
        httpx2.AsyncClient(
            verify=get_ssl_context(get_settings()),
            event_hooks={"response": [make_log_hook(ServiceTag.HUB, is_async=True)]},
        ),
        get_hub_async_client.cache_clear,
    )


@lru_cache(maxsize=1)
def get_proxy_client() -> httpx2.AsyncClient:
    """Shared async client for the downstream services."""
    return _track_client(httpx2.AsyncClient(), get_proxy_client.cache_clear)


def _read_node_cache() -> dict:
    """Load the cached node IDs from disk, returning an empty cache if there is no file yet.

    The file is only ever written by _write_node_cache into this app's own cache directory, so the
    pickle is trusted local data rather than external input.
    """
    if not node_id_pickle_path.is_file():
        return {}

    with open(node_id_pickle_path, "rb") as f:
        return pickle.load(f)


def _write_node_cache(node_cache: dict) -> None:
    """Persist the node ID cache to disk."""
    with open(node_id_pickle_path, "wb") as f:
        pickle.dump(node_cache, f)


@catch_hub_errors
def get_node_id(
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    force_refresh: bool = False,
) -> str | None:
    """Uses the Node client ID to obtain the associated node ID, sets it in the env vars, and returns it.

    An empty string node_id indicates no node is associated with the provided node client username.

    If None is returned, no filtering will be applied, which is useful for debugging.

    Defined with "def" because it reads the cache file and calls the synchronous Hub client.
    """
    node_client_id = settings.hub_node_client_id

    node_cache = {}

    if not force_refresh:
        node_cache = _read_node_cache()

    # Returns None if key not in dict or '' if no Node ID was found
    # Need to default to an intentionally wrong nodeId if nothing found otherwise Hub will return all resources

    node_id = node_cache.get(node_client_id) or "nothingFound"

    if node_client_id not in node_cache:  # Node ID may be None since not every node is associated with a node
        logger.info("NODE_ID not set for HUB_NODE_CLIENT_ID, retrieving from Hub")

        try:
            node_id_resp = core_client.find_nodes(filter={"clientId": node_client_id}, fields="id")

        except httpx2.ConnectError as e:
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
            node_cache[node_client_id] = node_id

            _write_node_cache(node_cache)

        elif node_id_resp:
            logger.error("Hub returned multiple nodes for HUB_NODE_CLIENT_ID")

        else:
            logger.info("No Hub node is associated with HUB_NODE_CLIENT_ID")

    return node_id


@catch_hub_errors
async def get_node_type_cache(
    settings: Annotated[Settings, Depends(get_settings)],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    global _node_type_cache

    if _node_type_cache is None:
        node_id = await get_node_id(core_client=core_client, settings=settings)

        try:
            # Stays async because it awaits get_node_id, so the Hub call is offloaded
            node_resp = await run_in_threadpool(core_client.get_node, node_id=node_id)
            _node_type_cache = {"type": node_resp.type}

        except httpx2.ConnectError as e:
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
) -> Node | None:
    """Get analysis metadata for a given UUID to be used in creating analysis image URL."""
    node_metadata: Node | None = core_client.get_node(node_id=node_id)

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
        if err.error_response.status_code == status.HTTP_404_NOT_FOUND:
            err_msg = f"Registry Project {node_metadata.registry_project_id} not found"
            logger.error(err_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Hub",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from err

        else:
            logger.error(err.error_response.message)
            raise HTTPException(
                status_code=err.error_response.status_code,
                detail={
                    "message": err.error_response.message,
                    "service": "Hub",
                    "status_code": err.error_response.status_code,
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
                "message": "Unable to retrieve node client ID or secret from the registry",
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
