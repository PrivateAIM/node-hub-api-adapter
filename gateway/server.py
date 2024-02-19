"""Methods for verifying auth."""
import uuid

import uvicorn
from fastapi import FastAPI, Request, Response, Security
from starlette import status

from auth import idp_settings, initialize_k8s_api_conn, oauth2_scheme
from conf import gateway_settings
from models import ScratchRequest
from wrapper import route

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


@app.get("/pods", tags=["PodOrc"])
async def get_k8s_pods():
    """Get a list of k8s pods."""
    k8s_api = initialize_k8s_api_conn()
    return k8s_api.list_pod_for_all_namespaces().to_dict()


@route(
    request_method=app.get,
    path="/scratch/{object_id}",
    status_code=status.HTTP_200_OK,
    payload_key=None,  # None for GET reqs
    # payload_key="scratch_read",  # Only for POST
    service_url=gateway_settings.RESULTS_SERVICE_URL,
    response_model=None,  # StreamingResponse
    tags=["Results"],
)
async def read_from_scratch(
    object_id: uuid.UUID,
    request: Request,
    response: Response,
    token: str = Security(oauth2_scheme),
):
    pass


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
