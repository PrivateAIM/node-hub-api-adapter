"""Test the results eps."""
import random
import re

import httpx
from starlette import status


class TestResults:
    """Test the results eps."""

    def test_scratch(self, test_client, test_token):
        """Test the upload_to_scratch and read_from_scratch methods."""
        # Upload blob
        blob = random.randbytes(24)
        r = test_client.put("/scratch", auth=test_token, files={"file": blob})

        assert r.status_code == status.HTTP_200_OK

        upload_path = r.json()["url"]
        uuid = upload_path.split("/")[-1]
        uuid_regex = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert re.match(uuid_regex, uuid) is not None

        # Read it again
        get_r = httpx.get(upload_path, auth=test_token)
        assert get_r.status_code == status.HTTP_200_OK
        assert get_r.read() == blob

    def test_upload_to_hub(self, test_client, test_token):
        """Test the upload_to_hub method."""
        # TODO
        pass
