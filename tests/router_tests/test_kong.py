"""Unit tests for the kong endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from kong_admin_client import (
    ACL,
    ApiException,
    Consumer,
    KeyAuth,
    ListConsumer200Response,
    ListKeyAuthsForConsumer200Response,
    ListRoute200Response,
    ListService200Response,
    Route,
    Service,
)
from starlette import status

from hub_adapter.errors import (
    BucketError,
    FhirEndpointError,
    KongConsumerApiKeyError,
    KongError,
    KongGatewayError,
    KongServiceError,
)
from hub_adapter.models.kong import DataStoreType
from hub_adapter.routers.kong import probe_connection, probe_data_service
from tests.constants import (
    DS_TYPE,
    KONG_ANALYSIS_SUCCESS_RESP,
    KONG_GET_ROUTE_RESPONSE,
    TEST_JWT,
    TEST_KONG_CONSUMER_DATA,
    TEST_KONG_CREATE_SERVICE_REQUEST,
    TEST_KONG_ROUTE_DATA,
    TEST_KONG_ROUTE_RESPONSE,
    TEST_KONG_SERVICE_DATA,
    TEST_KONG_SERVICE_ID,
    TEST_KONG_SERVICE_RESPONSE,
    TEST_MOCK_ANALYSIS_ID,
    TEST_MOCK_PROJECT_ID,
)
from tests.pseudo_auth import BearerAuth

test_svc_name = test_route_name = f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}"

TEST_SVC_NAME = f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}"


class TestKong:
    """Kong EP tests."""

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.list_service")
    def test_get_data_stores(self, mock_svc, authorized_test_client):
        """Test the service retrieval (GET /datastore/{project_id}) methods."""
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

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    def test_create_service(self, mock_create_service, authorized_test_client):
        """Test the create_service methods."""
        # Mock values
        mock_create_service.return_value = TEST_KONG_SERVICE_DATA

        create_resp = authorized_test_client.post(
            "/kong/datastore", json=TEST_KONG_CREATE_SERVICE_REQUEST, auth=BearerAuth(TEST_JWT)
        )

        assert create_resp.status_code == status.HTTP_201_CREATED
        assert create_resp.json() == TEST_KONG_SERVICE_DATA

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.list_service")
    def test_get_projects(self, mock_svc, mock_route, authorized_test_client):
        """Test the route retrieval (GET /project/{project_id}) methods."""
        mock_svc.return_value = ListService200Response(data=[Service(**TEST_KONG_SERVICE_DATA)])
        mock_route.return_value = ListRoute200Response(data=[TEST_KONG_ROUTE_DATA])

        all_routes_resp = authorized_test_client.get("/kong/project", auth=BearerAuth(TEST_JWT))
        assert all_routes_resp.status_code == status.HTTP_200_OK

        sparse_resp = all_routes_resp.json()
        assert sparse_resp == {"data": [TEST_KONG_ROUTE_DATA], "offset": None}
        assert isinstance(sparse_resp["data"][0]["service"], dict)  # Only RouteService when detailed=False

        # Include service data with detailed=True and get specific
        expected_detailed_resp = TEST_KONG_ROUTE_DATA.copy()
        expected_detailed_resp.update({"service": TEST_KONG_SERVICE_DATA})

        detailed_route_resp = authorized_test_client.get(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}", params={"detailed": True}, auth=BearerAuth(TEST_JWT)
        )
        assert detailed_route_resp.status_code == status.HTTP_200_OK
        assert detailed_route_resp.json() == {"data": [expected_detailed_resp], "offset": None}

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.create_route_for_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.PluginsApi.create_plugin_for_route")
    def test_create_route_to_datastore(self, mock_plugin, mock_route, authorized_test_client):
        """Test the create_route_to_datastore (POST /project) method."""
        mock_route.return_value = Route(**TEST_KONG_ROUTE_DATA)
        mock_plugin.side_effect = [KeyAuth(), ACL()]

        body_data = {
            "data_store_id": TEST_MOCK_PROJECT_ID,
            "project_id": TEST_MOCK_PROJECT_ID,
        }
        create_route_resp = authorized_test_client.post("/kong/project", json=body_data, auth=BearerAuth(TEST_JWT))

        assert mock_plugin.call_count == 2  # One for KeyAuth and one for ACL
        assert create_route_resp.status_code == status.HTTP_201_CREATED
        assert create_route_resp.json() == TEST_KONG_ROUTE_RESPONSE

    @patch("hub_adapter.routers.kong.create_route_to_datastore")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    @patch("hub_adapter.routers.kong.probe_connection")
    @patch("hub_adapter.routers.kong.delete_data_store")
    def test_create_datastore_and_project_with_link(
        self, mock_delete, mock_conn, mock_create_svc, mock_route, authorized_test_client
    ):
        """Test create_datastore_and_project_with_link (POST /initialize), specifically the error handling."""
        mock_route.return_value = TEST_KONG_ROUTE_RESPONSE
        mock_create_svc.return_value = Service(**TEST_KONG_SERVICE_DATA)
        mock_conn.return_value = None  # Not needed
        mock_delete.return_value = None  # Not needed

        body_data = TEST_KONG_CREATE_SERVICE_REQUEST  # Has "datastore" and "ds_type"
        body_data["project_id"] = TEST_MOCK_PROJECT_ID

        initialize_resp = authorized_test_client.post("/kong/initialize", json=body_data, auth=BearerAuth(TEST_JWT))

        assert initialize_resp.status_code == status.HTTP_201_CREATED
        assert initialize_resp.json() == TEST_KONG_ROUTE_RESPONSE

        # Connection fails
        mock_conn.side_effect = HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
        error_resp = authorized_test_client.post("/kong/initialize", json=body_data, auth=BearerAuth(TEST_JWT))
        assert error_resp.status_code == status.HTTP_408_REQUEST_TIMEOUT

    @patch("hub_adapter.routers.kong.logger")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.delete_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.get_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.delete_consumer")
    def test_delete_route(
        self,
        mock_delete_consumer,
        mock_consumer,
        mock_get_route,
        mock_delete_route,
        mock_logger,
        authorized_test_client,
    ):
        """Test delete_route (DELETE //project/{project_route_id})."""
        mock_delete_route.return_value = None  # Not needed
        mock_consumer.return_value = ListConsumer200Response(data=[Consumer(**TEST_KONG_CONSUMER_DATA)])
        mock_get_route.return_value = Route(**TEST_KONG_ROUTE_DATA)
        mock_delete_consumer.return_value = None  # Not needed

        expected_resp = {"removed": TEST_KONG_ROUTE_DATA, "status": status.HTTP_200_OK}

        delete_resp = authorized_test_client.delete(f"/kong/project/{TEST_SVC_NAME}", auth=BearerAuth(TEST_JWT))
        assert delete_resp.status_code == status.HTTP_200_OK
        assert delete_resp.json() == expected_resp
        assert mock_logger.info.call_count == 1
        mock_logger.info.assert_called_with(
            f"Project {TEST_KONG_ROUTE_DATA['id']} disconnected from data store {TEST_KONG_SERVICE_ID}"
        )

    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.get_consumer")
    def test_get_analyses(
        self,
        mock_get_consumer,
        mock_list_consumer,
        authorized_test_client,
    ):
        """Test consumer retrieval (GET /analysis/{analysis_id}) methods."""
        mock_get_consumer.return_value = Consumer(**TEST_KONG_CONSUMER_DATA["consumer"])  # Not needed
        mock_list_consumer.return_value = ListConsumer200Response(
            data=[Consumer(**TEST_KONG_CONSUMER_DATA["consumer"])]
        )

        all_consumers_resp = authorized_test_client.get("/kong/analysis", auth=BearerAuth(TEST_JWT))
        assert all_consumers_resp.status_code == status.HTTP_200_OK
        assert all_consumers_resp.json() == {"data": [TEST_KONG_CONSUMER_DATA["consumer"]], "offset": None}

        one_analysis_resp = authorized_test_client.get(
            f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=BearerAuth(TEST_JWT)
        )
        assert one_analysis_resp.status_code == status.HTTP_200_OK
        assert one_analysis_resp.json() == {"data": [TEST_KONG_CONSUMER_DATA["consumer"]], "offset": None}

    @patch("hub_adapter.routers.kong.logger")
    @patch("hub_adapter.routers.kong.kong_admin_client.KeyAuthsApi.create_key_auth_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ACLsApi.create_acl_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.create_consumer")
    @patch("hub_adapter.routers.kong.get_projects")
    def test_create_and_connect_analysis_to_project(
        self,
        mock_projects,
        mock_create_consumer,
        mock_acl,
        mock_keyauth,
        mock_logger,
        authorized_test_client,
    ):
        """Test the create_and_connect_analysis_to_project (POST /analysis) method."""
        mock_projects.return_value = ListRoute200Response(data=[TEST_KONG_ROUTE_DATA])
        mock_create_consumer.return_value = Consumer(**TEST_KONG_CONSUMER_DATA["consumer"])
        mock_acl.return_value = ACL()
        mock_keyauth.return_value = KeyAuth()

        body_data = {
            "project_id": TEST_MOCK_PROJECT_ID,
            "analysis_id": TEST_MOCK_ANALYSIS_ID,
        }

        working_consumer_resp = authorized_test_client.post("/kong/analysis", json=body_data, auth=BearerAuth(TEST_JWT))
        assert working_consumer_resp.status_code == status.HTTP_201_CREATED
        assert working_consumer_resp.json() == TEST_KONG_CONSUMER_DATA
        assert mock_logger.info.call_count == 3

        # Missing route for given project ID
        mock_projects.return_value = ListRoute200Response(data=[])
        broken_consumer_resp = authorized_test_client.post("/kong/analysis", json=body_data, auth=BearerAuth(TEST_JWT))
        assert broken_consumer_resp.status_code == status.HTTP_404_NOT_FOUND
        assert broken_consumer_resp.json() == {
            "detail": {
                "message": "Associated project not mapped to a data store",
                "service": "Kong",
                "status_code": 404,
            }
        }

    @patch("hub_adapter.routers.kong.logger")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.delete_consumer")
    def test_delete_analysis(
        self,
        mock_delete,
        mock_logger,
        authorized_test_client,
    ):
        """Test the delete_analysis (DELETE /analysis/{analysis_id}) method."""
        mock_delete.return_value = None

        delete_resp = authorized_test_client.delete(
            f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=BearerAuth(TEST_JWT)
        )
        assert delete_resp.status_code == status.HTTP_200_OK
        assert mock_logger.info.call_count == 1
        mock_logger.info.assert_called_with(f"Analysis {TEST_MOCK_ANALYSIS_ID} deleted")


class TestConnection:
    """Tests for methods related to probing the connection via Kong."""

    @pytest.mark.asyncio
    async def test_test_connection_missing_proxy_url(self, test_settings):
        """Unit test for test_connection in which the proxy URL is not set."""
        from dataclasses import replace

        removed_kong_url_settings = replace(test_settings, KONG_PROXY_SERVICE_URL="")

        with pytest.raises(HTTPException) as err:
            await probe_connection(
                settings=removed_kong_url_settings,
                project_id=TEST_MOCK_PROJECT_ID,
                ds_type=DataStoreType.FHIR,
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
        success_resp = await probe_connection(
            settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR
        )
        mock_logger.warning.assert_called_with(f"No health consumer found for {TEST_MOCK_PROJECT_ID}, creating one now")
        assert success_resp == status.HTTP_200_OK

        # Failed health retrieval
        mock_list_key_auths_for_consumer.return_value = {}
        with pytest.raises(KongConsumerApiKeyError) as err:
            await probe_connection(
                settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR
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
