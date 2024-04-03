"""Test the results eps."""
import httpx
from starlette import status


class TestResults:
    """Test the results eps."""

    def test_read_from_scratch(self, test_client, test_token):
        """Test the read_from_scratch method."""
        # r = test_client.get(f"/scratch/{uuid.uuid4()}", auth=fakeauth)
        r = test_client.get("/scratch/81818dd9-37ce-4f4f-99d6-4fb1386274f0", auth=test_token)
        assert r.status_code == status.HTTP_200_OK
        assert r.headers["Content-Length"] > 100
        assert isinstance(r.text, str)

    def test_upload_to_scratch(self, test_client, test_token):
        """Test the upload_to_scratch method."""
        test_file_content = b"Hello World!"
        r = test_client.put("/scratch", auth=test_token, files={"file": test_file_content})
        assert r.status_code == status.HTTP_200_OK

        path = r.json()["url"]

        # Read it again
        get_r = httpx.get(path, auth=test_token)
        assert get_r.status_code == status.HTTP_200_OK
        assert isinstance(get_r.text, str)
        assert get_r.text == "Hello World!"

    def test_upload_to_hub(self, test_client, test_token):
        """Test the upload_to_hub method."""
        # TODO
        pass
