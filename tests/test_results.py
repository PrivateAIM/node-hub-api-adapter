"""Test the results eps."""
from starlette import status

from tests.pseudo_auth import fakeauth


class TestResults:
    """Test the results eps."""

    def test_read_from_scratch(self, test_client):
        """Test the read_from_scratch method."""
        r = test_client.get("/scratch/{object_id}", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        namespace_list = r.json()
        assert len(namespace_list)
        assert isinstance(namespace_list, list)
