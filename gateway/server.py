"""Methods for verifying auth."""

import uvicorn
from fastapi import FastAPI, Security

from auth import idp_settings, oauth2_scheme
from gateway.routers.k8s import k8s_router
from gateway.routers.results import results_router

# API metadata
tags_metadata = [
    {"name": "Results", "description": "Endpoints for the Results service."},
    {"name": "Analysis", "description": "Endpoints for the Analysis service."},
    {"name": "PodOrc", "description": "Endpoints for the Pod Orchestration service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="Test API for FLAME project",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        # Auth fill client ID for the docs with the below value
        "clientId": idp_settings.client_id,  # default client-id is Keycloak
        "clientSecret": idp_settings.client_secret,
    },
)


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins="*",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )


@app.get("/unsecure")
async def unsecure_test() -> dict:
    """Default greeting."""
    return {"message": "Howdy anonymous"}


@app.get("/secure")
async def secure_test(token: str = Security(oauth2_scheme)):
    """Secured response greeting."""
    return token
    # return {
    #     "message": f"Hello {user.username} your name is: {user.first_name} {user.last_name}"
    # }


app.include_router(
    k8s_router,
    tags=["PodOrc"],
)

app.include_router(
    results_router,
    tags=["Results"],
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081, reload=True)
