"""Collection of methods for running in autostart mode in which analyses are detected and started automatically."""

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from flame_hub import HubAPIError
from httpx import ConnectError, HTTPStatusError, ReadTimeout, RemoteProtocolError
from starlette import status

from hub_adapter.auth import _get_internal_token
from hub_adapter.constants import SERVICE_NAME
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
from hub_adapter.event_logging import EventLogger, get_event_logger
from hub_adapter.models.events import ANNOTATED_EVENTS, EventTag
from hub_adapter.oidc import check_oidc_configs_match
from hub_adapter.routers.hub import (
    _format_query_params,
    list_analysis_nodes,
)
from hub_adapter.routers.kong import (
    create_and_connect_analysis_to_project,
    delete_analysis,
    list_projects,
)
from hub_adapter.utils import _check_data_required, annotate_event

logger = logging.getLogger(__name__)


class GoGoAnalysis:
    def __init__(self):
        self.settings = None
        self.core_client = None
        self.event_logger: EventLogger | None = get_event_logger()

        self.gather_deps()  # populates self.settings and self.core_client

    def gather_deps(self):
        """Gather all the dependencies needed to run the autostart mode."""
        settings = get_settings()
        ssl_ctx = get_ssl_context(settings)
        hub_auth = get_flame_hub_auth_flow(ssl_ctx, settings)
        core_client = get_core_client(hub_auth, ssl_ctx, settings)

        self.settings = settings
        self.core_client = core_client

    def log_analysis(self, metadata: dict, body: str | None = None, status_code: int | None = None) -> None:
        """Log analysis info as an event."""
        if status_code:  # Overwrite if provided
            metadata["status_code"] = status_code

        annotated_event_name, tags = annotate_event(
            "autostart.analysis.create", status_code=metadata["status_code"], tags=[EventTag.AUTOSTART]
        )

        event_data = ANNOTATED_EVENTS.get(annotated_event_name)

        # Use list(set()) to prune redundant tags and list is needed to make JSON serializable
        metadata["tags"] = list(set(event_data["tags"] + tags)) if tags else event_data["tags"]
        if self.event_logger:
            self.event_logger.log_event(
                event_name=annotated_event_name,
                service_name=SERVICE_NAME,
                body=body or event_data.get("body"),  # User given body takes priority
                attributes=metadata,
            )

    async def auto_start_analyses(self) -> set | None:
        """Gather and iterate over analyses from hub and start them if they pass checks."""
        analyses_started = set()

        try:
            node_id, node_type = await self.describe_node()

        except (HubAPIError, HTTPException) as e:
            logger.error(f"Unable to connect to the Hub: {e}")
            return None

        formatted_query_params = _format_query_params({"sort": "-updated_at", "include": "analysis"})

        try:
            analyses = await list_analysis_nodes(
                core_client=self.core_client, node_id=node_id, query_params=formatted_query_params
            )

        except ConnectError as e:
            logger.error(f"Unable to start analyses, error connecting to Hub: {e}")
            return analyses_started

        valid_projects = await self.get_valid_projects()
        datastore_required = _check_data_required(node_type)
        ready_to_start_analyses = self.parse_analyses(analyses, valid_projects, datastore_required)

        for analysis in ready_to_start_analyses:
            analysis_id, project_id, node_id, _, _ = analysis
            start_resp, status_code = await self.register_and_start_analysis(
                analysis_id, project_id, node_id, node_type
            )

            self.log_analysis(
                metadata={
                    "project_id": project_id,
                    "status_code": status_code,
                    "analysis_id": analysis_id,
                },
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
        datastore_required = _check_data_required(node_type)
        if datastore_required:
            kong_resp, status_code = await self.register_analysis(analysis_id, project_id)
            if status_code != status.HTTP_201_CREATED:
                return kong_resp, status_code

            kong_token = kong_resp["keyauth"].key

        else:  # Aggregator nodes don't need a kong store nor if the data requirement is disabled
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
        node_id = await get_node_id(core_client=self.core_client, settings=self.settings)
        node_type_cache = await get_node_type_cache(settings=self.settings, core_client=self.core_client)
        node_type = node_type_cache["type"]

        return node_id, node_type

    async def register_analysis(
        self, analysis_id: str, project_id: str, attempt: int = 1, max_attempts: int = 5
    ) -> tuple[dict | None, int] | None:
        """Register an analysis with kong."""
        logger.info(f"Attempt {attempt} at starting analysis {analysis_id}")
        event_metadata = {
            "project_id": project_id,
            "analysis_id": analysis_id,
            "tags": [EventTag.KONG],
        }
        try:
            kong_resp = await create_and_connect_analysis_to_project(
                settings=self.settings, project_id=project_id, analysis_id=analysis_id
            )
            return kong_resp, status.HTTP_201_CREATED

        except KongConnectError as e:
            msg = f"{e.detail['message']}, failed to start analysis {analysis_id}"
            logger.error(msg)
            self.log_analysis(event_metadata, body=msg, status_code=e.status_code)

            return None, e.status_code

        except KongConflictError as e:
            logger.warning(f"Analysis {analysis_id} already registered, checking if pod exists...")
            pod_exists = await self.pod_running(analysis_id)
            if pod_exists is None:  # Status could not be obtained, skip and try later
                logger.warning(f"Status for analysis {analysis_id} could not be obtained, will try again")
                pass

            elif not pod_exists:  # Status obtained and if not running, delete kong consumer
                logger.info(f"No pod found for {analysis_id}, will delete kong consumer and retry")
                await delete_analysis(settings=self.settings, analysis_id=analysis_id)

                if attempt < max_attempts:
                    return await self.register_analysis(analysis_id, project_id, attempt + 1, max_attempts)

                else:
                    msg = f"Failed to start analysis {analysis_id} after {max_attempts} attempts"
                    logger.error(msg)
                    self.log_analysis(event_metadata, body=msg, status_code=e.status_code)
                    return None, e.status_code

            else:
                logger.info(f"Pod already exists for analysis {analysis_id}, skipping start sequence")
                return None, e.status_code

        except HTTPException as e:
            msg = f"Failed to start analysis {analysis_id}, {e}"
            logger.error(msg)
            self.log_analysis(event_metadata, body=msg, status_code=e.status_code)
            return None, e.status_code

        return None, status.HTTP_500_INTERNAL_SERVER_ERROR

    async def pod_running(self, analysis_id: str) -> bool | None:
        """Check whether a pod with the given analysis_id is already running."""
        pod_status = await self.fetch_analysis_status(analysis_id=analysis_id)
        if pod_status is not None:
            # null, 'executed', 'failed', and 'stopped' means no pod present
            existing_pod_statuses = ("started", "starting", "executing", "stopping")
            return bool(analysis_id in pod_status and pod_status[analysis_id] in existing_pod_statuses)

        return pod_status  # Error occurred and no status retrieved

    async def fetch_token_header(self) -> dict | None:
        """Append OIDC token to headers."""
        try:
            _, oidc_config = check_oidc_configs_match()
            token = await _get_internal_token(oidc_config, self.settings)
            return token

        except (HTTPException, HTTPStatusError) as e:
            logger.error(f"Unable to fetch OIDC token: {e}")

    async def send_start_request(self, analysis_props: dict, kong_token: str) -> tuple[dict | None, int] | None:
        """Start a new analysis pod via the PO."""
        logger.info(f"Starting new analysis pod for {analysis_props['analysis_id']}")

        node_metadata = get_node_metadata_for_url(analysis_props["node_id"], core_client=self.core_client)
        analysis_info = get_registry_metadata_for_url(node_metadata, core_client=self.core_client)

        analysis_id = analysis_props["analysis_id"]
        project_id = analysis_props["project_id"]
        event_metadata = {
            "project_id": project_id,
            "analysis_id": analysis_id,
            "tags": [EventTag.PO],
        }

        props = compile_analysis_pod_data(
            analysis_id=analysis_id,
            project_id=project_id,
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
                logger.info(f"Analysis start response for {analysis_id}: {resp_data[analysis_id]}")
                return resp_data, status_code

            except HTTPException as e:
                msg = f"Unable to start analysis {analysis_id} due to the following error: {e}"
                logger.error(msg)
                self.log_analysis(event_metadata, body=msg, status_code=e.status_code)
                return e.detail, e.status_code

            except HTTPStatusError as e:
                msg = f"Unable to start analysis {analysis_id} due to the following error: {e.response.text}"
                resp = {
                    "message": f"PodOrc encountered the following error: {e.response.text}",
                    "service": "PO",
                    "status_code": e.response.status_code,
                }
                logger.error(msg)
                self.log_analysis(event_metadata, body=msg, status_code=e.response.status_code)
                return resp, e.response.status_code

            except (ConnectError, RemoteProtocolError) as e:
                msg = f"Pod Orchestrator unreachable - {e}"
                logger.error(msg)
                self.log_analysis(event_metadata, body=msg, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                return None, status.HTTP_500_INTERNAL_SERVER_ERROR

            except ReadTimeout:
                logger.warning(
                    f"Analysis {analysis_props['analysis_id']} taking longer than usual to start, waiting 60 seconds"
                )
                time.sleep(60)
                msg = "PodOrc failed to respond in time likely due to an image pull taking too long"
                resp = {
                    "message": msg,
                    "service": "PO",
                    "status_code": status.HTTP_408_REQUEST_TIMEOUT,
                }
                self.log_analysis(event_metadata, body=msg, status_code=status.HTTP_408_REQUEST_TIMEOUT)
                return resp, status.HTTP_408_REQUEST_TIMEOUT

        else:  # No token available or PO unreachable
            self.log_analysis(
                event_metadata,
                body="PO failed to start the analysis due to a missing token or is unreachable",
                status_code=status.HTTP_404_NOT_FOUND,
            )
            return None, status.HTTP_404_NOT_FOUND

    async def fetch_analysis_status(self, analysis_id: uuid.UUID | str) -> dict | None:
        """Fetch the status for a specific analysis run. For autostart operation"""
        headers = await self.fetch_token_header()
        microsvc_path = f"{get_settings().PODORC_SERVICE_URL}/po/status/{analysis_id}"
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
            kong_routes = await list_projects(settings=self.settings, detailed=False)

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
    def parse_analyses(
        analyses: list, valid_projects: set, datastore_required: bool = True, enforce_time_and_status_check: bool = True
    ) -> set:
        """Iterate through analyses and check whether they are approved, built, and have a run status."""
        ready_analyses = set()
        for entry in analyses:
            analysis_id, project_id, node_id, build_status, execution_status, approved, created_at = (
                str(entry.analysis_id),
                str(entry.analysis.project_id),
                str(entry.node_id),
                entry.analysis.build_status,
                entry.execution_status,
                entry.approval_status,
                entry.created_at,  # Already parsed as datetime object from python hub client
            )

            is_valid = approved == "approved" and build_status == "executed"

            if enforce_time_and_status_check and is_valid:
                # Need timezone.utc to make it offset-aware otherwise will not work with created_at datetime obj
                is_recent = (datetime.now(timezone.utc) - created_at) < timedelta(hours=24)
                is_valid = is_valid and is_recent and not execution_status

            if datastore_required and is_valid:  # If aggregator, then skip this since kong route is not needed
                is_valid = is_valid and project_id in valid_projects
                if not is_valid:
                    logger.info(
                        f"Cannot start analysis {analysis_id} because its project with ID {project_id} is not valid. "
                        f"Project is either not approved or missing a data store"
                    )

            if is_valid:
                valid_entry = (analysis_id, project_id, node_id, build_status, execution_status)
                ready_analyses.add(valid_entry)

        logger.info(f"Found {len(ready_analyses)} valid analyses ready to start")
        return ready_analyses
