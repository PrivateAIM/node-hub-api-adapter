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
        resp = {"foo": "bar"}
        httpx_mock.add_response(url=ep, json=resp, status_code=200)

        working_resp, working_code = await make_request(ep, method="get", headers={})

        assert isinstance(working_resp, dict)
        assert working_code == 200
        assert working_resp == resp

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
        httpx_mock.add_response(url=ep, json={"foo": "bar"}, status_code=200)

        file_resp, working_code = await make_request(ep, method="get", headers={}, file_response=True)

        assert working_code == 200
        assert isinstance(file_resp, FileResponse)

    # TODO write unit tests for route decorator
    # def test_route_decorator(self, httpx_mock):
    #     """Test the route decorator function."""
    #     ep_url = f"{TEST_URL}"
    #     ep_path = "/nodes"
    #     expected_status_code = status.HTTP_200_OK
    #     expected_response = {"foo": "bar"}
    #
    #     httpx_mock.add_response(url=f"{ep_url}{ep_path}", json=expected_response, status_code=expected_status_code)
    #     test_request = Request(method="get", url=f"{ep_url}{ep_path}")
    #
    #     @route(
    #         request_method="get",
    #         path=ep_path,
    #         status_code=expected_status_code,
    #         response_model=None,
    #         service_url=ep_url,
    #     )
    #     def working_resp(request=test_request):
    #         pass
    #
    #     gen_resp = working_resp()
    #     assert gen_resp == expected_response
