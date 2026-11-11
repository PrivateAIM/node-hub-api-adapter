"""Test the key functions that govern the gateway."""

from unittest.mock import patch

import httpx2
import pytest
from starlette.responses import FileResponse

from hub_adapter.core import make_request
from tests.constants import TEST_JWT, TEST_MOCK_PROJECT_ID, TEST_URL
from tests.pseudo_auth import BearerAuth


class TestCore:
    """Test the core module methods."""

    @pytest.mark.asyncio
    async def test_working_make_request(self, httpx2_mock):
        """Test the make_request method."""
        ep = f"{TEST_URL}/nodes"
        resp = {"foo": "bar"}
        httpx2_mock.get(ep).respond(status_code=200, json=resp)

        working_resp, working_code = await make_request(ep, method="get", headers={})

        assert isinstance(working_resp, dict)
        assert working_code == 200
        assert working_resp == resp

    @pytest.mark.asyncio
    async def test_broken_make_request(self, httpx2_mock):
        """Test the make_request method and it raises an error."""
        ep = f"{TEST_URL}/nodes/broken"
        httpx2_mock.get(ep).mock(side_effect=httpx2.ConnectError("No bueno"))

        with pytest.raises(httpx2.ConnectError) as respError:
            await make_request(ep, method="get", headers={})

        assert respError.value.args[0] == "No bueno"

    @pytest.mark.asyncio
    async def test_working_make_request_file_response(self, httpx2_mock):
        """Test the make_request method and if it can return a FileResponse object."""
        ep = f"{TEST_URL}/nodes/file"
        httpx2_mock.get(ep).respond(status_code=200, json={"foo": "bar"})

        file_resp, working_code = await make_request(ep, method="get", headers={}, file_response=True)

        assert working_code == 200
        assert isinstance(file_resp, FileResponse)

    @patch("hub_adapter.core.make_request")
    @patch("hub_adapter.core.fetch_hub_token_header")
    def test_route_replaces_user_token_with_hub_token(self, mock_hub_token, mock_request, authorized_test_client):
        """Proxied requests carry the core client's Hub JWT instead of the user's IDP token."""
        mock_hub_token.return_value = {"Authorization": "Bearer hub-jwt"}
        mock_request.return_value = ({}, 200)

        resp = authorized_test_client.delete(
            "/local", params={"project_id": TEST_MOCK_PROJECT_ID}, auth=BearerAuth(TEST_JWT)
        )

        assert resp.status_code == 200
        sent_headers = mock_request.call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer hub-jwt"
        assert "authorization" not in sent_headers

    # TODO write unit tests for route decorator
    # def test_route_decorator(self, httpx2_mock):
    #     """Test the route decorator function."""
    #     ep_url = f"{TEST_URL}"
    #     ep_path = "/nodes"
    #     expected_status_code = status.HTTP_200_OK
    #     expected_response = {"foo": "bar"}
    #
    #     httpx2_mock.add_response(url=f"{ep_url}{ep_path}", json=expected_response, status_code=expected_status_code)
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
