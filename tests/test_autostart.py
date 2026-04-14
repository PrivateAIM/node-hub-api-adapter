"""Collection of unit tests for testing autostart operation."""

import asyncio
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from flame_hub.models import AnalysisNode
from httpx import ConnectError, HTTPStatusError, RemoteProtocolError, Request, Response
from kong_admin_client import ListRoute200Response
from starlette import status

from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.conf import Settings
from hub_adapter.errors import KongConflictError, KongConnectError
from tests.constants import (
    ANALYSIS_NODES_RESP,
    KONG_ANALYSIS_SUCCESS_RESP,
    KONG_GET_ROUTE_RESPONSE,
    TEST_MOCK_ANALYSIS_ID,
    TEST_MOCK_NODE_ID,
    TEST_MOCK_PROJECT_ID,
)


class FakeKeycloak:
    key: str = "fakeKey"


class TestAutostart:
    """Autostart unit tests."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.gather_deps_patcher = patch.object(GoGoAnalysis, "gather_deps")
        self.mock_gather_deps = self.gather_deps_patcher.start()

        self.analyzer = GoGoAnalysis()

        self.analyzer.settings = Settings()
        self.analyzer.core_client = None

    @patch("hub_adapter.autostart.create_and_connect_analysis_to_project")
    @pytest.mark.asyncio
    async def test_register_analysis(self, mock_create_and_connect_analysis_to_project):
        """Test registering an analysis with kong."""
        mock_create_and_connect_analysis_to_project.return_value = KONG_ANALYSIS_SUCCESS_RESP
        resp = await self.analyzer.register_analysis(TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID)

        assert resp == (KONG_ANALYSIS_SUCCESS_RESP, status.HTTP_201_CREATED)

    @pytest.mark.asyncio
    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.GoGoAnalysis.pod_running")
    @patch("hub_adapter.autostart.create_and_connect_analysis_to_project")
    async def test_register_analysis_conflict_pod_exists(self, mock_create_and_connect, mock_pod_running, mock_logger):
        """Test registering an analysis with kong and there is already a pod running."""
        self.analyzer._log = mock_logger
        # Pod exists already
        mock_create_and_connect.side_effect = KongConflictError(
            status_code=status.HTTP_409_CONFLICT, detail={"message": "Conflict"}
        )
        mock_pod_running.return_value = True
        pod_exists_resp = await self.analyzer.register_analysis(TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID)

        # check logs
        assert mock_logger.info.call_count == 2  # Attempt log and pod exists log
        assert mock_logger.warning.call_count == 1
        mock_logger.warning.assert_called_with(
            f"Analysis {TEST_MOCK_ANALYSIS_ID} already registered, checking if pod exists..."
        )
        mock_logger.info.assert_called_with(
            f"Pod already exists for analysis {TEST_MOCK_ANALYSIS_ID}, skipping start sequence"
        )

        # Return None if pod already exists
        assert pod_exists_resp == (None, 409)

    @pytest.mark.asyncio
    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.GoGoAnalysis.pod_running")
    @patch("hub_adapter.autostart.delete_analysis")
    @patch("hub_adapter.autostart.create_and_connect_analysis_to_project")
    async def test_register_analysis_conflict_no_pod(
        self, mock_create_and_connect, mock_delete_analysis, mock_pod_running, mock_logger
    ):
        """Test registering an analysis with kong and there is a conflict but no pod running."""
        self.analyzer._log = mock_logger
        # No pod found, but consumer found, and delete was successful
        mock_create_and_connect.side_effect = KongConflictError(
            status_code=status.HTTP_409_CONFLICT, detail={"message": "Conflict"}
        )
        mock_delete_analysis.return_value = 200
        mock_pod_running.return_value = False

        max_attempts = 5
        pod_exists_resp = await self.analyzer.register_analysis(
            TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID, attempt=1, max_attempts=max_attempts
        )

        # check logs
        assert mock_logger.info.call_count == max_attempts * 2
        assert mock_logger.warning.call_count == max_attempts
        mock_logger.warning.assert_called_with(
            f"Analysis {TEST_MOCK_ANALYSIS_ID} already registered, checking if pod exists..."
        )
        mock_logger.info.assert_called_with(
            f"No pod found for {TEST_MOCK_ANALYSIS_ID}, will delete kong consumer and retry"
        )
        mock_logger.error.assert_called_with(
            f"Failed to start analysis {TEST_MOCK_ANALYSIS_ID} after {max_attempts} attempts"
        )

        # Return None if pod already exists
        assert pod_exists_resp == (None, 409)

    @pytest.mark.asyncio
    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.create_and_connect_analysis_to_project")
    async def test_register_analysis_missing_datastore(self, mock_create_and_connect, mock_logger):
        """Test registering an analysis with kong and data store is missing."""
        self.analyzer._log = mock_logger
        fake_err_msg = "Not found"
        mock_create_and_connect.side_effect = KongConnectError(
            status_code=status.HTTP_404_NOT_FOUND, detail={"message": fake_err_msg}
        )
        missing_db_resp = await self.analyzer.register_analysis(TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID)
        assert mock_logger.error.call_count == 1
        mock_logger.error.assert_called_with(f"{fake_err_msg}, failed to start analysis {TEST_MOCK_ANALYSIS_ID}")
        assert missing_db_resp == (None, 404)

    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_analysis_status")
    @pytest.mark.asyncio
    async def test_pod_running(self, mock_fetch_analysis_status):
        """Test checking whether the pod is running."""
        # Pod running
        mock_fetch_analysis_status.return_value = {TEST_MOCK_ANALYSIS_ID: "executing"}
        pod_running_resp = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert pod_running_resp  # True

        mock_fetch_analysis_status.return_value = {TEST_MOCK_ANALYSIS_ID: ""}
        pod_not_running_resp = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert not pod_not_running_resp  # False

        mock_fetch_analysis_status.return_value = None
        pod_running_error = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert pod_running_error is None

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart._get_internal_token")
    @pytest.mark.asyncio
    async def test_fetch_token_header(self, mock_fetch_token, mock_logger):
        """Test checking whether the pod is running."""
        self.analyzer._log = mock_logger
        # Success
        mock_fetch_token.return_value = {"Authorization": "Bearer test_token"}
        token_resp = await self.analyzer.fetch_token_header()
        assert token_resp == {"Authorization": "Bearer test_token"}

        # Failure
        mock_fetch_token.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="IDP can't be reached"
        )
        no_connect_error_resp = await self.analyzer.fetch_token_header()
        assert no_connect_error_resp is None
        mock_logger.error.assert_called_with("Unable to fetch OIDC token: 503: IDP can't be reached")

        mock_fetch_token.side_effect = HTTPStatusError(
            message="IDP exchange failed",
            request=Request(url="/", method="GET"),
            response=Response(status_code=status.HTTP_401_UNAUTHORIZED),
        )
        exchange_error_resp = await self.analyzer.fetch_token_header()
        assert exchange_error_resp is None
        mock_logger.error.assert_called_with("Unable to fetch OIDC token: IDP exchange failed")

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.make_request")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    @patch("hub_adapter.autostart.compile_analysis_pod_data")
    @patch("hub_adapter.autostart.get_node_metadata_for_url")
    @patch("hub_adapter.autostart.get_registry_metadata_for_url")
    @pytest.mark.asyncio
    async def test_send_start_request(
        self, mock_registry_metadata, mock_node_metadata, mock_pod_data, mock_token_header, mock_request, mock_logger
    ):
        """Test starting an analysis pod."""
        self.analyzer._log = mock_logger
        # These first methods are for feeding into one another
        mock_registry_metadata.return_value = {}  # Not needed
        mock_node_metadata.return_value = {}  # Not needed
        mock_pod_data.return_value = {}  # Not needed
        mock_token_header.return_value = {"foo"}  # Just need something

        sim_input = {
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
            "node_id": TEST_MOCK_ANALYSIS_ID,
        }

        # Working
        mock_request.return_value = {TEST_MOCK_ANALYSIS_ID: "executing"}, status.HTTP_201_CREATED
        pod_resp, status_code = await self.analyzer.send_start_request(sim_input, "fakeKongToken")
        assert mock_logger.info.call_count == 2
        mock_logger.info.assert_called_with(f"Analysis start response for {TEST_MOCK_ANALYSIS_ID}: executing")
        assert pod_resp == {TEST_MOCK_ANALYSIS_ID: "executing"}
        assert status_code == status.HTTP_201_CREATED

        # Problem
        po_err_msg = "she's dead jim"
        mock_request.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=po_err_msg)
        pod_failed_resp = await self.analyzer.send_start_request(sim_input, "fakeKongToken")
        assert mock_logger.error.call_count == 1
        mock_logger.error.assert_called_with(
            f"Unable to start analysis {TEST_MOCK_ANALYSIS_ID} due to the following error: 503: she's dead jim"
        )
        assert pod_failed_resp == (po_err_msg, status.HTTP_503_SERVICE_UNAVAILABLE)

    @pytest.mark.asyncio
    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.make_request")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    async def test_fetch_analysis_status(self, mock_header, mock_request, mock_logger):
        """Test fetching the status of an analysis."""
        self.analyzer._log = mock_logger
        mock_header.return_value = {"foo"}  # Just need something

        # Success
        mock_request.return_value = {"status": "executing"}, status.HTTP_200_OK
        status_resp = await self.analyzer.fetch_analysis_status(TEST_MOCK_ANALYSIS_ID)
        assert status_resp == {"status": "executing"}

        # Failures
        mock_request.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="she's dead jim"
        )
        status_http_failed_resp = await self.analyzer.fetch_analysis_status(TEST_MOCK_ANALYSIS_ID)
        assert mock_logger.error.call_count == 1
        mock_logger.error.assert_called_with(
            f"Unable to fetch the status of analysis {TEST_MOCK_ANALYSIS_ID} due "
            f"to the following error: 503: she's dead jim"
        )
        assert status_http_failed_resp is None

        mock_request.side_effect = ConnectError(message="Connection failure")
        status_connect_failed_resp = await self.analyzer.fetch_analysis_status(TEST_MOCK_ANALYSIS_ID)
        assert mock_logger.error.call_count == 2  # Includes the error above
        mock_logger.error.assert_called_with("Unable to contact the PO: Connection failure")
        assert status_connect_failed_resp is None

    @pytest.mark.asyncio
    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.list_projects")
    async def test_get_valid_projects(self, mock_projects, mock_logger):
        """Test getting and parsing projects (routes) from kong."""
        self.analyzer._log = mock_logger
        # Success
        mock_projects.return_value = ListRoute200Response(**KONG_GET_ROUTE_RESPONSE)
        projects = await self.analyzer.get_valid_projects()
        assert projects == {TEST_MOCK_PROJECT_ID}
        assert isinstance(projects, set)

        # Failure
        mock_projects.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kong off")
        no_projects = await self.analyzer.get_valid_projects()
        assert no_projects == set()
        mock_logger.error.assert_called_with("Route retrieval failed, unable to contact Kong: 503: Kong off")

    def test_parse_analyses(self):
        """Test parsing analyses choosing whether they should be started i.e. built but no run status."""
        formatted_analyses = [AnalysisNode(**analysis) for analysis in ANALYSIS_NODES_RESP]
        assert len(formatted_analyses) == 6
        ready_analyses = self.analyzer.parse_analyses(formatted_analyses, {TEST_MOCK_PROJECT_ID})

        assert len(ready_analyses) == 1
        assert isinstance(ready_analyses, set)
        analysis_id, project_id, node_id, build_status, execution_status = list(ready_analyses).pop()

        assert analysis_id == TEST_MOCK_ANALYSIS_ID
        assert project_id == TEST_MOCK_PROJECT_ID
        assert node_id == TEST_MOCK_NODE_ID
        assert build_status == "executed"
        assert execution_status is None


class TestAutostartErrorAndEvents:
    """Additional unit tests for the autostart module to check expected errors and coverage."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.gather_deps_patcher = patch.object(GoGoAnalysis, "gather_deps")
        self.mock_gather_deps = self.gather_deps_patcher.start()

        self.analyzer = GoGoAnalysis()
        self.analyzer.settings = Settings()
        self.analyzer.core_client = None

    def teardown_method(self):
        """Clean up patches after each test method."""
        self.gather_deps_patcher.stop()

    @patch("hub_adapter.autostart.get_node_id")
    @patch("hub_adapter.autostart.get_node_type_cache")
    @pytest.mark.asyncio
    async def test_describe_node_success(self, mock_node_type_cache, mock_get_node_id):
        """Test describe_node returns node_id and node_type successfully."""
        mock_get_node_id.return_value = TEST_MOCK_NODE_ID
        mock_node_type_cache.return_value = {"type": "default"}

        node_id, node_type = await self.analyzer.describe_node()

        assert node_id == TEST_MOCK_NODE_ID
        assert node_type == "default"
        mock_get_node_id.assert_called_once()
        mock_node_type_cache.assert_called_once()

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.make_request")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    @patch("hub_adapter.autostart.compile_analysis_pod_data")
    @patch("hub_adapter.autostart.get_node_metadata_for_url")
    @patch("hub_adapter.autostart.get_registry_metadata_for_url")
    @pytest.mark.asyncio
    async def test_send_start_request_http_status_error(
        self, mock_registry_metadata, mock_node_metadata, mock_pod_data, mock_token_header, mock_request, mock_logger
    ):
        """Test send_start_request with HTTPStatusError."""
        self.analyzer._log = mock_logger
        mock_registry_metadata.return_value = {}
        mock_node_metadata.return_value = {}
        mock_pod_data.return_value = {}
        mock_token_header.return_value = {"Authorization": "Bearer token"}

        sim_input = {
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
            "node_id": TEST_MOCK_NODE_ID,
        }

        mock_request.side_effect = HTTPStatusError(
            message="Server error",
            request=Request(method="POST", url="/po/"),
            response=Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, text="Internal error"),
        )

        resp, status_code = await self.analyzer.send_start_request(sim_input, "kong_token")

        assert status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp["message"] == "PodOrc encountered the following error: Internal error"
        mock_logger.error.assert_called_once()

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.make_request")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    @patch("hub_adapter.autostart.compile_analysis_pod_data")
    @patch("hub_adapter.autostart.get_node_metadata_for_url")
    @patch("hub_adapter.autostart.get_registry_metadata_for_url")
    @pytest.mark.asyncio
    async def test_send_start_request_connect_error(
        self, mock_registry_metadata, mock_node_metadata, mock_pod_data, mock_token_header, mock_request, mock_logger
    ):
        """Test send_start_request with ConnectError."""
        self.analyzer._log = mock_logger
        mock_registry_metadata.return_value = {}
        mock_node_metadata.return_value = {}
        mock_pod_data.return_value = {}
        mock_token_header.return_value = {"Authorization": "Bearer token"}

        sim_input = {
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
            "node_id": TEST_MOCK_NODE_ID,
        }

        mock_request.side_effect = ConnectError(message="Cannot connect to Pod Orchestrator")

        resp, status_code = await self.analyzer.send_start_request(sim_input, "kong_token")

        assert status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp is None
        mock_logger.error.assert_called_once()

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    @patch("hub_adapter.autostart.compile_analysis_pod_data")
    @patch("hub_adapter.autostart.get_node_metadata_for_url")
    @patch("hub_adapter.autostart.get_registry_metadata_for_url")
    @pytest.mark.asyncio
    async def test_send_start_request_no_token(
        self, mock_registry_metadata, mock_node_metadata, mock_pod_data, mock_token_header, mock_logger
    ):
        """Test send_start_request when token header is None."""
        mock_token_header.return_value = None

        sim_input = {
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
            "node_id": TEST_MOCK_NODE_ID,
        }

        resp, status_code = await self.analyzer.send_start_request(sim_input, "kong_token")

        assert status_code == status.HTTP_404_NOT_FOUND
        assert resp is None

    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_analysis_status")
    @pytest.mark.asyncio
    async def test_pod_running_with_different_statuses(self, mock_fetch_status):
        """Test pod_running with all possible pod statuses."""
        from hub_adapter.schemas.podorc import PodStatus

        # Test all running statuses
        running_statuses = [
            PodStatus.STARTED,
            PodStatus.STARTING,
            PodStatus.EXECUTING,
            PodStatus.STOPPING,
            PodStatus.RUNNING,
        ]

        for status_val in running_statuses:
            mock_fetch_status.return_value = {TEST_MOCK_ANALYSIS_ID: status_val}
            result = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
            assert result is True, f"Failed for status: {status_val}"

        # Test non-running statuses
        non_running_statuses = [
            PodStatus.EXECUTED,
            PodStatus.FAILED,
            PodStatus.STOPPED,
            None,
            "",
        ]

        for status_val in non_running_statuses:
            mock_fetch_status.return_value = {TEST_MOCK_ANALYSIS_ID: status_val}
            result = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
            assert result is False, f"Failed for status: {status_val}"

        # Test missing analysis_id
        mock_fetch_status.return_value = {"other_id": PodStatus.EXECUTING}
        result = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert result is False

    @patch("hub_adapter.autostart.logger")
    def test_parse_analyses_no_datastore_required(self, mock_logger):
        """Test parse_analyses when datastore is not required."""
        formatted_analyses = [AnalysisNode(**analysis) for analysis in ANALYSIS_NODES_RESP]
        ready_analyses = self.analyzer.parse_analyses(
            formatted_analyses, {TEST_MOCK_PROJECT_ID}, datastore_required=False
        )

        assert len(ready_analyses) >= 1
        assert isinstance(ready_analyses, set)

    @patch("hub_adapter.autostart.logger")
    def test_parse_analyses_without_time_check(self, mock_logger):
        """Test parse_analyses when time and status check is disabled."""
        formatted_analyses = [AnalysisNode(**analysis) for analysis in ANALYSIS_NODES_RESP]
        ready_analyses = self.analyzer.parse_analyses(
            formatted_analyses, {TEST_MOCK_PROJECT_ID}, enforce_time_and_status_check=False
        )

        # Should include analyses that are approved and executed regardless of time
        assert len(ready_analyses) >= 1

    @patch("hub_adapter.autostart.logger")
    def test_parse_analyses_empty_list(self, mock_logger):
        """Test parse_analyses with empty analysis list."""
        ready_analyses = self.analyzer.parse_analyses([], {TEST_MOCK_PROJECT_ID})
        assert len(ready_analyses) == 0
        assert isinstance(ready_analyses, set)

    @patch("hub_adapter.autostart.logger")
    def test_parse_analyses_no_valid_projects(self, mock_logger):
        """Test parse_analyses with no valid projects."""
        formatted_analyses = [AnalysisNode(**analysis) for analysis in ANALYSIS_NODES_RESP]
        ready_analyses = self.analyzer.parse_analyses(formatted_analyses, set())
        assert len(ready_analyses) == 0


