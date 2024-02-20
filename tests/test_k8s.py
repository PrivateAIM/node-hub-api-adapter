"""Test the k8s eps."""
from starlette import status


class TestK8s:
    """K8s tests."""

    def test_get_namespaces(self, test_client):
        """Test the get_namespaces method."""
        r = test_client.get("/namespaces")
        assert r.status_code == status.HTTP_200_OK
