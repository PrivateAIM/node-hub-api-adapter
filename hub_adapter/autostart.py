"""Collection of methods for running in autostart mode in which analyses are detected and started automatically."""

import asyncio
import logging
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from flame_hub import HubAPIError
from httpx import ConnectError, HTTPStatusError, ReadTimeout, RemoteProtocolError
from starlette import status

from hub_adapter.auth import _get_internal_token
from hub_adapter.constants import ServiceTag
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
from hub_adapter.middleware import log_event
from hub_adapter.routers.hub import (
    _format_query_params,
    list_analysis_nodes,
)
from hub_adapter.routers.kong import (
    create_and_connect_analysis_to_project,
    delete_analysis,
    list_projects,
)
from hub_adapter.schemas.podorc import PodStatus
from hub_adapter.user_settings import load_persistent_settings
from hub_adapter.utils import _check_data_required


class GoGoAnalysis:
    def __init__(self):
        self.settings = None
        self.core_client = None

        self.gather_deps()  # populates self.settings and self.core_client

    def gather_deps(self):
        """Gather all the dependencies needed to run the autostart mode."""
        settings = get_settings()
        ssl_ctx = get_ssl_context(settings)
        hub_auth = get_flame_hub_auth_flow(ssl_ctx, settings)
        core_client = get_core_client(hub_auth, ssl_ctx, settings)

        self.settings = settings
        self.core_client = core_client

    async def auto_start_analyses(self) -> set | None:
        """Gather and iterate over analyses from hub and start them if they pass checks."""
        analyses_started = set()

        try:
            node_id, node_type = await self.describe_node()

        except (HubAPIError, HTTPException) as e:
            log_event(
                "autostart.hub.connect_error",
                event_description=f"Unable to connect to the Hub: {e}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )
            return None

        formatted_query_params = _format_query_params({"sort": "-updated_at", "include": "analysis"})

        try:
            analyses = await list_analysis_nodes(
                core_client=self.core_client,
                node_id=node_id,
                query_params=formatted_query_params,
            )

        except ConnectError as e:
            log_event(
                "autostart.analysis.hub_fetch_error",
                event_description=f"Unable to start analyses, error connecting to Hub: {e}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )
            return analyses_started

        valid_projects = await self.get_valid_projects()
        datastore_required = _check_data_required(node_type)
        ready_to_start_analyses = self.parse_analyses(analyses, valid_projects, datastore_required)

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

    async def describe_node(self) -> tuple[str | None, str] | None:
        """Get node information from cache, and if not present, get from Hub and set cache."""
        node_id = await get_node_id(core_client=self.core_client, settings=self.settings)
        node_type_cache = await get_node_type_cache(settings=self.settings, core_client=self.core_client)
        node_type = node_type_cache["type"]

        return node_id, node_type

    async def register_analysis(
        self, analysis_id: str, project_id: str, attempt: int = 1, max_attempts: int = 5
    ) -> tuple[dict | None, int] | None:
        """Register an analysis with kong."""
        log_event(
            "autostart.analysis.register",
            event_description=f"Attempt {attempt} at starting analysis {analysis_id}",
            level=logging.INFO,
            service=ServiceTag.AUTOSTART,
        )
        try:
            kong_resp = await create_and_connect_analysis_to_project(
                settings=self.settings, project_id=project_id, analysis_id=analysis_id
            )
            return kong_resp, status.HTTP_201_CREATED

        except KongConnectError as e:
            log_event(
                "autostart.analysis.register_error",
                event_description=f"{e.detail['message']}, failed to start analysis {analysis_id}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )
            return None, e.status_code

        except KongConflictError as e:
            log_event(
                "autostart.analysis.conflict",
                event_description=f"Analysis {analysis_id} already registered, checking if pod exists...",
                level=logging.WARNING,
                service=ServiceTag.AUTOSTART,
            )
            pod_exists = await self.pod_running(analysis_id)
            if pod_exists is None:  # Status could not be obtained, skip and try later
                log_event(
                    "autostart.analysis.status_unknown",
                    event_description=f"Status for analysis {analysis_id} could not be obtained, will try again",
                    level=logging.WARNING,
                    service=ServiceTag.AUTOSTART,
                )
                pass

            elif not pod_exists:  # Status obtained and if not running, delete kong consumer
                log_event(
                    "autostart.analysis.orphan_cleanup",
                    event_description=f"No pod found for {analysis_id}, will delete kong consumer and retry",
                    level=logging.INFO,
                    service=ServiceTag.AUTOSTART,
                )
                await delete_analysis(settings=self.settings, analysis_id=analysis_id)

                if attempt < max_attempts:
                    return await self.register_analysis(analysis_id, project_id, attempt + 1, max_attempts)

                else:
                    log_event(
                        "autostart.analysis.max_retries",
                        event_description=f"Failed to start analysis {analysis_id} after {max_attempts} attempts",
                        level=logging.ERROR,
                        service=ServiceTag.AUTOSTART,
                    )
                    return None, e.status_code

            else:
                log_event(
                    "autostart.analysis.already_running",
                    event_description=f"Pod already exists for analysis {analysis_id}, skipping start sequence",
                    level=logging.INFO,
                    service=ServiceTag.AUTOSTART,
                )
                return None, e.status_code

        except HTTPException as e:
            log_event(
                "autostart.analysis.register_error",
                event_description=f"Failed to start analysis {analysis_id}, {e}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )
            return None, e.status_code

        return None, status.HTTP_500_INTERNAL_SERVER_ERROR

    async def pod_running(self, analysis_id: str) -> bool | None:
        """Check whether a pod with the given analysis_id is already running."""
        pod_status = await self.fetch_analysis_status(analysis_id=analysis_id)
        if pod_status is not None:
            # null, 'executed', 'failed', and 'stopped' means no pod present
            existing_pod_statuses = (
                PodStatus.STARTED,
                PodStatus.STARTING,
                PodStatus.EXECUTING,
                PodStatus.STOPPING,
                PodStatus.RUNNING,  # Deprecated
            )
            return bool(analysis_id in pod_status and pod_status[analysis_id] in existing_pod_statuses)

        return pod_status  # Error occurred and no status retrieved

    async def fetch_token_header(self) -> dict | None:
        """Append OIDC token to headers."""
        try:
            token = await _get_internal_token(self.settings)
            return token

        except (HTTPException, HTTPStatusError) as e:
            log_event(
                "autostart.token.error",
                event_description=f"Unable to fetch OIDC token: {e}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )

    async def send_start_request(self, analysis_props: dict, kong_token: str) -> tuple[dict | None, int] | None:
        """Start a new analysis pod via the PO."""
        log_event(
            "autostart.analysis.starting",
            event_description=f"Starting new analysis pod for {analysis_props['analysis_id']}",
            level=logging.INFO,
            service=ServiceTag.AUTOSTART,
        )

        node_metadata = get_node_metadata_for_url(analysis_props["node_id"], core_client=self.core_client)
        analysis_info = get_registry_metadata_for_url(node_metadata, core_client=self.core_client)

        analysis_id = analysis_props["analysis_id"]
        project_id = analysis_props["project_id"]

        props = compile_analysis_pod_data(
            analysis_id=analysis_id,
            project_id=project_id,
            compiled_info=analysis_info,
            kong_token=kong_token,
        )

        headers = await self.fetch_token_header()
        microsvc_path = f"{get_settings().podorc_service_url}/po/"

        if headers:
            try:
                resp_data, status_code = await make_request(
                    url=microsvc_path,
                    method="post",
                    headers=headers,
                    data=props,
                )
                log_event(
                    "autostart.analysis.start_response",
                    event_description=f"Analysis start response for {analysis_id}: {resp_data[analysis_id]}",
                    level=logging.INFO,
                    service=ServiceTag.AUTOSTART,
                )
                return resp_data, status_code

            except HTTPException as e:
                log_event(
                    "autostart.analysis.start_error",
                    event_description=f"Unable to start analysis {analysis_id} due to the following error: {e}",
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )
                return e.detail, e.status_code

            except HTTPStatusError as e:
                log_event(
                    "autostart.analysis.start_error",
                    event_description=(
                        f"Unable to start analysis {analysis_id} due to the following error: {e.response.text}"
                    ),
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )
                resp = {
                    "message": f"PodOrc encountered the following error: {e.response.text}",
                    "service": "PO",
                    "status_code": e.response.status_code,
                }
                return resp, e.response.status_code

            except (ConnectError, RemoteProtocolError) as e:
                log_event(
                    "autostart.podorc.unreachable",
                    event_description=f"Pod Orchestrator unreachable - {e}",
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )
                return None, status.HTTP_500_INTERNAL_SERVER_ERROR

            except ReadTimeout:
                log_event(
                    "autostart.analysis.timeout",
                    event_description=(
                        f"Analysis {analysis_props['analysis_id']} taking longer than usual to start,"
                        " waiting 60 seconds"
                    ),
                    level=logging.WARNING,
                    service=ServiceTag.AUTOSTART,
                )
                time.sleep(60)
                resp = {
                    "message": "PodOrc failed to respond in time likely due to an image pull taking too long",
                    "service": "PO",
                    "status_code": status.HTTP_408_REQUEST_TIMEOUT,
                }
                return resp, status.HTTP_408_REQUEST_TIMEOUT

        else:  # No token available or PO unreachable
            log_event(
                "autostart.analysis.no_token",
                event_description="PO failed to start the analysis due to a missing token or is unreachable",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )
            return None, status.HTTP_404_NOT_FOUND

    async def fetch_analysis_status(self, analysis_id: uuid.UUID | str) -> dict | None:
        """Fetch the status for a specific analysis run. For autostart operation"""
        headers = await self.fetch_token_header()
        microsvc_path = f"{get_settings().podorc_service_url}/po/status/{analysis_id}"
        resp_data = None

        if headers:
            try:
                resp_data, _ = await make_request(url=microsvc_path, method="get", headers=headers, service="PodOrc")

            except HTTPException as e:
                log_event(
                    "autostart.analysis.status_error",
                    event_description=(
                        f"Unable to fetch the status of analysis {analysis_id} due to the following error: {e}"
                    ),
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )

            except ConnectError as e:
                log_event(
                    "autostart.podorc.unreachable",
                    event_description=f"Unable to contact the PO: {e}",
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )

        return resp_data

    async def get_valid_projects(self) -> set:
        """Collect the available data stores and create a set of project UUIDs with a valid data store."""
        kong_routes = None
        try:
            kong_routes = await list_projects(settings=self.settings, detailed=False)

        except HTTPException as e:
            log_event(
                "autostart.kong.route_error",
                event_description=f"Route retrieval failed, unable to contact Kong: {e}",
                level=logging.ERROR,
                service=ServiceTag.AUTOSTART,
            )

        valid_projects = set()

        if kong_routes:
            for route in kong_routes.data:
                proj_uuid_chunks = route.name.split("-")[:-1]
                proj_uuid = "-".join(proj_uuid_chunks)
                valid_projects.add(proj_uuid)

        return valid_projects

    def parse_analyses(
        self,
        analyses: list,
        valid_projects: set,
        datastore_required: bool = True,
        enforce_time_and_status_check: bool = True,
    ) -> set:
        """Iterate through analyses and check whether they are approved, built, and have a run status."""
        ready_analyses = set()
        for entry in analyses:
            (analysis_id, project_id, node_id, build_status, run_status, approved, created_at, distribution_status) = (
                str(entry.analysis_id),
                str(entry.analysis.project_id),
                str(entry.node_id),
                entry.analysis.build_status,
                entry.execution_status,
                entry.approval_status,
                entry.created_at,  # Already parsed as datetime object from python hub client
                entry.analysis.distribution_status,
            )

            is_valid = approved == "approved" and build_status == "executed" and distribution_status == "executed"

            if enforce_time_and_status_check and is_valid:
                # Need timezone.utc to make it offset-aware otherwise will not work with created_at datetime obj
                is_recent = (datetime.now(UTC) - created_at) < timedelta(hours=24)
                is_valid = is_valid and is_recent and not run_status

            if datastore_required and is_valid:  # If aggregator, then skip this since kong route is not needed
                is_valid = is_valid and project_id in valid_projects
                if not is_valid:
                    log_event(
                        "autostart.analysis.invalid_project",
                        event_description=(
                            f"Cannot start analysis {analysis_id} because its project with ID {project_id}"
                            " is not valid. Project is either not approved or missing a data store"
                        ),
                        level=logging.INFO,
                        service=ServiceTag.AUTOSTART,
                    )

            if is_valid:
                valid_entry = (
                    analysis_id,
                    project_id,
                    node_id,
                    build_status,
                    run_status,
                )
                ready_analyses.add(valid_entry)

        log_event(
            "autostart.analysis.ready",
            event_description=f"Found {len(ready_analyses)} valid analyses ready to start",
            level=logging.INFO,
            service=ServiceTag.AUTOSTART,
        )
        return ready_analyses


class AutostartManager:
    """Manages the autostart task lifecycle."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._enabled = False

    async def update(self) -> None:
        """Update the autostart state based on current settings."""
        settings = load_persistent_settings()
        user_enabled = settings.autostart.enabled if settings.autostart else False
        interval = settings.autostart.interval if settings.autostart else 60

        if user_enabled and not self._enabled:
            # Start autostart task
            log_event(
                "autostart.started",
                event_description=f"Starting autostart with interval {interval}s",
                level=logging.INFO,
                service=ServiceTag.AUTOSTART,
            )
            self._task = asyncio.create_task(self._run_autostart(interval))
            self._enabled = True

        elif not user_enabled and self._enabled:
            # Stop autostart task
            log_event(
                "autostart.stopped",
                event_description="Stopping autostart",
                level=logging.INFO,
                service=ServiceTag.AUTOSTART,
            )
            if self._task and not self._task.done():
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task

            self._task = None
            self._enabled = False

        elif user_enabled and self._enabled:
            # Interval might have changed, restart if needed
            if self._task and not self._task.done():
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task

            log_event(
                "autostart.restarted",
                event_description=f"Restarting autostart with new interval {interval}s",
                level=logging.INFO,
                service=ServiceTag.AUTOSTART,
            )
            self._task = asyncio.create_task(self._run_autostart(interval))

    async def _run_autostart(self, interval: int) -> None:
        """Run the autostart probing loop."""
        analysis_initiator = GoGoAnalysis()
        while True:
            try:
                log_event(
                    "autostart.poll",
                    event_description="Checking for new analyses to start",
                    level=logging.INFO,
                    service=ServiceTag.AUTOSTART,
                )
                await analysis_initiator.auto_start_analyses()

            except Exception as e:
                log_event(
                    "autostart.error",
                    event_description=f"Error during autostart: {e}",
                    level=logging.ERROR,
                    service=ServiceTag.AUTOSTART,
                )

            await asyncio.sleep(interval)

    async def stop(self) -> None:
        """Stop the autostart task."""
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

        self._enabled = False