class TestAutostartManager:
    """Unit tests for AutostartManager."""

    def test_autostart_manager_init(self):
        """Test AutostartManager initialization."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()

        assert manager._task is None
        assert manager._enabled is False

    @patch("hub_adapter.autostart.load_persistent_settings")
    @patch("hub_adapter.autostart.logger")
    @pytest.mark.asyncio
    async def test_autostart_manager_update_start(self, mock_logger, mock_load_settings):
        """Test AutostartManager starting autostart."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()
        manager._log = mock_logger
        mock_settings = MagicMock()
        mock_settings.autostart.enabled = True
        mock_settings.autostart.interval = 30
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.autostart.GoGoAnalysis"):
            await manager.update()

            assert manager._enabled is True
            assert manager._task is not None
            mock_logger.info.assert_called()

        # Clean up
        await manager.stop()

    @patch("hub_adapter.autostart.load_persistent_settings")
    @patch("hub_adapter.autostart.logger")
    @pytest.mark.asyncio
    async def test_autostart_manager_update_stop(self, mock_logger, mock_load_settings):
        """Test AutostartManager stopping autostart."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()

        # First start it
        mock_settings = MagicMock()
        mock_settings.autostart.enabled = True
        mock_settings.autostart.interval = 30
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.autostart.GoGoAnalysis"):
            await manager.update()
            assert manager._enabled is True

            # Now stop it
            mock_settings.autostart.enabled = False
            await manager.update()

            assert manager._enabled is False

    @patch("hub_adapter.autostart.load_persistent_settings")
    @patch("hub_adapter.autostart.logger")
    @pytest.mark.asyncio
    async def test_autostart_manager_update_restart(self, mock_logger, mock_load_settings):
        """Test AutostartManager restart with changed interval."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()

        # Start with interval 30
        mock_settings = MagicMock()
        mock_settings.autostart.enabled = True
        mock_settings.autostart.interval = 30
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.autostart.GoGoAnalysis"):
            await manager.update()
            assert manager._enabled is True
            first_task = manager._task

            # Change interval to 60
            mock_settings.autostart.interval = 60
            await manager.update()

            # Should have created a new task
            assert manager._task != first_task or manager._task is None

        # Clean up
        await manager.stop()

    @patch("hub_adapter.autostart.logger")
    @pytest.mark.asyncio
    async def test_autostart_manager_stop(self, mock_logger):
        """Test AutostartManager stop."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()
        manager._enabled = True
        manager._task = asyncio.create_task(asyncio.sleep(10))

        await manager.stop()

        assert manager._enabled is False

    @patch("hub_adapter.autostart.load_persistent_settings")
    @patch("hub_adapter.autostart.logger")
    @pytest.mark.asyncio
    async def test_autostart_manager_run_autostart_error_handling(self, mock_logger, mock_load_settings):
        """Test _run_autostart error handling."""
        from hub_adapter.autostart import AutostartManager

        manager = AutostartManager()
        manager._log = mock_logger
        mock_settings = MagicMock()
        mock_settings.autostart.enabled = True
        mock_settings.autostart.interval = 1
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.autostart.GoGoAnalysis") as mock_gogos:
            mock_instance = MagicMock()
            mock_gogos.return_value = mock_instance
            mock_instance.auto_start_analyses.side_effect = Exception("Test error")

            task = asyncio.create_task(manager._run_autostart(interval=1))

            # Let it run for a short time
            await asyncio.sleep(0.5)

            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

            # Should have logged the error
            mock_logger.error.assert_called()


class TestAutostartWithRemoteProtocolError:
    """Tests for send_start_request with RemoteProtocolError."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gather_deps_patcher = patch.object(GoGoAnalysis, "gather_deps")
        self.mock_gather_deps = self.gather_deps_patcher.start()
        self.analyzer = GoGoAnalysis()
        self.analyzer.settings = Settings()
        self.analyzer.core_client = None

    def teardown_method(self):
        """Clean up patches."""
        self.gather_deps_patcher.stop()

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.make_request")
    @patch("hub_adapter.autostart.GoGoAnalysis.fetch_token_header")
    @patch("hub_adapter.autostart.compile_analysis_pod_data")
    @patch("hub_adapter.autostart.get_node_metadata_for_url")
    @patch("hub_adapter.autostart.get_registry_metadata_for_url")
    @pytest.mark.asyncio
    async def test_send_start_request_remote_protocol_error(
        self, mock_registry_metadata, mock_node_metadata, mock_pod_data, mock_token_header, mock_request, mock_logger
    ):
        """Test send_start_request with RemoteProtocolError."""
        mock_registry_metadata.return_value = {}
        mock_node_metadata.return_value = {}
        mock_pod_data.return_value = {}
        mock_token_header.return_value = {"Authorization": "Bearer token"}

        sim_input = {
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
            "node_id": TEST_MOCK_NODE_ID,
        }

        mock_request.side_effect = RemoteProtocolError(message="Remote protocol error")

        resp, status_code = await self.analyzer.send_start_request(sim_input, "kong_token")

        assert status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp is None
