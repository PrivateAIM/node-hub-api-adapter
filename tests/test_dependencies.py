"""Collection of unit tests for testing the dependency methods."""

import logging
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from fastapi import HTTPException
from flame_hub import CoreClient
from flame_hub._auth_flows import ClientAuth
from pydantic import BaseModel
from starlette import status

from hub_adapter.dependencies import (
    compile_analysis_pod_data,
    get_core_client,
    get_flame_hub_auth_flow,
    get_node_id,
    get_node_type_cache,
    get_ssl_context,
)
from hub_adapter.errors import HubConnectError
from tests.constants import TEST_MOCK_ANALYSIS_ID, TEST_MOCK_NODE, TEST_MOCK_PROJECT_ID


class TestDeps:
    """Collection of unit tests for testing the dependency methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, test_settings):
        """Set up test fixtures before each test method."""
        with patch("hub_adapter.dependencies.get_settings") as mock_settings:
            mock_settings.return_value = test_settings
            self.mock_settings = mock_settings.return_value

            # Clear cache before creating context
            get_ssl_context.cache_clear()

            self.ctx = get_ssl_context(self.mock_settings)

            # Create fake core client
            auth = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
            self.cc = get_core_client(auth, self.ctx, self.mock_settings)

            yield  # Test runs here

    def test_get_ssl_context(self, test_settings):
        """Test the get_ssl_context method."""

        # Clear the cache to avoid conflicts
        get_ssl_context.cache_clear()

        cert_file_path = Path(__file__).resolve().parent.joinpath("assets/test.ssl.pem")
        non_existent_cert = Path("./foo.pem")

        assert cert_file_path.exists()
        assert not non_existent_cert.exists()

        # Missing file
        no_context = get_ssl_context(self.mock_settings)
        assert len(no_context._ctx.get_ca_certs()) == 0

        # Valid file
        get_ssl_context.cache_clear()

        added_certs_settings = test_settings.model_copy(update={"extra_ca_certs": str(cert_file_path)})

        context = get_ssl_context(added_certs_settings)
        assert context is not None
        assert len(context._ctx.get_ca_certs()) == 2  # 2 certificates in test file

    def test_hub_auth_flow(self, test_settings):
        """Test the get_flame_hub_auth_flow method."""

        working_auth = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
        assert isinstance(working_auth, ClientAuth)

        # Missing HUB_ROBOT_USER should raise ValueError
        missing_node_client_user_settings = test_settings.model_copy(update={"hub_node_client_id": ""})
        with pytest.raises(ValueError):
            get_flame_hub_auth_flow(self.ctx, missing_node_client_user_settings)

        # Non UUID HUB_ROBOT_USER should raise HTTPException error
        wrong_node_client_id_settings = test_settings.model_copy(update={"hub_node_client_id": "foo"})
        with pytest.raises(HTTPException) as badUser:
            get_flame_hub_auth_flow(self.ctx, wrong_node_client_id_settings)

        assert badUser.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid node client ID" in badUser.value.detail["message"]

    def test_get_core_client(self):
        """Test the get_core_client method."""
        auth = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
        cc = get_core_client(auth, self.ctx, self.mock_settings)
        assert isinstance(cc, CoreClient)

    @pytest.mark.asyncio
    async def test_get_node_id(self):
        """Test the get_node_id method."""
        # Working test
        with patch("flame_hub._core_client.CoreClient.find_nodes") as node_response:
            node_response.return_value = [TEST_MOCK_NODE]
            correct_node_id = await get_node_id(self.cc, self.mock_settings, force_refresh=True)

        assert correct_node_id == str(TEST_MOCK_NODE.id)

        # Test when Hub is down
        with (
            patch(
                "flame_hub._core_client.CoreClient.find_nodes", side_effect=httpx2.ConnectError(message="Hub is dead")
            ),
            pytest.raises(HubConnectError) as hubError,
        ):
            await get_node_id(self.cc, self.mock_settings, force_refresh=True)

        assert hubError.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @patch("hub_adapter.dependencies.get_node_id")
    @pytest.mark.asyncio
    async def test_get_node_type_cache(self, mock_node_id):
        """Test the get_node_type_cache method."""
        mock_node_id.return_value = TEST_MOCK_NODE.id
        with patch("flame_hub._core_client.CoreClient.get_node") as cc_response:
            cc_response.side_effect = httpx2.ConnectError(message="Hub is dead")

            with pytest.raises(HubConnectError) as hubError:
                await get_node_type_cache(self.mock_settings, self.cc)

            assert hubError.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            cc_response.side_effect = None
            cc_response.return_value = TEST_MOCK_NODE

            good_cache = await get_node_type_cache(self.mock_settings, self.cc)
            assert good_cache["type"] == TEST_MOCK_NODE.type

    def test_compile_analysis_pod_data(self):
        """Test the compile_analysis_pod_data method."""
        kong_token = "fakeKongToken"

        compiled_info = compile_analysis_pod_data(
            TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID, kong_token
        )

        expected_result = {
            "analysis_id": str(TEST_MOCK_ANALYSIS_ID),
            "project_id": str(TEST_MOCK_PROJECT_ID),
            "kong_token": kong_token,
        }

        assert compiled_info == expected_result

    @patch("hub_adapter.dependencies.log_event")
    def test_make_log_hook_calls_log_event(self, mock_log_event):
        """make_log_hook emits a structured hub.http.response event."""
        from hub_adapter.dependencies import make_log_hook

        hook = make_log_hook("Hub")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.http_version = "HTTP/1.1"
        mock_response.request.method = "GET"
        mock_response.request.url = "https://core.privateaim.dev/nodes"

        hook(mock_response)

        mock_log_event.assert_called_once_with(
            "hub.http.response",
            event_description="HTTP GET https://core.privateaim.dev/nodes HTTP/1.1 200",
            level=logging.INFO,
            status_code=200,
            service="Hub",
        )
