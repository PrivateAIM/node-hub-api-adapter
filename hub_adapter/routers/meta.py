"""Custom endpoints that combine other API endpoints for simplification."""

import logging
import uuid
from typing import Annotated

import flame_hub
import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Path, Security
from pydantic import BaseModel
from starlette import status

from hub_adapter.auth import (
    add_internal_token_if_missing,
    get_internal_token,
    jwtbearer,
    require_researcher_role,
    verify_idp_token,
)
from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.conf import Settings
from hub_adapter.core import make_request
from hub_adapter.dependencies import get_core_client, get_settings
from hub_adapter.models.podorc import StatusResponse
from hub_adapter.oidc import check_oidc_configs_match
from hub_adapter.routers.kong import delete_analysis

meta_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
        Depends(add_internal_token_if_missing),
        Depends(require_researcher_role),
    ],
    tags=["Meta"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


class InitializeAnalysis(BaseModel):
    analysis_id: uuid.UUID | str
    project_id: uuid.UUID | str


@meta_router.post(
    "/analysis/initialize",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_analysis(
    analysis_params: Annotated[InitializeAnalysis, Form(description="Required information to start analysis")],
    core_client: Annotated[flame_hub.CoreClient, Depends(get_core_client)],
):
    """Perform the required checks to start an analysis and send information to the PO."""
    initiator = GoGoAnalysis()
    node_id, node_type = await initiator.describe_node()

    analysis = core_client.find_analysis_nodes(filter={"analysis_id": analysis_params.analysis_id})
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Analysis {analysis_params.analysis_id} not found",
                "service": "Hub",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )

    valid_projects = await initiator.get_valid_projects()
    is_default_node = node_type == "default"
    parsed_analyses = initiator.parse_analyses(
        [analysis[0]], valid_projects, is_default_node, enforce_time_and_status_check=False
    )
    ready_to_start_analyses = [analysis[0] for analysis in parsed_analyses]

    if analysis_params.analysis_id not in ready_to_start_analyses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Analysis not ready",
                "service": "Hub",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )

    start_resp, start_status_code = await initiator.register_and_start_analysis(
        node_id=node_id, node_type=node_type, **analysis_params.model_dump()
    )

    # PO sometimes changes returned status code
    if start_status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK):
        return start_resp

    elif start_resp:
        raise HTTPException(
            status_code=start_status_code,
            detail=start_resp,
            headers={"WWW-Authenticate": "Bearer"},
        )

    else:
        raise HTTPException(
            status_code=start_status_code,
            detail={
                "message": "Failed to initialize analysis",
                "service": "PO",
                "status_code": start_status_code,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


@meta_router.delete(
    "/analysis/terminate/{analysis_id}",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
)
async def terminate_analysis(
    analysis_id: Annotated[str | uuid.UUID, Path(description="Analysis UUID that should be terminated")],
    hub_adapter_settings: Annotated[Settings, Depends(get_settings)],
):
    """Perform the required checks to stop an analysis and delete it and its components.

    This method will first delete the kong consumer and then send the delete command to the PO.
    """
    await delete_analysis(analysis_id=analysis_id, hub_adapter_settings=hub_adapter_settings)

    configs_match, oidc_config = check_oidc_configs_match()
    headers = await get_internal_token(oidc_config, hub_adapter_settings)

    microsvc_path = f"{get_settings().PODORC_SERVICE_URL}/po/delete/{analysis_id}"

    try:
        resp_data, status_code = await make_request(
            url=microsvc_path,
            method="delete",
            headers=headers,
        )

    except httpx.ConnectError as e:
        msg = "Connection Error - PO is currently unreachable"
        logger.error(msg)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={  # Invalid authentication credentials
                "message": msg,
                "service": "PO",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Service error - {e}",
                "service": "PO",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if not resp_data:
        logger.info(f"Analysis {analysis_id} had no pods running that could be terminated")

    else:
        logger.info(f"Analysis {analysis_id} was terminated")

    return resp_data
