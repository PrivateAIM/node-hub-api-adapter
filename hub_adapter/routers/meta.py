"""Custom endpoints that combine other API endpoints for simplification."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Security
from pydantic import BaseModel
from starlette import status

from hub_adapter.auth import (
    add_internal_token_if_missing,
    jwtbearer,
    verify_idp_token,
)
from hub_adapter.headless import GoGoAnalysis
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
):
    """Perform the required checks to start an analysis and send information to the PO."""
    initiator = GoGoAnalysis()
    node_id, node_type = await initiator.describe_node()
    po_resp, po_status_code = await initiator.register_and_start_analysis(
        node_id=node_id, node_type=node_type, **analysis_params.model_dump()
    )
    if po_resp:
        return po_resp

    else:
        {"msg": "Failed to initialize analysis"}
