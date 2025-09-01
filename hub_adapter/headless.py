"""Collection of methods for running in headless mode in which analyses are detected and started automatically."""

import logging
import uuid

from fastapi import HTTPException
from httpx import HTTPStatusError
from starlette import status

from hub_adapter.auth import get_internal_token
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.core import make_request
from hub_adapter.oidc import check_oidc_configs_match
from hub_adapter.routers.hub import (
    compile_analysis_pod_data,
    format_query_params,
    get_node_id,
    get_node_metadata_for_url,
    get_node_type,
    get_registry_metadata_for_url,
    list_analysis_nodes,
)
from hub_adapter.routers.kong import (
    create_and_connect_analysis_to_project,
    delete_analysis,
    list_projects,
)

logger = logging.getLogger(__name__)


class StartAnalysisRequest:
    """Class designed for starting a new analysis run automatically."""

    def __init__(self, analysis_id, project_id, node_id, build_status, run_status):
        self.analysis_id = analysis_id
        self.project_id = project_id
        self.node_id = node_id
        self.build_status = build_status
        self.run_status = run_status

        # For controlling how many times to try and create a kong data store
        self.attempt = 0
        self.max_attempts = 3


async def auto_start_analyses():
    node_id = await get_node_id()
    node_type = await get_node_type()

    formatted_query_params = format_query_params(
        {"sort": "-updated_at", "include": "analysis"}
    )
    analyses = await list_analysis_nodes(
        node_id=node_id, query_params=formatted_query_params
    )
    valid_projects = await get_valid_projects()
    ready_to_start_analyses = parse_analyses(analyses, valid_projects)

    for analysis in ready_to_start_analyses:
        analysis_id, project_id, node_id, _, _ = analysis
        if node_type["type"] == "default":
            kong_resp = await register_analysis(analysis_id, project_id)
            if not kong_resp:
                continue

            kong_token = kong_resp["keyauth"].key

        else:  # Aggregator nodes don't need a kong store
            kong_token = "none_needed"

        props = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "node_id": node_id,
            "kong_token": kong_token,
        }
        await start_analysis_pod(analysis_props=props, kong_token=kong_token)


async def register_analysis(
    analysis_id: str, project_id: str, attempt: int = 1, max_attempts: int = 5
) -> dict | None:
    """Register an analysis with kong."""
    logger.info(f"Attempt {attempt} at starting analysis {analysis_id}")
    try:
        kong_resp = await create_and_connect_analysis_to_project(
            project_id, analysis_id
        )
        return kong_resp

    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            logger.error(
                f"{e.detail['message']}, failed to start analysis {analysis_id}"
            )

        elif e.status_code == status.HTTP_409_CONFLICT:
            logger.warning(
                f"Analysis {analysis_id} already registered, checking if pod exists..."
            )
            pod_exists = await pod_running(analysis_id)
            if pod_exists is None:  # Status could not be obtained, skip and try later
                pass

            elif (
                not pod_exists
            ):  # Status obtained and if not running, delete kong consumer
                logger.info(
                    f"No pod found for {analysis_id}, will delete kong consumer and retry"
                )
                await delete_analysis(analysis_id=analysis_id)

                if attempt < max_attempts:
                    return await register_analysis(
                        analysis_id, project_id, attempt + 1, max_attempts
                    )

            else:
                logger.info(
                    f"Pod already exists for analysis {analysis_id}, skipping start sequence"
                )

        else:
            logger.error(f"Failed to start analysis {analysis_id}, {e}")


async def pod_running(analysis_id: str) -> bool | None:
    """Check whether a pod with the given analysis_id is already running."""
    pod_status = await fetch_analysis_status(analysis_id=analysis_id)
    if pod_status:
        return bool(pod_status["status"])  # If anything exists

    return None  # Error occurred and no status retrieved


async def fetch_token_header() -> dict:
    """Append OIDC token to headers."""
    _, oidc_config = check_oidc_configs_match()
    token = await get_internal_token(oidc_config)
    return token


async def start_analysis_pod(analysis_props: dict, kong_token: str):
    """Start a new analysis pod."""
    logger.info(f"Starting new analysis pod for {analysis_props['analysis_id']}")

    node_metadata = get_node_metadata_for_url(analysis_props["node_id"])
    analysis_info = get_registry_metadata_for_url(node_metadata)
    props = compile_analysis_pod_data(
        analysis_id=analysis_props["analysis_id"],
        project_id=analysis_props["project_id"],
        compiled_info=analysis_info,
        kong_token=kong_token,
    )

    headers = await fetch_token_header()
    microsvc_path = f"{hub_adapter_settings.PODORC_SERVICE_URL}/po/"

    try:
        resp_data, _ = await make_request(
            url=microsvc_path,
            method="post",
            headers=headers,
            data=props,
        )
        logger.info(
            f"Analysis start response for {analysis_props["analysis_id"]}: {resp_data['status']}"
        )

    except HTTPStatusError as e:
        logger.error(
            f"Unable to start analysis {analysis_props['analysis_id']} due to the following error: {e}"
        )


async def fetch_analysis_status(analysis_id: uuid.UUID | str) -> dict:
    """Fetch the status for a specific analysis run. For headless operation"""
    headers = await fetch_token_header()
    microsvc_path = f"{hub_adapter_settings.PODORC_SERVICE_URL}/po/{analysis_id}/status"
    resp_data = None

    try:
        resp_data, _ = await make_request(
            url=microsvc_path,
            method="get",
            headers=headers,
        )

    except HTTPStatusError as e:
        logger.error(
            f"Unable to fetch the status of analysis {analysis_id} due to the following error: {e}"
        )

    return resp_data


async def get_valid_projects() -> set:
    """Collect the available data stores and create a set of project UUIDs with a valid data store."""
    kong_routes = await list_projects(project_id=None, detailed=False)
    valid_projects = set()

    for route in kong_routes.data:
        proj_uuid_chunks = route.name.split("-")[:-1]
        proj_uuid = "-".join(proj_uuid_chunks)
        valid_projects.add(proj_uuid)

    return valid_projects


def parse_analyses(analyses: list, valid_projects: set) -> set:
    """Iterate through analyses and check whether they are approved, built, and have a run status."""
    ready_analyses = set()
    for entry in analyses:
        analysis_id, project_id, node_id, build_status, run_status, approved = (
            str(entry.analysis_id),
            str(entry.analysis.project_id),
            str(entry.node_id),
            entry.analysis.build_status,
            entry.run_status,
            entry.approval_status,
        )
        if (
            approved == "approved"
            and build_status == "finished"
            and not run_status
            and project_id in valid_projects
        ):
            valid_entry = (analysis_id, project_id, node_id, build_status, run_status)
            ready_analyses.add(valid_entry)

    logger.info(f"Found {len(ready_analyses)} valid analyses ready to start")
    return ready_analyses
