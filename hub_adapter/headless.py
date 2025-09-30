"""Collection of methods for running in headless mode in which analyses are detected and started automatically."""

import logging
import uuid

from fastapi import HTTPException
from flame_hub import HubAPIError
from httpx import ConnectError, HTTPStatusError
from starlette import status

from hub_adapter.auth import get_internal_token
from hub_adapter.core import make_request
from hub_adapter.dependencies import (
    compile_analysis_pod_data,
    get_core_client,
    get_flame_hub_auth_flow,
    get_node_id,
    get_node_metadata_for_url,
    get_node_type_cache,
    get_registry_metadata_for_url,
    get_settings,
    get_ssl_context,
)
from hub_adapter.errors import KongConflictError, KongConnectError
from hub_adapter.oidc import check_oidc_configs_match
from hub_adapter.routers.hub import (
    format_query_params,
    list_analysis_nodes,
)
from hub_adapter.routers.kong import (
    create_and_connect_analysis_to_project,
    delete_analysis,
    list_projects,
)

logger = logging.getLogger(__name__)


class GoGoAnalysis:
    def __init__(self):
        self.settings = None
        self.core_client = None

        self.gather_deps()  # populates self.settings and self.core_client

    def gather_deps(self):
        """Gather all the dependencies needed to run the headless mode."""
        settings = get_settings()
        ssl_ctx = get_ssl_context(settings)
        hub_robot = get_flame_hub_auth_flow(ssl_ctx, settings)
        core_client = get_core_client(hub_robot, ssl_ctx, settings)

        self.settings = settings
        self.core_client = core_client

    async def auto_start_analyses(self) -> set | None:
        """Gather and iterate over analyses from hub and start them if they pass checks."""
        analyses_started = set()

        try:
            node_id, node_type = await self.describe_node()

        except (HubAPIError, HTTPException) as e:
            logger.error(f"Unable to connect to the Hub: {e}")
            return None

        formatted_query_params = format_query_params({"sort": "-updated_at", "include": "analysis"})

        try:
            analyses = await list_analysis_nodes(
                core_client=self.core_client, node_id=node_id, query_params=formatted_query_params
            )

        except ConnectError as e:
            logger.error(f"Unable to start analyses, error connecting to Hub: {e}")
            return analyses_started

        valid_projects = await self.get_valid_projects()
        ready_to_start_analyses = self.parse_analyses(analyses, valid_projects)

        for analysis in ready_to_start_analyses:
            analysis_id, project_id, node_id, _, _ = analysis
            start_resp, status_code = await self.register_and_start_analysis(
                analysis_id, project_id, node_id, node_type
            )
            if start_resp is None:
                continue

            if status_code == status.HTTP_201_CREATED:
                analyses_started.add(analysis_id)

        return analyses_started

    async def register_and_start_analysis(
        self, analysis_id: str, project_id: str, node_id: str, node_type: str
    ) -> tuple | None:
        """Return node information."""
        if node_type == "default":
            kong_resp, status_code = await self.register_analysis(analysis_id, project_id)
            if status_code != status.HTTP_201_CREATED:
                return kong_resp, status_code

            kong_token = kong_resp["keyauth"].key

        else:  # Aggregator nodes don't need a kong store
            kong_token = "none_needed"

        props = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "node_id": node_id,
            "kong_token": kong_token,
        }
        start_resp, status_code = await self.send_start_request(analysis_props=props, kong_token=kong_token)
        return start_resp, status_code

    async def describe_node(self) -> tuple[str, str] | None:
        """Get node information from cache, and if not present, get from Hub and set cache."""
        node_id = await get_node_id(core_client=self.core_client, hub_adapter_settings=self.settings)
        node_type_cache = await get_node_type_cache(hub_adapter_settings=self.settings, core_client=self.core_client)
        node_type = node_type_cache["type"]

        return node_id, node_type

    async def register_analysis(
        self, analysis_id: str, project_id: str, attempt: int = 1, max_attempts: int = 5
    ) -> tuple[dict | None, int] | None:
        """Register an analysis with kong."""
        logger.info(f"Attempt {attempt} at starting analysis {analysis_id}")
        try:
            kong_resp = await create_and_connect_analysis_to_project(
                hub_adapter_settings=self.settings, project_id=project_id, analysis_id=analysis_id
            )
            return kong_resp, status.HTTP_201_CREATED

        except KongConnectError as e:
            logger.error(f"{e.detail['message']}, failed to start analysis {analysis_id}")
            return None, e.status_code

        except KongConflictError as e:
            logger.warning(f"Analysis {analysis_id} already registered, checking if pod exists...")
            pod_exists = await self.pod_running(analysis_id)
            if pod_exists is None:  # Status could not be obtained, skip and try later
                pass

            elif not pod_exists:  # Status obtained and if not running, delete kong consumer
                logger.info(f"No pod found for {analysis_id}, will delete kong consumer and retry")
                await delete_analysis(hub_adapter_settings=self.settings, analysis_id=analysis_id)

                if attempt < max_attempts:
                    return await self.register_analysis(analysis_id, project_id, attempt + 1, max_attempts)

                else:
                    logger.error(f"Failed to start analysis {analysis_id} after {max_attempts} attempts")
                    return None, e.status_code

            else:
                logger.info(f"Pod already exists for analysis {analysis_id}, skipping start sequence")
                return None, e.status_code

        except HTTPException as e:
            logger.error(f"Failed to start analysis {analysis_id}, {e}")
            return None, e.status_code

        return None, status.HTTP_500_INTERNAL_SERVER_ERROR

    async def pod_running(self, analysis_id: str) -> bool | None:
        """Check whether a pod with the given analysis_id is already running."""
        pod_status = await self.fetch_analysis_status(analysis_id=analysis_id)
        if pod_status:
            return bool(pod_status["status"])  # If anything exists

        return None  # Error occurred and no status retrieved

    async def fetch_token_header(self) -> dict | None:
        """Append OIDC token to headers."""
        try:
            _, oidc_config = check_oidc_configs_match()
            token = await get_internal_token(oidc_config, self.settings)
            return token

        except (HTTPException, HTTPStatusError) as e:
            logger.error(f"Unable to fetch OIDC token: {e}")

    async def send_start_request(self, analysis_props: dict, kong_token: str) -> tuple[dict | None, int] | None:
        """Start a new analysis pod via the PO."""
        logger.info(f"Starting new analysis pod for {analysis_props['analysis_id']}")

        node_metadata = get_node_metadata_for_url(analysis_props["node_id"], core_client=self.core_client)
        analysis_info = get_registry_metadata_for_url(node_metadata, core_client=self.core_client)
        props = compile_analysis_pod_data(
            analysis_id=analysis_props["analysis_id"],
            project_id=analysis_props["project_id"],
            compiled_info=analysis_info,
            kong_token=kong_token,
        )

        headers = await self.fetch_token_header()
        microsvc_path = f"{get_settings().PODORC_SERVICE_URL}/po/"

        if headers:
            try:
                resp_data, status_code = await make_request(
                    url=microsvc_path,
                    method="post",
                    headers=headers,
                    data=props,
                )
                logger.info(f"Analysis start response for {analysis_props['analysis_id']}: {resp_data['status']}")
                return resp_data, status_code

            except HTTPException as e:
                logger.error(
                    f"Unable to start analysis {analysis_props['analysis_id']} due to the following error: {e}"
                )

            except ConnectError as e:
                logger.error(f"Pod Orchestrator unreachable - {e}")

        else:  # No token available or PO unreachable
            return None, status.HTTP_404_NOT_FOUND

    async def fetch_analysis_status(self, analysis_id: uuid.UUID | str) -> dict | None:
        """Fetch the status for a specific analysis run. For headless operation"""
        headers = await self.fetch_token_header()
        microsvc_path = f"{get_settings().PODORC_SERVICE_URL}/po/{analysis_id}/status"
        resp_data = None

        if headers:
            try:
                resp_data, _ = await make_request(
                    url=microsvc_path,
                    method="get",
                    headers=headers,
                )

            except HTTPException as e:
                logger.error(f"Unable to fetch the status of analysis {analysis_id} due to the following error: {e}")

            except ConnectError as e:
                logger.error(f"Unable to contact the PO: {e}")

        return resp_data

    async def get_valid_projects(self) -> set:
        """Collect the available data stores and create a set of project UUIDs with a valid data store."""
        kong_routes = None
        try:
            kong_routes = await list_projects(hub_adapter_settings=self.settings, project_id=None, detailed=False)

        except HTTPException as e:
            logger.error(f"Route retrieval failed, unable to contact Kong: {e}")

        valid_projects = set()

        if kong_routes:
            for route in kong_routes.data:
                proj_uuid_chunks = route.name.split("-")[:-1]
                proj_uuid = "-".join(proj_uuid_chunks)
                valid_projects.add(proj_uuid)

        return valid_projects

    @staticmethod
    def parse_analyses(analyses: list, valid_projects: set, ignore_run_status: bool = False) -> set:
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
            is_valid = approved == "approved" and build_status == "finished" and project_id in valid_projects

            if not ignore_run_status:
                is_valid = is_valid and not run_status  # Headless will check run status, endpoint will not

            if is_valid:
                valid_entry = (analysis_id, project_id, node_id, build_status, run_status)
                ready_analyses.add(valid_entry)

        logger.info(f"Found {len(ready_analyses)} valid analyses ready to start")
        return ready_analyses
