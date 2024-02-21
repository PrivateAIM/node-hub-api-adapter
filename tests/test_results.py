"""Test the results eps."""
import uuid

from starlette import status

from tests.pseudo_auth import fakeauth


class TestResults:
    """Test the results eps."""

    def test_read_from_scratch(self, test_client):
        """Test the read_from_scratch method."""
        r = test_client.get(f"/scratch/{uuid.uuid4()}", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        upload = r.json()
        assert len(upload)
