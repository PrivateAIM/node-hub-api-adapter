"""Methods for verifying auth."""

import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from hub_adapter.dependencies import get_settings
from hub_adapter.headless import GoGoAnalysis
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.meta import meta_router
from hub_adapter.routers.podorc import po_router

logger = logging.getLogger(__name__)

# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {"name": "Meta", "description": "Custom Hub Adapter endpoints which combine endpoints from other APIs."},
    {
        "name": "Health",
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {"name": "Hub", "description": "Gateway endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {"name": "PodOrc", "description": "Gateway endpoints for the Pod Orchestration service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="FLAME project API for interacting with various microservices within the node for the UI.",
    swagger_ui_init_oauth={
        # "usePkceWithAuthorizationCodeGrant": True,
        # Auth fill client ID for the docs with the below value
        "clientId": get_settings().API_CLIENT_ID,  # default client-id is Keycloak
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        "identifier": "Apache-2.0",
    },
    root_path=get_settings().API_ROOT_PATH,
)

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
    hub_router,
    kong_router,
    health_router,
    auth_router,
)

for router in routers:
    app.include_router(router)


async def run_server(host: str, port: int, reload: bool):
    """Start the hub adapter API server."""
    config = uvicorn.Config(app, host=host, port=port, reload=reload)
    server = uvicorn.Server(config)
    await server.serve()


async def headless_probing(interval: int = 60):
    """Check for available analyses in the background and start them automatically.

    Parameters
    ----------
    interval : int
        Time in seconds to wait between checks.
    """
    analysis_initiator = GoGoAnalysis()
    while True:
        await analysis_initiator.auto_start_analyses()
        await asyncio.sleep(interval)


async def deploy(host: str = "127.0.0.1", port: int = 8081, reload: bool = False):
    # Run both tasks concurrently
    tasks = [asyncio.create_task(run_server(host, port, reload))]

    headless: bool = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
    logger.info(f"Headless enabled: {headless}")
    headless_interval: int = int(os.getenv("HEADLESS_INTERVAL", "60"))

    if headless:
        headless_operation = asyncio.create_task(headless_probing(interval=headless_interval))
        tasks.append(headless_operation)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(deploy())
