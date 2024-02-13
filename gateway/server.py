"""Methods for verifying auth."""
import uuid

import uvicorn
from fastapi import FastAPI, Depends, Request, Response
from starlette import status

from auth import get_user_info, settings as auth_settings
from conf import settings as conf_settings
from models import User, ScratchRequest
from wrapper import route

# API Schemas to collect
RESULTS_API_SCHEMA = "http://localhost:8000/openapi.json"

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
        "clientId": auth_settings.client_id,  # default client-id is Keycloak
        "clientSecret": auth_settings.client_secret,
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
async def secure_test(user: User = Depends(get_user_info)):
    """Secured response greeting."""
    return {
        "message": f"Hello {user.username} your name is: {user.first_name} {user.last_name}"
    }


@route(
    request_method=app.get,
    path="/results/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    payload_key="object_settings",
    service_url=conf_settings.RESULTS_SERVICE_URL,
    response_model=None,  # StreamingResponse
    tags=["Results"],
)
async def read_from_scratch(
    object_id: uuid.UUID,
    object_settings: ScratchRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_user_info),
):
    pass


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
