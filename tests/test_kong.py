"""Unit tests for the kong endpoints."""
from starlette import status

from tests.constants import TEST_DS, TEST_PROJECT
from tests.pseudo_auth import fakeauth


class TestKong:
    """Kong EP tests. Dependent on having a running instance of Kong and admin URL defined in ENV."""

    def test_list_data_stores(self, test_client, setup_kong):
        """Test the list_data_stores method."""
        r = test_client.get("/datastore", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        json_data = r.json()
        data = json_data["data"]

        assert len(data)  # should not be none
        assert isinstance(data, list)
        assert len(data) > 0  # minimum 1

        data_store_names = [ds["name"] for ds in data]
        assert TEST_DS in data_store_names

    def test_list_data_stores_by_project(self, test_client, setup_kong):
        """Test the list_data_stores_by_project method."""
        r = test_client.get(f"/datastore/{TEST_PROJECT}", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        json_data = r.json()
        data = json_data["data"]

        assert len(data) == 1  # should only be one named this

        data_store = data[0]

        assert data_store["protocols"] == ["http"]
        assert data_store["name"] == TEST_PROJECT
        assert data_store["methods"] == ["GET", "POST", "PUT", "DELETE"]

    def test_create_delete_data_store(self, test_client, setup_kong):
        """Test the create_data_store and delete_data_store methods."""
        test_ds_name = "theWWW"
        new_ds = {
            "name": test_ds_name,
            "port": 443,
            "protocol": "http",
            "host": "earth",
            "path": "/cloud",
        }
        r = test_client.post("/datastore", auth=fakeauth, json=new_ds)
        assert r.status_code == status.HTTP_201_CREATED

        new_service = r.json()
        for k, v in new_ds.items():
            assert new_service[k] == v

        d = test_client.delete(f"/datastore/{test_ds_name}", auth=fakeauth)
        assert d.status_code == status.HTTP_200_OK

    def test_connect_disconnect_project_to_datastore(self, test_client, setup_kong):
        """Test the connect_project_to_datastore and disconnect_project methods."""
        test_project_name = "Manhattan"
        proj_specs = {
            "data_store_id": TEST_DS,
            "project_id": test_project_name,
            "methods": [
                "GET",
                "POST",
                "PUT",
                "DELETE"
            ],
            "protocols": [
                "http"
            ],
            "ds_type": "fhir"
        }
        r = test_client.post("/datastore/project", auth=fakeauth, json=proj_specs)
        assert r.status_code == status.HTTP_200_OK
        link_data = r.json()

        expected_keys = {"route", "keyauth", "acl"}
        found_keys = [key in expected_keys for key in link_data.keys()]
        assert all(found_keys)
        assert link_data["route"]["name"] == test_project_name

        d = test_client.put(f"/disconnect/{test_project_name}", auth=fakeauth)
        assert d.status_code == status.HTTP_200_OK

        removed_routes = d.json()["removed_routes"]
        assert len(removed_routes) == 1

    def test_connect_delete_analysis_to_project(self, test_client, setup_kong):
        """Test the connect_analysis_to_project method."""
        test_analysis = "datalore"
        analysis_request = {
            "project_id": TEST_PROJECT,
            "analysis_id": test_analysis,
        }
        r = test_client.post("/project/analysis", auth=fakeauth, json=analysis_request)
        assert r.status_code == status.HTTP_202_ACCEPTED

        link_data = r.json()

        expected_keys = {"consumer", "keyauth", "acl"}
        found_keys = [key in expected_keys for key in link_data.keys()]
        assert all(found_keys)
        assert link_data["consumer"]["username"] == test_analysis
        assert link_data["consumer"]["tags"] == [TEST_PROJECT]

        d = test_client.delete(f"/analysis/{test_analysis}", auth=fakeauth)
        assert d.status_code == status.HTTP_200_OK
