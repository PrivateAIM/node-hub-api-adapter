"""Test the key functions that govern the gateway."""

import httpx
import pytest
from starlette.responses import FileResponse

from hub_adapter.core import make_request
from tests.constants import TEST_URL


class TestCore:
    """Test the core module methods."""

    @pytest.mark.asyncio
    async def test_working_make_request(self, httpx_mock):
        """Test the make_request method."""
        ep = f"{TEST_URL}/nodes"
        httpx_mock.add_response(url=ep, json={"id": "123", "type": "worker"}, status_code=200)

        working_resp, working_code = await make_request(ep, method="get", headers={})

        assert isinstance(working_resp, dict)
        assert working_code == 200
        assert working_resp == {"id": "123", "type": "worker"}

    @pytest.mark.asyncio
    async def test_broken_make_request(self, httpx_mock):
        """Test the make_request method and it raises an error."""
        ep = f"{TEST_URL}/nodes/broken"
        httpx_mock.add_exception(httpx.ConnectError(message="No bueno"), url=ep)

        with pytest.raises(httpx.ConnectError) as respError:
            await make_request(ep, method="get", headers={})

        assert respError.value.args[0] == "No bueno"

    @pytest.mark.asyncio
    async def test_working_make_request_file_response(self, httpx_mock):
        """Test the make_request method and if it can return a FileResponse object."""
        ep = f"{TEST_URL}/nodes/file"
        httpx_mock.add_response(url=ep, json={"id": "123", "type": "worker"}, status_code=200)

        file_resp, working_code = await make_request(ep, method="get", headers={}, file_response=True)

        assert working_code == 200
        assert isinstance(file_resp, FileResponse)
