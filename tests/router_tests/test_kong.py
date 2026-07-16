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
    KongError,
    KongGatewayError,
    KongServiceError,
    KongUpstreamError,
)
from hub_adapter.routers.kong import kong_router, probe_connection, probe_data_service
from hub_adapter.schemas.kong import LinkDataStoreProject
from tests.conftest import check_routes
from tests.constants import (
    DS_TYPE,
    KONG_ANALYSIS_CONSUMER_DATA,
    KONG_DS_CREATE_REQUEST,
    KONG_DS_SERVICE_DATA,
    KONG_LINK_ROUTE_DATA,
    TEST_JWT,
    TEST_KONG_DS_NAME,
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

    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.delete_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.PluginsApi.create_plugin_for_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    def test_create_data_store_rolls_back_on_s3_api_exception(
        self, mock_create_service, mock_create_plugin, mock_delete_service, authorized_test_client
    ):
        """A real s3-gateway failure (ApiException from the SDK) rolls back the just-created service."""
        mock_create_service.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_create_plugin.side_effect = ApiException(status=status.HTTP_400_BAD_REQUEST, reason="bad s3 config")

        body_data = {
            **KONG_DS_CREATE_REQUEST,
            "s3_config": {
                "s3_access_key": "access",
                "s3_secret_key": "secret",
                "bucket_name": "my-bucket",
            },
        }
        resp = authorized_test_client.post("/kong/datastore", json=body_data, auth=BearerAuth(TEST_JWT))

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        mock_delete_service.assert_called_once_with(service_id_or_name=KONG_DS_SERVICE_DATA["id"])

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

    @patch("hub_adapter.routers.kong.probe_connection")
    @patch("hub_adapter.routers.kong.kong_admin_client.PluginsApi.create_plugin_for_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.create_route_for_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    def test_link_project_to_datastore(
        self, mock_get_svc, mock_list_route, mock_create_route, mock_plugin, mock_probe, authorized_test_client
    ):
        """POST /project/{pid}/datastore/{dsid} creates a nameless tagged route with plugins."""
        mock_get_svc.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_list_route.return_value = ListRoute200Response(data=[])  # not yet linked
        mock_create_route.return_value = Route(**KONG_LINK_ROUTE_DATA)
        mock_plugin.side_effect = [KeyAuth(), ACL()]
        mock_probe.return_value = status.HTTP_200_OK

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

    def test_link_project_to_datastore_rejects_non_uuid_ids(self, authorized_test_client):
        """A comma-bearing (or otherwise non-UUID) project_id/datastore_id is rejected with 422.

        A comma would otherwise corrupt the Kong tags filter (Kong ANDs comma-separated tag values),
        letting the pre-existing-link check spuriously find nothing and create a duplicate link.
        """
        malicious_project_id = f"{TEST_MOCK_PROJECT_ID},health"
        resp = authorized_test_client.post(
            f"/kong/project/{malicious_project_id}/datastore/{TEST_KONG_SERVICE_ID}",
            json={},
            auth=BearerAuth(TEST_JWT),
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        malicious_datastore_id = f"{TEST_KONG_SERVICE_ID},health"
        resp = authorized_test_client.post(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{malicious_datastore_id}",
            json={},
            auth=BearerAuth(TEST_JWT),
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.delete_route")
    @patch("hub_adapter.routers.kong.probe_connection")
    @patch("hub_adapter.routers.kong.kong_admin_client.PluginsApi.create_plugin_for_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.create_route_for_service")
    @patch("hub_adapter.routers.kong.kong_admin_client.RoutesApi.list_route")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.get_service")
    def test_link_rolls_back_route_on_probe_failure(
        self,
        mock_get_svc,
        mock_list_route,
        mock_create_route,
        mock_plugin,
        mock_probe,
        mock_del_route,
        authorized_test_client,
    ):
        """A failed connection probe deletes the just-created route and propagates the error."""
        mock_get_svc.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_list_route.return_value = ListRoute200Response(data=[])
        mock_create_route.return_value = Route(**KONG_LINK_ROUTE_DATA)
        mock_plugin.side_effect = [KeyAuth(), ACL()]
        mock_probe.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        resp = authorized_test_client.post(
            f"/kong/project/{TEST_MOCK_PROJECT_ID}/datastore/{TEST_KONG_SERVICE_ID}",
            json={},
            auth=BearerAuth(TEST_JWT),
        )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        mock_del_route.assert_called_once_with(KONG_LINK_ROUTE_DATA["id"])

    @patch("hub_adapter.routers.kong.link_project_to_datastore")
    @patch("hub_adapter.routers.kong.kong_admin_client.ServicesApi.create_service")
    @patch("hub_adapter.routers.kong.delete_data_store")
    def test_create_datastore_and_project_with_link(
        self, mock_delete, mock_create_svc, mock_link, authorized_test_client
    ):
        """Test create_datastore_and_project_with_link (POST /initialize), specifically the error handling.

        link_project_to_datastore is mocked (it now probes internally), so the only error path exercised
        here is a link/probe failure, which rolls back by deleting the freshly created service (cascade).
        """
        # The mocked link_project_to_datastore return value is re-validated by FastAPI against
        # response_model=LinkDataStoreProject, so build the expectation via the same model to get
        # matching defaults for fields absent from KONG_LINK_ROUTE_DATA.
        link_response = LinkDataStoreProject(route=Route(**KONG_LINK_ROUTE_DATA), keyauth=KeyAuth(), acl=ACL())
        mock_link.return_value = link_response.model_dump(mode="json")
        mock_create_svc.return_value = Service(**KONG_DS_SERVICE_DATA)
        mock_delete.return_value = None  # Not needed

        body_data = {
            **KONG_DS_CREATE_REQUEST,  # Has "datastore" and "ds_type"
            "project_id": TEST_MOCK_PROJECT_ID,
        }

        initialize_resp = authorized_test_client.post("/kong/initialize", json=body_data, auth=BearerAuth(TEST_JWT))

        assert initialize_resp.status_code == status.HTTP_201_CREATED
        assert initialize_resp.json() == link_response.model_dump(mode="json")

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
        mock_list_consumer.return_value = ListConsumer200Response(data=[Consumer(**KONG_ANALYSIS_CONSUMER_DATA)])

        resp = authorized_test_client.delete(f"/kong/project/{TEST_MOCK_PROJECT_ID}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_200_OK
        mock_del_route.assert_called_once_with(KONG_LINK_ROUTE_DATA["id"])
        mock_del_consumer.assert_called_once()
        mock_list_route.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")
        mock_list_consumer.assert_called_with(tags=f"project:{TEST_MOCK_PROJECT_ID}")

        # Nothing found (routes and consumers both empty) -> 404, nothing deleted
        mock_list_route.return_value = ListRoute200Response(data=[])
        mock_list_consumer.return_value = ListConsumer200Response(data=[])
        mock_del_route.reset_mock()
        mock_del_consumer.reset_mock()

        resp = authorized_test_client.delete(f"/kong/project/{TEST_MOCK_PROJECT_ID}", auth=BearerAuth(TEST_JWT))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        mock_del_route.assert_not_called()
        mock_del_consumer.assert_not_called()

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

    def test_unlink_project_from_datastore_rejects_non_uuid_ids(self, authorized_test_client):
        """A comma-bearing project_id/datastore_id is rejected with 422 before hitting Kong."""
        malicious_project_id = f"{TEST_MOCK_PROJECT_ID},health"
        resp = authorized_test_client.delete(
            f"/kong/project/{malicious_project_id}/datastore/{TEST_KONG_SERVICE_ID}", auth=BearerAuth(TEST_JWT)
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

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

    @patch("hub_adapter.routers.kong.get_projects")
    def test_create_analysis_rejects_non_uuid_ids(self, mock_projects, authorized_test_client):
        """A non-UUID project_id/analysis_id is rejected with 422 before any Kong lookup.

        Both ids end up in Kong tags and the consumer's ACL group; a comma would corrupt tag filters
        and a malformed id would produce an ACL group that never matches any link route.
        """
        for body_data in (
            {"project_id": f"{TEST_MOCK_PROJECT_ID},health", "analysis_id": TEST_MOCK_ANALYSIS_ID},
            {"project_id": TEST_MOCK_PROJECT_ID, "analysis_id": f"{TEST_MOCK_ANALYSIS_ID},health"},
        ):
            resp = authorized_test_client.post("/kong/analysis", json=body_data, auth=BearerAuth(TEST_JWT))
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        mock_projects.assert_not_called()

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
    async def test_probe_connection_missing_proxy_url(self, test_settings):
        """probe_connection fails with 500 when the proxy URL is not set."""
        removed_kong_url_settings = test_settings.model_copy(update={"kong_proxy_service_url": ""})

        with pytest.raises(HTTPException) as err:
            await probe_connection(
                settings=removed_kong_url_settings,
                project_id=TEST_MOCK_PROJECT_ID,
                datastore_id=TEST_KONG_SERVICE_ID,
            )

        assert err.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_probe_connection_rejects_non_uuid_ids(self, test_settings):
        """probe_connection fails with 422 when project_id/datastore_id are not UUID-shaped."""
        with pytest.raises(HTTPException) as err:
            await probe_connection(
                settings=test_settings,
                project_id=f"{TEST_MOCK_PROJECT_ID},health",
                datastore_id=TEST_KONG_SERVICE_ID,
            )

        assert err.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.kong.probe_data_service")
    @patch("hub_adapter.routers.kong.ensure_health_consumer")
    @patch("kong_admin_client.RoutesApi.list_route")
    async def test_probe_connection(self, mock_list_route, mock_ensure_health, mock_probe, test_settings):
        """probe_connection resolves the link route via tags and probes with the health consumer key."""
        mock_list_route.return_value = ListRoute200Response(data=[Route(**KONG_LINK_ROUTE_DATA)])
        mock_ensure_health.return_value = "healthApiKey"
        mock_probe.return_value = status.HTTP_200_OK

        resp = await probe_connection(
            settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, datastore_id=TEST_KONG_SERVICE_ID
        )
        assert resp == status.HTTP_200_OK

        probe_kwargs = mock_probe.call_args.kwargs
        assert probe_kwargs["is_fhir"] is True  # KONG_LINK_ROUTE_DATA carries type:fhir
        assert probe_kwargs["url"].endswith(f"/{TEST_MOCK_PROJECT_ID}/{TEST_KONG_SERVICE_ID}/metadata")
        assert probe_kwargs["apikey"] == "healthApiKey"

        # Unlinked pair -> 404
        mock_list_route.return_value = ListRoute200Response(data=[])
        with pytest.raises(HTTPException) as err:
            await probe_connection(
                settings=test_settings, project_id=TEST_MOCK_PROJECT_ID, datastore_id=TEST_KONG_SERVICE_ID
            )
        assert err.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("kong_admin_client.KeyAuthsApi.create_key_auth_for_consumer")
    @patch("kong_admin_client.KeyAuthsApi.list_key_auths_for_consumer")
    @patch("kong_admin_client.ACLsApi.create_acl_for_consumer")
    @patch("kong_admin_client.ConsumersApi.create_consumer")
    @patch("kong_admin_client.ConsumersApi.list_consumer")
    def test_ensure_health_consumer_creates_when_missing(
        self, mock_list_consumer, mock_create, mock_acl, mock_list_keyauth, mock_create_keyauth, test_settings
    ):
        """ensure_health_consumer creates consumer + ACL + keyauth when none exists."""
        from hub_adapter.routers.kong import ensure_health_consumer

        health_id = "bbbbbbbb-1111-2222-3333-444444444444"
        mock_list_consumer.return_value = ListConsumer200Response(data=[])
        mock_create.return_value = Consumer(id=health_id, username=f"health-{TEST_MOCK_PROJECT_ID}")
        mock_acl.return_value = ACL(group=TEST_MOCK_PROJECT_ID)
        mock_list_keyauth.return_value = ListKeyAuthsForConsumer200Response(data=[])
        mock_create_keyauth.return_value = KeyAuth(key="freshKey")

        key = ensure_health_consumer(settings=test_settings, project_id=TEST_MOCK_PROJECT_ID)

        assert key == "freshKey"
        mock_list_consumer.assert_called_once_with(tags=f"health,project:{TEST_MOCK_PROJECT_ID}")
        consumer_request = mock_create.call_args.args[0]
        assert consumer_request.username == f"health-{TEST_MOCK_PROJECT_ID}"
        assert "health" in consumer_request.tags

    @patch("kong_admin_client.KeyAuthsApi.list_key_auths_for_consumer")
    @patch("kong_admin_client.ConsumersApi.list_consumer")
    def test_ensure_health_consumer_reuses_existing(self, mock_list_consumer, mock_list_keyauth, test_settings):
        """ensure_health_consumer resolves an existing consumer via tags and reuses its credential."""
        from hub_adapter.routers.kong import ensure_health_consumer

        health_id = "bbbbbbbb-1111-2222-3333-444444444444"
        mock_list_consumer.return_value = ListConsumer200Response(
            data=[Consumer(id=health_id, username=f"health-{TEST_MOCK_PROJECT_ID}")]
        )
        mock_list_keyauth.return_value = ListKeyAuthsForConsumer200Response(data=[KeyAuth(key="existingKey")])

        assert ensure_health_consumer(settings=test_settings, project_id=TEST_MOCK_PROJECT_ID) == "existingKey"
        mock_list_consumer.assert_called_once_with(tags=f"health,project:{TEST_MOCK_PROJECT_ID}")

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
        self.probe_data_service_test(status.HTTP_404_NOT_FOUND, KongUpstreamError)

        # Bad URL
        self.probe_data_service_test(status.HTTP_502_BAD_GATEWAY, KongGatewayError)
