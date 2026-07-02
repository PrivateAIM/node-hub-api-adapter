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
from hub_adapter.routers.kong import kong_router, probe_connection, probe_data_service
from hub_adapter.schemas.kong import (
    DataStoreType,
)
from tests.conftest import check_routes
from tests.constants import (
    DS_TYPE,
    KONG_ANALYSIS_CONSUMER_DATA,
    KONG_ANALYSIS_SUCCESS_RESP,
    KONG_DS_CREATE_REQUEST,
    KONG_DS_SERVICE_DATA,
    KONG_GET_ROUTE_RESPONSE,
    KONG_LINK_ROUTE_DATA,
    TEST_JWT,
    TEST_KONG_CONSUMER_DATA,
    TEST_KONG_DS_NAME,
    TEST_KONG_ROUTE_RESPONSE,
    TEST_KONG_SERVICE_DATA,
    TEST_KONG_SERVICE_ID,
    TEST_MOCK_ANALYSIS_ID,
    TEST_MOCK_PROJECT_ID,
)
from tests.pseudo_auth import BearerAuth
from tests.router_tests.routes import EXPECTED_KONG_ROUTE_CONFIG


class TestKong:
    """Kong EP tests."""

    def test_route_configs(self, test_client):
        """Test end point configurations for the PodOrc gateway routes."""
        check_routes(kong_router, EXPECTED_KONG_ROUTE_CONFIG, test_client)

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.list_service")
    def test_get_data_stores(self, mock_svc, authorized_test_client):
        """GET /datastore lists all services, optionally filtered by type."""
        mock_svc.return_value = ListService200Response(data=[Service(**KONG_DS_SERVICE_DATA)])

        all_resp = authorized_test_client.get("/kong/datastore", auth=BearerAuth(TEST_JWT))
        assert all_resp.status_code == status.HTTP_200_OK
        assert all_resp.json()["data"][0]["name"] == TEST_KONG_DS_NAME
        mock_svc.assert_called_with(tags=None)

        authorized_test_client.get("/kong/datastore", params={"ds_type": "fhir"}, auth=BearerAuth(TEST_JWT))
        mock_svc.assert_called_with(tags="type:fhir")

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    def test_get_single_data_store(self, mock_get_svc, authorized_test_client):
        """GET /datastore/{id_or_name} wraps the single service in a list response."""
        mock_get_svc.return_value = Service(**KONG_DS_SERVICE_DATA)

        resp = authorized_test_client.get(f"/kong/datastore/{TEST_KONG_DS_NAME}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == TEST_KONG_SERVICE_ID
        mock_get_svc.assert_called_once_with(service_id_or_name=TEST_KONG_DS_NAME)

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    def test_create_data_store(self, mock_create_service, authorized_test_client):
        """POST /datastore creates a service with a type tag and no project coupling."""
        mock_create_service.return_value = Service(**KONG_DS_SERVICE_DATA)

        create_resp = authorized_test_client.post(
            "/kong/datastore", json=KONG_DS_CREATE_REQUEST, auth=BearerAuth(TEST_JWT)
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        assert create_resp.json()["name"] == TEST_KONG_DS_NAME

        request_arg = mock_create_service.call_args.args[0]
        assert request_arg.name == TEST_KONG_DS_NAME
        assert request_arg.tags == ["type:fhir"]

    def test_create_data_store_rejects_uuid_name(self, authorized_test_client):
        """POST /datastore rejects UUID-shaped display names with 422."""
        bad_request = {
            "datastore": {**KONG_DS_CREATE_REQUEST["datastore"], "name": TEST_MOCK_PROJECT_ID},
            "ds_type": DS_TYPE,
        }
        resp = authorized_test_client.post("/kong/datastore", json=bad_request, auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.delete_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.delete_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    def test_delete_data_store(
        self, mock_get_svc, mock_del_svc, mock_list_route, mock_del_route, authorized_test_client
    ):
        """DELETE /datastore is refused (409) while linked unless cascade=true."""
        mock_get_svc.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_list_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])

        # Still linked, no cascade -> 409, nothing deleted
        resp = authorized_test_client.delete(f"/kong/datastore/{TEST_KONG_DS_NAME}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_409_CONFLICT
        mock_del_svc.assert_not_called()
        mock_del_route.assert_not_called()

        # Cascade -> routes then service deleted
        resp = authorized_test_client.delete(
            f"/kong/datastore/{TEST_KONG_DS_NAME}", params={"cascade": True}, auth=BearerAuth(TEST_JWT)
        )
        assert resp.status_code == status.HTTP_200_OK
        mock_del_route.assert_called_once_with(KONG_LINK_ROUTE_DATA["id"])
        mock_del_svc.assert_called_once_with(service_id_or_name=TEST_KONG_SERVICE_ID)

        # Unlinked -> plain delete works without cascade
        mock_list_route.return_value = ListRoute200Response(data=[])
        mock_del_svc.reset_mock()
        resp = authorized_test_client.delete(f"/kong/datastore/{TEST_KONG_DS_NAME}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_200_OK
        mock_del_svc.assert_called_once_with(service_id_or_name=TEST_KONG_SERVICE_ID)

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    def test_get_projects(self, mock_route, authorized_test_client):
        """GET /project and /project/{id} filter routes by project tag."""
        mock_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])

        all_resp = authorized_test_client.get("/kong/project", auth=BearerAuth(TEST_JWT))
        assert all_resp.status_code == status.HTTP_200_OK
        assert all_resp.json()["data"][0]["paths"] == KONG_LINK_ROUTE_DATA["paths"]
        mock_route.assert_called_with(tags=None)

        one_resp = authorized_test_client.get(f"/kong/project/{TEST_MOCK_PROJECT_ID}", auth=BearerAuth(TEST_JWT))
        assert one_resp.status_code == status.HTTP_200_OK
        mock_route.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")

    @patch("hub_adapter.routers.kong.kong_admin_client.PluginsApi.create_plugin_for_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.create_route_for_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    def test_link_project_to_datastore(
        self, mock_get_svc, mock_list_route, mock_create_route, mock_plugin, authorized_test_client
    ):
        """POST /project/{pid}/datastore/{dsid} creates a nameless tagged route with plugins."""
        mock_get_svc.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_list_route.return_value = ListRoute200Response(data=[])  # not yet linked
        mock_create_route.return_value = Route(**KONG_LINK_ROUTE_DATA)
        mock_plugin.side_effect = [KeyAuth(), ACL()]

        resp = authorized_test_client.post(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{TEST_KONG_SERVICE_ID}",
            json={},
            auth=BearerAuth(TEST_JWT),
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert mock_plugin.call_count == 2

        route_request = mock_create_route.call_args.args[1]
        assert route_request.name is None
        assert route_request.paths == [f"/{TEST_MOCK_PROJECT_ID}/{TEST_KONG_SERVICE_ID}"]
        assert set(route_request.tags) == set(KONG_LINK_ROUTE_DATA["tags"])

        # Already linked -> 409
        mock_list_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])
        dup_resp = authorized_test_client.post(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{TEST_KONG_SERVICE_ID}",
            json={},
            auth=BearerAuth(TEST_JWT),
        )
        assert dup_resp.status_code == status.HTTP_409_CONFLICT

    @patch("hub_adapter.routers.kong.link_project_to_datastore")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    @patch("hub_adapter.routers.kong.delete_data_store")
    def test_create_datastore_and_project_with_link(
        self, mock_delete, mock_create_svc, mock_link, authorized_test_client
    ):
        """Test create_datastore_and_project_with_link (POST /initialize), specifically the error handling.

        NOTE: probe wiring is removed until Task 5 restores it inside link_project_to_datastore, so the only
        error path exercised here is the route-creation (link) failure, which still deletes the orphaned service.
        """
        mock_link.return_value = TEST_KONG_ROUTE_RESPONSE
        mock_create_svc.return_value = Service(**TEST_KONG_SERVICE_DATA)
        mock_delete.return_value = None  # Not needed

        body_data = {
            **KONG_DS_CREATE_REQUEST,  # Has "datastore" and "ds_type"
            "project_id": TEST_MOCK_PROJECT_ID,
        }

        initialize_resp = authorized_test_client.post("/kong/initialize", json=body_data, auth=BearerAuth(TEST_JWT))

        assert initialize_resp.status_code == status.HTTP_201_CREATED
        assert initialize_resp.json() == TEST_KONG_ROUTE_RESPONSE

        # Link fails -> orphaned service is deleted (cascade)
        mock_link.side_effect = HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
        error_resp = authorized_test_client.post("/kong/initialize", json=body_data, auth=BearerAuth(TEST_JWT))
        assert error_resp.status_code == status.HTTP_408_REQUEST_TIMEOUT
        mock_delete.assert_called_once()

    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.delete_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.delete_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    def test_delete_project(
        self, mock_list_route, mock_del_route, mock_list_consumer, mock_del_consumer, authorized_test_client
    ):
        """DELETE /project/{pid} removes all its routes and consumers."""
        mock_list_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])
        mock_list_consumer.return_value = ListConsumer200Response(
            data=[Consumer(**TEST_KONG_CONSUMER_DATA["consumer"])]
        )

        resp = authorized_test_client.delete(f"/kong/project/{TEST_MOCK_PROJECT_ID}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_200_OK
        mock_del_route.assert_called_once_with(KONG_LINK_ROUTE_DATA["id"])
        mock_del_consumer.assert_called_once()
        mock_list_route.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")
        mock_list_consumer.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.delete_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    def test_unlink_project_from_datastore(self, mock_list_route, mock_del_route, authorized_test_client):
        """DELETE /project/{pid}/datastore/{dsid} removes only the link route, keeping consumers."""
        mock_list_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])

        resp = authorized_test_client.delete(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{TEST_KONG_SERVICE_ID}", auth=BearerAuth(TEST_JWT)
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["removed_consumers"] == []
        mock_del_route.assert_called_once_with(KONG_LINK_ROUTE_DATA["id"])

        # Not linked -> 404
        mock_list_route.return_value = ListRoute200Response(data=[])
        resp = authorized_test_client.delete(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{TEST_KONG_SERVICE_ID}", auth=BearerAuth(TEST_JWT)
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    def test_get_analyses(self, mock_list_consumer, authorized_test_client):
        """GET /analysis[/{id}] resolves consumers via tags, filtering out health consumers."""
        health_consumer = {
            "id": "aaaaaaaa-1111-2222-3333-444444444444",
            "username": f"health-{TEST_MOCK_PROJECT_ID}",
            "tags": ["health", f"project:{TEST_MOCK_PROJECT_ID}"],
        }
        mock_list_consumer.return_value = ListConsumer200Response(
            data=[Consumer(**KONG_ANALYSIS_CONSUMER_DATA), Consumer(**health_consumer)]
        )

        all_resp = authorized_test_client.get("/kong/analysis", auth=BearerAuth(TEST_JWT))
        assert all_resp.status_code == status.HTTP_200_OK
        usernames = [c["username"] for c in all_resp.json()["data"]]
        assert f"analysis-{TEST_MOCK_ANALYSIS_ID}" in usernames
        assert health_consumer["username"] not in usernames  # health consumers are not analyses
        mock_list_consumer.assert_called_with(tags=None)

        authorized_test_client.get(
            "/kong/analysis", params={"project_id": TEST_MOCK_PROJECT_ID}, auth=BearerAuth(TEST_JWT)
        )
        mock_list_consumer.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")

        one_resp = authorized_test_client.get(f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=BearerAuth(TEST_JWT))
        assert one_resp.status_code == status.HTTP_200_OK
        mock_list_consumer.assert_called_with(tags=f"analysis:{TEST_MOCK_ANALYSIS_ID}")

    @patch("hub_adapter.routers.kong.logger")
    @patch("hub_adapter.routers.kong.kong_admin_client.KeyAuthsApi.create_key_auth_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ACLsApi.create_acl_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.create_consumer")
    @patch("hub_adapter.routers.kong.get_projects")
    def test_create_and_connect_analysis_to_project(
        self, mock_projects, mock_create_consumer, mock_acl, mock_keyauth, mock_logger, authorized_test_client
    ):
        """POST /analysis creates a tagged consumer with prefixed username, ACL group and keyauth."""
        mock_projects.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])
        mock_create_consumer.return_value = Consumer(**KONG_ANALYSIS_CONSUMER_DATA)
        mock_acl.return_value = ACL(group=TEST_MOCK_PROJECT_ID)
        mock_keyauth.return_value = KeyAuth()

        body_data = {"project_id": TEST_MOCK_PROJECT_ID, "analysis_id": TEST_MOCK_ANALYSIS_ID}
        resp = authorized_test_client.post("/kong/analysis", json=body_data, auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_201_CREATED

        consumer_request = mock_create_consumer.call_args.args[0]
        assert consumer_request.username == f"analysis-{TEST_MOCK_ANALYSIS_ID}"
        assert set(consumer_request.tags) == set(KONG_ANALYSIS_CONSUMER_DATA["tags"])
        assert mock_logger.info.call_count == 3

        # Project without any linked data store -> 404
        mock_projects.return_value = ListRoute200Response(data=[])
        broken_resp = authorized_test_client.post("/kong/analysis", json=body_data, auth=BearerAuth(TEST_JWT))
        assert broken_resp.status_code == status.HTTP_404_NOT_FOUND

    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.delete_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    def test_delete_analysis(self, mock_list_consumer, mock_delete, authorized_test_client):
        """DELETE /analysis/{id} resolves the consumer via tags and deletes by Kong ID."""
        mock_list_consumer.return_value = ListConsumer200Response(data=[Consumer(**KONG_ANALYSIS_CONSUMER_DATA)])

        resp = authorized_test_client.delete(f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_200_OK
        mock_delete.assert_called_once_with(consumer_username_or_id=KONG_ANALYSIS_CONSUMER_DATA["id"])

        # Unknown analysis -> 404
        mock_list_consumer.return_value = ListConsumer200Response(data=[])
        resp = authorized_test_client.delete(f"/kong/analysis/{TEST_MOCK_ANALYSIS_ID}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @patch("hub_adapter.routers.kong.kong_admin_client.KeyAuthsApi.list_key_auths_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    def test_get_analysis_keyauth_returns_existing(self, mock_list_consumer, mock_list_keyauths, test_settings):
        """get_analysis_keyauth resolves the consumer via tags then returns its first credential."""
        from hub_adapter.routers.kong import get_analysis_keyauth

        mock_list_consumer.return_value = ListConsumer200Response(data=[Consumer(**KONG_ANALYSIS_CONSUMER_DATA)])
        mock_list_keyauths.return_value = ListKeyAuthsForConsumer200Response(data=[KeyAuth(key="existingKongKey")])

        result = get_analysis_keyauth(settings=test_settings, analysis_id=TEST_MOCK_ANALYSIS_ID)

        assert result.key == "existingKongKey"
        mock_list_keyauths.assert_called_once_with(KONG_ANALYSIS_CONSUMER_DATA["id"])

    @patch("hub_adapter.routers.kong.kong_admin_client.KeyAuthsApi.list_key_auths_for_consumer")
    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    def test_get_analysis_keyauth_returns_none_when_missing(
        self, mock_list_consumer, mock_list_keyauths, test_settings
    ):
        """get_analysis_keyauth returns None when the consumer or its credential is absent."""
        from hub_adapter.routers.kong import get_analysis_keyauth

        # No consumer at all
        mock_list_consumer.return_value = ListConsumer200Response(data=[])
        assert get_analysis_keyauth(settings=test_settings, analysis_id=TEST_MOCK_ANALYSIS_ID) is None

        # Consumer exists but has no credentials
        mock_list_consumer.return_value = ListConsumer200Response(data=[Consumer(**KONG_ANALYSIS_CONSUMER_DATA)])
        mock_list_keyauths.return_value = ListKeyAuthsForConsumer200Response(data=[])
        assert get_analysis_keyauth(settings=test_settings, analysis_id=TEST_MOCK_ANALYSIS_ID) is None

    @patch("hub_adapter.routers.kong.kong_admin_client.ConsumersApi.list_consumer")
    def test_get_analysis_keyauth_returns_none_on_api_error(self, mock_list_consumer, test_settings):
        """get_analysis_keyauth swallows Kong 404s and returns None so the caller can fall back."""
        from hub_adapter.routers.kong import get_analysis_keyauth

        mock_list_consumer.side_effect = ApiException(status=status.HTTP_404_NOT_FOUND, reason="Not found")

        assert get_analysis_keyauth(settings=test_settings, analysis_id=TEST_MOCK_ANALYSIS_ID) is None


class TestConnection:
    """Tests for methods related to probing the connection via Kong."""

    @pytest.mark.asyncio
    async def test_test_connection_missing_proxy_url(self, test_settings):
        """Unit test for test_connection in which the proxy URL is not set."""

        removed_kong_url_settings = test_settings.model_copy(update={"kong_proxy_service_url": ""})

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
        mock_logger.info.assert_called_with(f"No health consumer found for {TEST_MOCK_PROJECT_ID}, creating one now")
        assert success_resp == status.HTTP_200_OK

        # Failed health retrieval
        mock_list_key_auths_for_consumer.return_value = {}
        with pytest.raises(KongConsumerApiKeyError) as err:
            await probe_connection(settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, ds_type=DataStoreType.FHIR)

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
