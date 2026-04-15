"""Methods for verifying auth."""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from hub_adapter import logging_config
from hub_adapter.autostart import AutostartManager
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings
from hub_adapter.middleware import RequestLoggingMiddleware
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.logs import logs_router
from hub_adapter.routers.meta import meta_router
from hub_adapter.routers.node import node_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.storage import storage_router

logger = logging.getLogger(__name__)

autostart_manager = AutostartManager()


# API metadata
tags_metadata = [
    {"name": ServiceTag.AUTH, "description": "Endpoints for authorization specific tasks."},
    {"name": ServiceTag.LOGS, "description": "Retrieval of logs and events."},
    {"name": ServiceTag.HUB, "description": "Gateway endpoints for the central Hub service."},
    {
        "name": ServiceTag.HEALTH,
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {
        "name": ServiceTag.META,
        "description": "Custom Hub Adapter endpoints which combine endpoints from other APIs.",
    },
    {
        "name": ServiceTag.NODE,
        "description": "Endpoints for setting and getting node settings and configuration options.",
    },
    {"name": ServiceTag.KONG, "description": "Endpoints for the Kong gateway service."},
    {
        "name": ServiceTag.PODORC,
        "description": "Gateway endpoints for the Pod Orchestration service.",
    },
    {"name": ServiceTag.STORAGE, "description": "Gateway endpoints for the Storage service."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await autostart_manager.update()

    yield

    await autostart_manager.stop()


app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME Hub Adapter API",
    description="FLAME Hub Adapter gateway API for interacting with downstream services.",
    contact={
        "name": "Bruce Schultz",
        "email": "bschultz013@gmail.com",
        "url": "https://docs.privateaim.net/about/team.html",
    },
    swagger_ui_init_oauth={
        "clientId": get_settings().api_client_id,  # default client-id is Keycloak
    },
    servers=[
        {"url": "http://localhost:5000", "description": "api"},
    ],
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    root_path=get_settings().api_root_path,
    lifespan=lifespan,
)


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

routers = (
    po_router,
    meta_router,
    node_router,
    hub_router,
    storage_router,
    kong_router,
    health_router,
    auth_router,
    logs_router,
)

for router in routers:
    app.include_router(router)


async def deploy(host: str = "127.0.0.1", port: int = 5000, reload: bool = False):
    """Start the hub adapter API server with autostart management."""
    config = uvicorn.Config(app, host=host, port=port, reload=reload, log_config=logging_config)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(deploy())
