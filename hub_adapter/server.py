"""Methods for verifying auth."""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from node_event_logging import EventModelMap
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from hub_adapter import logging_config
from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.dependencies import get_settings
from hub_adapter.event_logging import get_event_logger, teardown_event_logging
from hub_adapter.models.events import ANNOTATED_EVENTS
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.events import event_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.meta import meta_router
from hub_adapter.routers.node import node_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.storage import storage_router
from hub_adapter.user_settings import load_persistent_settings

logger = logging.getLogger(__name__)

# Global autostart task management
_autostart_task: asyncio.Task | None = None
_autostart_lock = asyncio.Lock()


# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {
        "name": "Events",
        "description": "Gateway endpoints for interacting with logged events.",
    },
    {"name": "Hub", "description": "Gateway endpoints for the central Hub service."},
    {
        "name": "Health",
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {
        "name": "Meta",
        "description": "Custom Hub Adapter endpoints which combine endpoints from other APIs.",
    },
    {
        "name": "Node",
        "description": "Endpoints for setting and getting node settings and configuration options.",
    },
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {
        "name": "PodOrc",
        "description": "Gateway endpoints for the Pod Orchestration service.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    EventModelMap.mapping = {event_name: event_data.get("model") for event_name, event_data in ANNOTATED_EVENTS.items()}

    get_event_logger()  # Attempts to setup connections

    yield

    teardown_event_logging()


app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="FLAME project API for interacting with various microservices within the node for the UI.",
    swagger_ui_init_oauth={
        "clientId": get_settings().api_client_id,  # default client-id is Keycloak
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        "identifier": "Apache-2.0",
    },
    root_path=get_settings().api_root_path,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def event_logging_middleware(request: Request, call_next):
    """Middleware to log the events."""
    response = await call_next(request)

    try:
        middleware_logger = get_event_logger()
        middleware_logger.log_fastapi_request(request, response.status_code, log_health_checks=False)

    except AttributeError:
        # Event logging not initialized, skip
        pass

    return response


routers = (
    po_router,
    meta_router,
    node_router,
    hub_router,
    storage_router,
    kong_router,
    health_router,
    auth_router,
    event_router,
)

for router in routers:
    app.include_router(router)


async def run_server(host: str, port: int, reload: bool):
    """Start the hub adapter API server."""
    config = uvicorn.Config(app, host=host, port=port, reload=reload, log_config=logging_config)
    server = uvicorn.Server(config)
    await server.serve()


async def autostart_probing(interval: int = 60):
    """Check for available analyses in the background and start them automatically.

    Parameters
    ----------
    interval : int
        Time in seconds to wait between checks.
    """
    analysis_initiator = GoGoAnalysis()
    while True:
        # Check current settings on each iteration to respond to changes
        try:
            current_settings = load_persistent_settings()
            if not current_settings.autostart.enabled:
                logger.info("Autostart disabled, stopping probing")
                break
            interval = current_settings.autostart.interval
        except Exception as e:
    # Start autostart task if enabled
    await start_autostart_task(

async def start_autostart_task():
    """Start the autostart task if not already running."""
    global _autostart_task
    async with _autostart_lock:
        if _autostart_task is None or _autostart_task.done():
            user_settings = load_persistent_settings()
            if user_settings.autostart.enabled:
                logger.info(f"Starting autostart task with interval {user_settings.autostart.interval}s")
                _autostart_task = asyncio.create_task(autostart_probing(interval=user_settings.autostart.interval))
            else:
                logger.info("Autostart is disabled")


async def stop_autostart_task():
    """Stop the autostart task if running."""
    global _autostart_task
    async with _autostart_lock:
        if _autostart_task is not None and not _autostart_task.done():
            logger.info("Stopping autostart task")
            _autostart_task.cancel()
            try:
                await _autostart_task
            except asyncio.CancelledError:
                pass
            _autostart_task = None


async def restart_autostart_task():
    """Restart the autostart task with new settings."""
    await stop_autostart_task()
    await asyncio.sleep(0.1)  # Small delay to ensure task is fully stopped
    await start_autostart_task()


async def deploy(host: str = "127.0.0.1", port: int = 5000, reload: bool = False):
    # Run both tasks concurrently
    tasks = [asyncio.create_task(run_server(host, port, reload))]

    user_settings = load_persistent_settings()

    autostart: bool = user_settings.autostart.enabled
    logger.info(f"Autostart enabled: {autostart}")
    autostart_interval: int = user_settings.autostart.interval

    if autostart:
        autostart_operation = asyncio.create_task(autostart_probing(interval=autostart_interval))
        tasks.append(autostart_operation)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(deploy())
