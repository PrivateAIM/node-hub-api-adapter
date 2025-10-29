"""Unit tests for the kong endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from kong_admin_client import ApiException, ListKeyAuthsForConsumer200Response, Route
from starlette import status

from hub_adapter.conf import Settings
from hub_adapter.errors import (
    BucketError,
    FhirEndpointError,
    KongConsumerApiKeyError,
    KongError,
    KongGatewayError,
    KongServiceError,
)
from hub_adapter.models.kong import DataStoreType
from hub_adapter.routers.kong import FLAME, probe_data_service, test_connection
from tests.constants import (
    DS_TYPE,
    KONG_ANALYSIS_SUCCESS_RESP,
    KONG_GET_ROUTE_RESPONSE,
    TEST_MOCK_ANALYSIS_ID,
    TEST_MOCK_PROJECT_ID,
)

test_svc_name = test_route_name = f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}"


class TestKongEndpoints:
    """Kong EP tests. Dependent on having a running instance of Kong and admin URL defined in ENV."""

    def test_list_data_stores(self, test_client, setup_kong, test_token):
        """Test the list_data_stores method."""
        r = test_client.get("/kong/datastore", auth=test_token)
        assert r.status_code == status.HTTP_200_OK

        json_data = r.json()
        data = json_data["data"]

        assert len(data)  # should not be none
        assert isinstance(data, list)
        assert len(data) > 0  # minimum 1

        data_store_names = [ds["name"] for ds in data]
        assert test_svc_name in data_store_names

    def test_list_data_stores_by_project(self, test_client, setup_kong, test_token):
        """Test the list_data_stores_by_project method."""
        r = test_client.get(f"/kong/datastore/{TEST_MOCK_PROJECT_ID}", auth=test_token)
        assert r.status_code == status.HTTP_200_OK

        json_data = r.json()
        data = json_data["data"]

        assert len(data) == 1  # should only be one named this

        data_store = data[0]

        assert data_store["protocol"] == "http"
        assert data_store["name"] == test_svc_name
        assert data_store["port"] == 80

    def test_create_delete_data_store(self, test_client, setup_kong, test_token):
        """Test the create_data_store and delete_data_store methods."""
        test_create_name = "theWWW"
        new_ds = {
            "datastore": {
                "name": test_create_name,
                "port": 443,
                "protocol": "http",
                "host": "earth",
                "path": "/cloud",
            },
            "ds_type": DS_TYPE,
        }
        r = test_client.post("/kong/datastore", auth=test_token, json=new_ds)
        assert r.status_code == status.HTTP_201_CREATED

        new_service = r.json()
        new_datastore_info = new_ds["datastore"]
        for param in ("port", "protocol", "host", "path"):  # Name will be different
            assert new_service[param] == new_datastore_info[param]

        d = test_client.delete(f"/kong/datastore/{test_create_name}-{DS_TYPE}", auth=test_token)
        assert d.status_code == status.HTTP_200_OK

    def test_connect_disconnect_project_to_datastore(self, test_client, setup_kong, test_token):
        """Test the connect_project_to_datastore and disconnect_project methods."""
        test_project_name = "Manhattan"
        test_project_route_name = f"{test_project_name}-{DS_TYPE}"
        proj_specs = {
            "data_store_id": test_svc_name,
            "project_id": test_project_name,
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "protocols": ["http"],
            "ds_type": DS_TYPE,
        }
        r = test_client.post("/kong/project", auth=test_token, json=proj_specs)
        assert r.status_code == status.HTTP_201_CREATED
        link_data = r.json()

        expected_keys = {"route", "keyauth", "acl"}
        found_keys = [key in expected_keys for key in link_data]
        assert all(found_keys)
        assert link_data["route"]["name"] == test_project_route_name

        d = test_client.delete(f"/kong/project/{test_project_route_name}", auth=test_token)
        assert d.status_code == status.HTTP_200_OK

        removed_route = d.json()["removed"]
        assert removed_route["name"] == test_project_route_name

    def test_connect_delete_analysis_to_project(self, test_client, setup_kong, test_token):
        """Test the connect_analysis_to_project method."""
        analysis_request = {
            "project_id": TEST_MOCK_PROJECT_ID,
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
        }
        r = test_client.post("/kong/analysis", auth=test_token, json=analysis_request)
        assert r.status_code == status.HTTP_201_CREATED

        link_data = r.json()

        expected_keys = {"consumer", "keyauth", "acl"}
        found_keys = [key in expected_keys for key in link_data]
        assert all(found_keys)
        assert link_data["consumer"]["username"] == f"{TEST_MOCK_ANALYSIS_ID}-{FLAME}"
        assert link_data["consumer"]["tags"] == [TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID]

        d = test_client.delete(f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=test_token)
        assert d.status_code == status.HTTP_200_OK


class TestConnection:
    """Tests for methods related to probing the connection via Kong."""

    @pytest.mark.asyncio
    async def test_test_connection_missing_proxy_url(self):
        """Unit test for test_connection in which the proxy URL is not set."""
        settings = Settings(KONG_PROXY_SERVICE_URL="")

        with pytest.raises(HTTPException) as err:
            await test_connection(
                hub_adapter_settings=settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR
            )

        assert err.value.detail["service"] == "Kong"
        assert err.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.kong.logger")
    @patch("kong_admin_client.ConsumersApi.get_consumer")
    @patch("hub_adapter.routers.kong.create_and_connect_analysis_to_project")
    @patch("kong_admin_client.RoutesApi.get_route")
    @patch("kong_admin_client.KeyAuthsApi.list_key_auths_for_consumer")
    @patch("hub_adapter.routers.kong.probe_data_service")
    async def test_test_connection(
        self,
        mock_probe_data_service,
        mock_list_key_auths_for_consumer,
        mock_get_route,
        mock_analysis_connect,
        mock_get_consumer,
        mock_logger,
        test_settings,
    ):
        """Unit test for test_connection checking if the health consumer exists."""
        # Health consumer not made yet but should be made if an ApiException occurs
        mock_get_consumer.side_effect = ApiException(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        mock_analysis_connect.return_value = {}  # Just needs to be not None
        mock_get_route.return_value = Route(**KONG_GET_ROUTE_RESPONSE["data"][0])

        # Successful health retrieval
        mock_list_key_auths_for_consumer.return_value = ListKeyAuthsForConsumer200Response(
            data=[KONG_ANALYSIS_SUCCESS_RESP["keyauth"]]
        )
        mock_probe_data_service.return_value = status.HTTP_200_OK
        success_resp = await test_connection(
            hub_adapter_settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR
        )
        mock_logger.warning.assert_called_with(f"No health consumer found for {TEST_MOCK_PROJECT_ID}, creating one now")
        assert success_resp == status.HTTP_200_OK

        # Failed health retrieval
        mock_list_key_auths_for_consumer.return_value = {}
        with pytest.raises(KongConsumerApiKeyError) as err:
            await test_connection(
                hub_adapter_settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR
            )

        assert err.value.status_code == status.HTTP_404_NOT_FOUND

    @staticmethod
    def probe_data_service_test(
        status_code: int, error_type: type[KongError] | type[HTTPException], is_fhir: bool = False
    ):
        """Template unit test for testing various expected errors raised by probe_data_service."""
        mock_response = MagicMock()
        mock_response.status_code = status_code

        with patch("httpx.get", return_value=mock_response), pytest.raises(error_type) as expected_error:
            probe_data_service(url="fakeurl", apikey="fakekey", is_fhir=is_fhir, attempt=1, max_attempts=0)

        assert expected_error.type is error_type
        assert expected_error.value.status_code == status_code

    def test_probe_data_service(self):
        """Actual unit test for probe_data_service. Checks all errors that should occur."""
        # Missing and private bucket
        self.probe_data_service_test(status.HTTP_403_FORBIDDEN, BucketError)

        # Kong service unreachable
        self.probe_data_service_test(status.HTTP_503_SERVICE_UNAVAILABLE, KongServiceError)

        # Missing FHIR endpoint, bad path
        self.probe_data_service_test(status.HTTP_404_NOT_FOUND, FhirEndpointError, is_fhir=True)

        # Unable to contact storage service
        self.probe_data_service_test(status.HTTP_404_NOT_FOUND, HTTPException)

        # Bad URL
        self.probe_data_service_test(status.HTTP_502_BAD_GATEWAY, KongGatewayError)
