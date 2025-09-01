"""Methods for verifying auth."""

import asyncio

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from hub_adapter.conf import hub_adapter_settings
from hub_adapter.headless import auto_start_analyses
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.results import results_router

# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {
        "name": "Health",
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {"name": "Hub", "description": "Endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {"name": "PodOrc", "description": "Endpoints for the Pod Orchestration service."},
    {"name": "Results", "description": "Endpoints for the Results service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="FLAME project API for interacting with various microservices within the node for the UI.",
    swagger_ui_init_oauth={
        # "usePkceWithAuthorizationCodeGrant": True,
        # Auth fill client ID for the docs with the below value
        "clientId": hub_adapter_settings.API_CLIENT_ID,  # default client-id is Keycloak
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        "identifier": "Apache-2.0",
    },
    root_path=hub_adapter_settings.API_ROOT_PATH,
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
    results_router,
    hub_router,
    kong_router,
    health_router,
    auth_router,
)

for router in routers:
    app.include_router(router)


async def run_server():
    """Start the hub adapter API server."""
    config = uvicorn.Config(
        app, host="127.0.0.1", port=8081, reload=False, log_config=None
    )
    server = uvicorn.Server(config)
    await server.serve()


async def headless_probing(interval: int = 10):
    """Check for available analyses in the background and start them automatically.

    Parameters
    ----------
    interval : int
        Time in seconds to wait between checks.
    """
    while True:
        await auto_start_analyses()
        await asyncio.sleep(interval)


async def main():
    # Run both tasks concurrently
    tasks = [asyncio.create_task(run_server())]

    if hub_adapter_settings.HEADLESS:
        headless_operation = asyncio.create_task(headless_probing(interval=5))
        tasks.append(headless_operation)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
