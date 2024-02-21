"""Test the k8s eps."""
from starlette import status

from tests.pseudo_auth import fakeauth


class TestK8s:
    """K8s tests."""

    def test_get_namespaces(self, test_client):
        """Test the get_namespaces method."""
        r = test_client.get("/namespaces", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        namespace_list = r.json()
        assert len(namespace_list)
        assert isinstance(namespace_list, list)
