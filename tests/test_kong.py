"""Unit tests for the kong endpoints."""
from http.client import HTTPException
from unittest.mock import Mock, patch

import pytest
import starlette
from starlette import status

from hub_adapter.errors import BucketError, KongError
from hub_adapter.routers.kong import FLAME, probe_data_service
from tests.constants import DS_TYPE, TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID

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

    @patch("httpx.get")
    def probe_data_service_test(self, mock_get, status: int, error_type: KongError):
        """Test registering an analysis with kong."""
        mock_response = Mock()
        mock_response.status_code = status.HTTP_403_FORBIDDEN
        mock_get.return_value = mock_response

        with pytest.raises(BucketError) as bucket_error:
            probe_data_service(url="fakeurl", apikey="fakekey", is_fhir=False, attempt=1)

        assert bucket_error.type is BucketError
        assert bucket_error.value.status_code == status.HTTP_403_FORBIDDEN
