"""Collection of unit tests for testing the meta router module."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx import ConnectError
from starlette import status

from hub_adapter.dependencies import get_core_client, get_flame_hub_auth_flow, get_ssl_context
from hub_adapter.models.podorc import StatusResponse
from hub_adapter.routers.meta import InitializeAnalysis, initialize_analysis, terminate_analysis
from tests.constants import TEST_MOCK_ANALYSIS_ID, TEST_MOCK_NODE_ID, TEST_MOCK_PROJECT_ID


class TestMeta:
    @pytest.mark.asyncio
    @patch("hub_adapter.routers.meta.GoGoAnalysis.register_and_start_analysis")
    @patch("hub_adapter.routers.meta.GoGoAnalysis.parse_analyses")
    @patch("hub_adapter.routers.meta.GoGoAnalysis.get_valid_projects")
    @patch("flame_hub._core_client.CoreClient.find_analysis_nodes")
    @patch("hub_adapter.routers.meta.GoGoAnalysis.describe_node")
    @patch("hub_adapter.routers.meta.GoGoAnalysis.gather_deps")
    async def test_initialize_analysis(
        self,
        mock_deps,
        mock_node_info,
        mock_hub_analyses,
        mock_projects,
        mock_parsed_analyses,
        mock_start_resp,
        test_settings,
    ):
        """Test the basic steps of initializing an analysis."""
        # Setup core_client
        ctx = get_ssl_context(test_settings)
        robot = get_flame_hub_auth_flow(ctx, test_settings)
        cc = get_core_client(robot, ctx, test_settings)

        # Set mock values
        mock_deps.return_value = None
        mock_node_info.return_value = (TEST_MOCK_NODE_ID, "default")
        mock_hub_analyses.return_value = "foo"  # Just needs to be something
        mock_projects.return_value = None
        mock_parsed_analyses.return_value = [(TEST_MOCK_ANALYSIS_ID,)]
        valid_resp = {TEST_MOCK_ANALYSIS_ID: "running"}
        mock_start_resp.return_value = (valid_resp, status.HTTP_201_CREATED)

        # Input params
        fake_analysis_form = InitializeAnalysis(analysis_id=TEST_MOCK_ANALYSIS_ID, project_id=TEST_MOCK_PROJECT_ID)

        # Working
        gen_resp = await initialize_analysis(analysis_params=fake_analysis_form, core_client=cc)
        assert gen_resp == valid_resp
        assert StatusResponse.model_validate(gen_resp)

        # Returned status code not 201
        mock_start_resp.return_value = (valid_resp, status.HTTP_200_OK)
        with pytest.raises(HTTPException) as wrong_status_code_error:
            await initialize_analysis(analysis_params=fake_analysis_form, core_client=cc)
            assert wrong_status_code_error.value.status_code == status.HTTP_200_OK

        # No response from register_and_start_analysis
        mock_start_resp.return_value = ({}, status.HTTP_404_NOT_FOUND)
        with pytest.raises(HTTPException) as missing_response_error:
            await initialize_analysis(analysis_params=fake_analysis_form, core_client=cc)
            assert missing_response_error.value.status_code == status.HTTP_404_NOT_FOUND
            assert missing_response_error.value.detail == {
                "message": "Failed to initialize analysis",
                "service": "PO",
                "status_code": status.HTTP_404_NOT_FOUND,
            }

        # Analysis not ready to start i.e. not returned by parse_analyses
        mock_parsed_analyses.return_value = []
        with pytest.raises(HTTPException) as analysis_not_ready_error:
            await initialize_analysis(analysis_params=fake_analysis_form, core_client=cc)
            assert analysis_not_ready_error.value.status_code == status.HTTP_404_NOT_FOUND
            assert analysis_not_ready_error.value.detail == {
                "message": "Analysis not ready",
                "service": "Hub",
                "status_code": status.HTTP_404_NOT_FOUND,
            }

        # Analysis not found in Hub
        mock_hub_analyses.return_value = []
        with pytest.raises(HTTPException) as analysis_not_found_error:
            await initialize_analysis(analysis_params=fake_analysis_form, core_client=cc)
            assert analysis_not_found_error.value.status_code == status.HTTP_404_NOT_FOUND
            assert analysis_not_found_error.value.detail == {
                "message": f"Analysis {TEST_MOCK_ANALYSIS_ID} not found",
                "service": "Hub",
                "status_code": status.HTTP_404_NOT_FOUND,
            }

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.meta.logger")
    @patch("hub_adapter.routers.meta.make_request")
    @patch("hub_adapter.routers.meta.get_internal_token")
    @patch("hub_adapter.routers.meta.check_oidc_configs_match")
    @patch("hub_adapter.routers.meta.delete_analysis")
    async def test_terminate_analysis(
        self,
        mock_deletion,
        mock_oidc,
        mock_token,
        mock_po_request,
        mock_logger,
        test_settings,
    ):
        """Test the basic steps of terminating an analysis."""
        valid_resp = {TEST_MOCK_ANALYSIS_ID: "stopped"}

        # Mock values
        mock_deletion.return_value = None  # Don't need it
        mock_oidc.return_value = None, None  # Don't need it
        mock_token.return_value = {}  # Don't need it
        mock_po_request.return_value = (
            valid_resp,
            status.HTTP_200_OK,
        )

        # Working
        returned_data = await terminate_analysis(TEST_MOCK_ANALYSIS_ID, test_settings)
        assert returned_data == valid_resp
        assert mock_logger.info.call_count == 1
        mock_logger.info.assert_called_with(f"Analysis {TEST_MOCK_ANALYSIS_ID} was terminated")
        assert StatusResponse.model_validate(returned_data)

        # Can't connect to PodOrc
        mock_po_request.side_effect = ConnectError(message="")
        with pytest.raises(HTTPException) as po_connection_error:
            await terminate_analysis(TEST_MOCK_ANALYSIS_ID, test_settings)
            assert po_connection_error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            err_msg = "Connection Error - PO is currently unreachable"
            assert po_connection_error.value.detail == {
                "message": err_msg,
                "service": "Hub",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            }
            assert mock_logger.error.call_count == 1
            mock_logger.error.assert_called_with(err_msg)

        # Unknown error
        mock_po_request.side_effect = ValueError
        with pytest.raises(HTTPException) as unknown_error:
            await terminate_analysis(TEST_MOCK_ANALYSIS_ID, test_settings)
            assert unknown_error.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert mock_logger.error.call_count == 1

        # assert mock_logger.info.call_args_list[0] == f"Analysis {TEST_MOCK_ANALYSIS_ID} had no pods running that could be terminated"
