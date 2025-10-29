"""Collection of unit tests for testing autostart operation."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from flame_hub import HubAPIError
from flame_hub._core_client import AnalysisNode
from httpx import ConnectError, HTTPStatusError, Request, Response
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
    @patch("hub_adapter.autostart.GoGoAnalysis.pod_running")  # Reverse order from parameters
    @patch("hub_adapter.autostart.create_and_connect_analysis_to_project")
    async def test_register_analysis_conflict_pod_exists(self, mock_create_and_connect, mock_pod_running, mock_logger):
        """Test registering an analysis with kong and there is already a pod running."""
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
        mock_fetch_analysis_status.return_value = {TEST_MOCK_ANALYSIS_ID: "running"}
        pod_running_resp = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert pod_running_resp  # True

        mock_fetch_analysis_status.return_value = {TEST_MOCK_ANALYSIS_ID: ""}
        pod_not_running_resp = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert not pod_not_running_resp  # False

        mock_fetch_analysis_status.return_value = None
        pod_running_error = await self.analyzer.pod_running(TEST_MOCK_ANALYSIS_ID)
        assert pod_running_error is None

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.check_oidc_configs_match")
    @patch("hub_adapter.autostart.get_internal_token")
    @pytest.mark.asyncio
    async def test_fetch_token_header(self, mock_fetch_token, mock_config_check, mock_logger):
        """Test checking whether the pod is running."""
        # Success
        mock_fetch_token.return_value = {"Authorization": "Bearer test_token"}
        mock_config_check.return_value = True, "http://myIDP.com"
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
        mock_request.return_value = {TEST_MOCK_ANALYSIS_ID: "running"}, status.HTTP_201_CREATED
        pod_resp, status_code = await self.analyzer.send_start_request(sim_input, "fakeKongToken")
        assert mock_logger.info.call_count == 2
        mock_logger.info.assert_called_with(f"Analysis start response for {TEST_MOCK_ANALYSIS_ID}: running")
        assert pod_resp == {TEST_MOCK_ANALYSIS_ID: "running"}
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
        mock_header.return_value = {"foo"}  # Just need something

        # Success
        mock_request.return_value = {"status": "running"}, status.HTTP_200_OK
        status_resp = await self.analyzer.fetch_analysis_status(TEST_MOCK_ANALYSIS_ID)
        assert status_resp == {"status": "running"}

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
        analysis_id, project_id, node_id, build_status, run_status = list(ready_analyses).pop()

        assert analysis_id == TEST_MOCK_ANALYSIS_ID
        assert project_id == TEST_MOCK_PROJECT_ID
        assert node_id == TEST_MOCK_NODE_ID
        assert build_status == "finished"
        assert run_status is None

    @patch("hub_adapter.autostart.logger")
    @patch("hub_adapter.autostart.GoGoAnalysis.describe_node")
    @patch("hub_adapter.autostart.list_analysis_nodes")
    @patch("hub_adapter.autostart.GoGoAnalysis.get_valid_projects")
    @patch("hub_adapter.autostart.GoGoAnalysis.register_analysis")
    @patch("hub_adapter.autostart.GoGoAnalysis.send_start_request")
    @pytest.mark.asyncio
    async def test_auto_start_analyses(
        self,
        mock_start_pod,
        mock_registration,
        mock_projects,
        mock_analysis_nodes,
        mock_describe_node,
        mock_logger,
    ):
        """Test automatically starting analysis pods."""

        class FakeKeycloak:
            key: str = "fakeKey"

        mock_describe_node.return_value = TEST_MOCK_NODE_ID, "default"
        mock_analysis_nodes.return_value = [AnalysisNode(**analysis) for analysis in ANALYSIS_NODES_RESP]
        mock_projects.return_value = {TEST_MOCK_PROJECT_ID}
        mock_registration.return_value = {"keyauth": FakeKeycloak()}, status.HTTP_201_CREATED
        mock_start_pod.return_value = {}, status.HTTP_201_CREATED

        analyses_started = await self.analyzer.auto_start_analyses()
        assert len(analyses_started) == 1
        assert TEST_MOCK_ANALYSIS_ID in analyses_started

        # Aggregator starts with different key
        mock_describe_node.return_value = TEST_MOCK_NODE_ID, "aggregator"
        aggregator_started = await self.analyzer.auto_start_analyses()
        assert len(aggregator_started) == 1
        assert TEST_MOCK_ANALYSIS_ID in aggregator_started

        # Failure - Hub connection
        mock_analysis_nodes.side_effect = ConnectError(message="Service unavailable")
        no_resp = await self.analyzer.auto_start_analyses()
        assert no_resp == set()
        mock_logger.error.assert_called_with("Unable to start analyses, error connecting to Hub: Service unavailable")

        # Failure - Hub Python Client can't contact Hub
        mock_describe_node.side_effect = HubAPIError(message="Hub unavailable", request=Request(method="GET", url="/"))
        node_type_fail_resp = await self.analyzer.auto_start_analyses()
        assert node_type_fail_resp is None
        mock_logger.error.assert_called_with("Unable to connect to the Hub: Hub unavailable")

        # Failure - Hub Python Client can't contact Hub
        mock_describe_node.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Hub gone"
        )
        node_id_fail_resp = await self.analyzer.auto_start_analyses()
        assert node_id_fail_resp is None
        mock_logger.error.assert_called_with("Unable to connect to the Hub: 503: Hub gone")
