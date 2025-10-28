"""Collection of unit tests for testing the dependency methods."""

import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from flame_hub import CoreClient
from flame_hub._auth_flows import RobotAuth
from pydantic import BaseModel
from starlette import status

from hub_adapter.dependencies import (
    compile_analysis_pod_data,
    get_core_client,
    get_flame_hub_auth_flow,
    get_node_id,
    get_node_metadata_for_url,
    get_node_type_cache,
    get_registry_metadata_for_url,
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
            robot = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
            self.cc = get_core_client(robot, self.ctx, self.mock_settings)

            yield  # Test runs here

    def test_get_ssl_context(self, test_settings):
        """Test the get_ssl_context method."""
        from dataclasses import replace

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

        added_certs_settings = replace(test_settings, EXTRA_CA_CERTS=str(cert_file_path))

        context = get_ssl_context(added_certs_settings)
        assert context is not None
        assert len(context._ctx.get_ca_certs()) == 2  # 2 certificates in test file

    def test_hub_auth_flow(self, test_settings):
        """Test the get_flame_hub_auth_flow method."""
        from dataclasses import replace

        working_auth = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
        assert isinstance(working_auth, RobotAuth)

        # Missing HUB_ROBOT_USER should raise ValueError
        missing_robot_user_settings = replace(test_settings, HUB_ROBOT_USER="")
        with pytest.raises(ValueError):
            get_flame_hub_auth_flow(self.ctx, missing_robot_user_settings)

        # Non UUID HUB_ROBOT_USER should raise HTTPException error
        wrong_robot_user_settings = replace(test_settings, HUB_ROBOT_USER="foo")
        with pytest.raises(HTTPException) as badUser:
            get_flame_hub_auth_flow(self.ctx, wrong_robot_user_settings)

        assert badUser.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid robot ID" in badUser.value.detail["message"]

    def test_get_core_client(self):
        """Test the get_core_client method."""
        robot = get_flame_hub_auth_flow(self.ctx, self.mock_settings)
        cc = get_core_client(robot, self.ctx, self.mock_settings)
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
                "flame_hub._core_client.CoreClient.find_nodes", side_effect=httpx.ConnectError(message="Hub is dead")
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
            cc_response.side_effect = httpx.ConnectError(message="Hub is dead")

            with pytest.raises(HubConnectError) as hubError:
                await get_node_type_cache(self.mock_settings, self.cc)

            assert hubError.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            cc_response.side_effect = None
            cc_response.return_value = TEST_MOCK_NODE

            good_cache = await get_node_type_cache(self.mock_settings, self.cc)
            assert good_cache["type"] == TEST_MOCK_NODE.type

    @patch("flame_hub._core_client.CoreClient.get_node")
    def test_get_node_metadata_for_url(self, mock_node):
        """Test the get_node_metadata_for_url method."""
        mock_node.return_value = TEST_MOCK_NODE
        correct_metadata = get_node_metadata_for_url(TEST_MOCK_NODE.id, self.cc)
        assert correct_metadata == TEST_MOCK_NODE

        # Raise error if needed info is missing
        mock_node.return_value.registry_project_id = None
        with pytest.raises(HTTPException) as err:
            get_node_metadata_for_url(TEST_MOCK_NODE.id, self.cc)

            assert err.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("flame_hub._core_client.CoreClient.get_registry_project")
    def test_get_registry_metadata_for_url(self, mock_registry_project):
        """Test the get_registry_metadata_for_url method."""

        account_name = "fakeName"
        account_secret = "fakeSecret"
        host = "fakeHost"

        class FakeRegistry(BaseModel):
            host: str

        class FakeRegistryProject(BaseModel):
            account_id: uuid.UUID | None = None
            account_name: str | None = None
            account_secret: str | None = None
            external_name: str | None = None
            registry_id: uuid.UUID | None = None
            registry: FakeRegistry | None = None

        # Registry project not found - TODO fix
        # mock_registry_project.side_effect = HubAPIError(message="No external name for node found", request=None)
        # with pytest.raises(HubAPIError) as err:
        #     get_registry_metadata_for_url(FAKE_NODE, self.cc)
        #
        #     assert err.value.error_response.status_code == status.HTTP_404_NOT_FOUND
        #
        # mock_registry_project.side_effect = None

        mock_registry_project.return_value = FakeRegistryProject(
            account_id=TEST_MOCK_NODE.id,
            account_name=account_name,
            account_secret=account_secret,
            registry=FakeRegistry(host=host),
        )

        # No external name for node found
        with pytest.raises(HTTPException) as err:
            get_registry_metadata_for_url(TEST_MOCK_NODE, self.cc)

            assert err.value.status_code == status.HTTP_400_BAD_REQUEST
            assert err.value.detail["message"] == "No external name for node found"

        mock_registry_project.return_value.external_name = account_name

        # No account_name for node found
        mock_registry_project.return_value.account_name = None
        with pytest.raises(HTTPException) as err:
            get_registry_metadata_for_url(TEST_MOCK_NODE, self.cc)

            assert err.value.status_code == status.HTTP_404_NOT_FOUND
            assert err.value.detail["message"] == "Unable to retrieve robot name or secret from the registry"

        # Missing registry_id
        mock_registry_project.return_value.account_name = account_name
        with pytest.raises(HTTPException) as err:
            get_registry_metadata_for_url(TEST_MOCK_NODE, self.cc)

            assert err.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "No registry is associated with node " in err.value.detail["message"]

        mock_registry_project.return_value.registry_id = TEST_MOCK_NODE.id

        # Working response
        assert get_registry_metadata_for_url(TEST_MOCK_NODE, self.cc) == (
            host,
            account_name,
            account_name,
            account_secret,
        )

    @patch("flame_hub._core_client.CoreClient.get_registry_project")
    def test_compile_analysis_pod_data(self, mock_registry_project):
        """Test the compile_analysis_pod_data method."""
        host = "fakeHost"
        ext_name = "fakeExternalName"
        username = "fakeUsername"
        pwd = "fakePwd"
        kong_token = "fakeKongToken"

        registry_info = (host, ext_name, username, pwd)

        compiled_info = compile_analysis_pod_data(
            TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID, registry_info, kong_token
        )

        expected_result = {
            "image_url": f"{host}/{ext_name}/{TEST_MOCK_ANALYSIS_ID}",
            "analysis_id": str(TEST_MOCK_ANALYSIS_ID),
            "project_id": str(TEST_MOCK_PROJECT_ID),
            "kong_token": kong_token,
            "registry_url": host,
            "registry_user": username,
            "registry_password": pwd,
        }

        assert compiled_info == expected_result
