"""Unit tests for the kong endpoints."""
from starlette import status

from tests.constants import KONG_TEST_DS, KONG_TEST_PROJECT
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
        assert KONG_TEST_DS in data_store_names

    def test_list_data_stores_by_project(self, test_client, setup_kong):
        """Test the list_data_stores_by_project method."""
        r = test_client.get(f"/datastore/{KONG_TEST_PROJECT}", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        json_data = r.json()
        data = json_data["data"]
        assert len(data) == 1  # should only be one named this

        data_store = data[0]

        assert data_store["protocols"] == ["http"]
        assert data_store["name"] == KONG_TEST_DS
        assert data_store["methods"] == ["GET", "POST", "PUT", "DELETE"]
