"""Custom endpoints that combine other API endpoints for simplification."""

import logging
import uuid
from typing import Annotated

import flame_hub
from fastapi import APIRouter, Depends, Form, HTTPException, Security
from pydantic import BaseModel
from starlette import status

from hub_adapter.auth import (
    add_internal_token_if_missing,
    jwtbearer,
    verify_idp_token,
)
from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.dependencies import get_core_client
from hub_adapter.models.podorc import (
    CreatePodResponse,
)

meta_router = APIRouter(
    dependencies=[Security(verify_idp_token), Security(jwtbearer), Depends(add_internal_token_if_missing)],
    tags=["Meta"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


class InitializeAnalysis(BaseModel):
    analysis_id: uuid.UUID | str
    project_id: uuid.UUID | str


@meta_router.post(
    "/analysis/initialize",
    response_model=CreatePodResponse,
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

    if start_resp:
        return start_resp

    else:
        raise HTTPException(
            status_code=start_status_code,
            detail={"message": "Failed to initialize analysis", "status_code": start_status_code},
        )
