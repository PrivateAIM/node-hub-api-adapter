"""Methods for verifying auth."""

import uvicorn
from fastapi import FastAPI, Depends

from project.auth import get_user_info, settings
from project.models import User

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
        "clientId": settings.client_id,  # default client-id is Keycloak
        "clientSecret": settings.client_secret,
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


@app.get("/")
async def greeting() -> dict:
    """Default greeting."""
    return {"message": "Howdy anonymous"}


@app.get("/secure", tags=["Results"])
async def secure_greeting(user: User = Depends(get_user_info)):
    """Secured response greeting."""
    return {
        "message": f"Hello {user.username} your name is: {user.first_name} {user.last_name}"
    }


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
