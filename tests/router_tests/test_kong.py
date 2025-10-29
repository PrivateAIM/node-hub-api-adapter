"""Unit tests for the kong endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from kong_admin_client import ApiException, ListKeyAuthsForConsumer200Response, Route, Service
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
    TEST_JWT,
    TEST_KONG_SERVICE_RESPONSE,
    TEST_MOCK_ANALYSIS_ID,
    TEST_MOCK_PROJECT_ID,
)
from tests.pseudo_auth import BearerAuth

test_svc_name = test_route_name = f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}"

TEST_SVC_NAME = f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}-{DS_TYPE}"


class TestKong:
    """Kong EP tests."""

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.list_service")
    def test_list_data_stores(self, mock_svc, authorized_test_client):
        """Test the list_data_stores (GET /datastore) and list_specific_data_store methods
        (GET /datastore/{project_id}."""
        # TODO add testing for "detailed" parameter
        mock_svc.return_value = TEST_KONG_SERVICE_RESPONSE
        # test_client.dependency_overrides[verify_idp_token] = {"user_id": "test_user", "email": "test@example.com"}
        all_services_resp = authorized_test_client.get("/kong/datastore", auth=BearerAuth(TEST_JWT))
        assert all_services_resp.status_code == status.HTTP_200_OK

        json_data = all_services_resp.json()
        data = json_data["data"]

        assert isinstance(data, list)
        assert len(data) == 1

        assert data[0]["name"] == TEST_SVC_NAME

        single_service_resp = authorized_test_client.get(f"/kong/datastore/{TEST_SVC_NAME}", auth=BearerAuth(TEST_JWT))
        assert single_service_resp.status_code == status.HTTP_200_OK

        json_data = single_service_resp.json()
        one_store = json_data["data"]

        assert isinstance(one_store, list)
        assert len(one_store) == 1

        assert one_store[0]["name"] == TEST_SVC_NAME

    @patch("hub_adapter.routers.kong.logger")
    @patch("hub_adapter.routers.kong.delete_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.delete_service")
    def test_delete_data_store(
        self, mock_svc_delete, mock_svc_get, mock_route_delete, mock_logger, authorized_test_client
    ):
        """Test the delete_data_store method."""
        # Mock values
        mock_svc_delete.return_value = None
        mock_svc_get.return_value = Service(id=TEST_SVC_NAME)  # Needed for the subsequent `delete_service` method

        # No routes found
        mock_route_delete.side_effect = HTTPException(status.HTTP_404_NOT_FOUND)

        authorized_test_client.delete(f"/kong/datastore/{TEST_SVC_NAME}", auth=BearerAuth(TEST_JWT))
        assert mock_logger.info.call_count == 2
        mock_logger.info.assert_any_call(f"No routes for service {TEST_SVC_NAME} found")
        mock_logger.info.assert_any_call(f"Data store {TEST_SVC_NAME} deleted")

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
