"""Test the Hub eps."""

import pytest
from fastapi import HTTPException

from hub_adapter.routers.hub import _parse_query_params, hub_router
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_HUB_ROUTE_CONFIG


class TestHub:
    """Hub endpoint configuration tests."""

    def test_route_configs(self, test_client):
        """Test end point configurations for the Meta gateway routes."""
        check_routes(hub_router, EXPECTED_HUB_ROUTE_CONFIG, test_client)

    def test_parse_query_params(self):
        """Test endpoint formatting query params."""
        result = _parse_query_params(page='{"limit": 2, "offset": 3}', sort="-id", fields="id,ninja")
        assert result == {
            "page": {"limit": 2, "offset": 3},
            "fields": ["id", "ninja"],
            "sort": {"by": "id", "order": "descending"},
        }

        # Missing page
        result_2 = _parse_query_params(sort="+ninja", fields="foo,ninja")
        assert result_2 == {
            "fields": ["foo", "ninja"],
            "sort": {"by": "ninja", "order": "ascending"},
        }

    def test_parse_query_params_invalid_json_raises_422(self):
        """Malformed JSON in the page param must raise 422, not a raw JSONDecodeError."""
        with pytest.raises(HTTPException) as exc_info:
            _parse_query_params(page="not-valid-json")
        assert exc_info.value.status_code == 422

    def test_parse_query_params_non_object_json_raises_422(self):
        """A valid JSON value that is not an object (array, string, number) must raise 422."""
        for non_object in ('[1, 2, 3]', '"a string"', '42', 'true'):
            with pytest.raises(HTTPException) as exc_info:
                _parse_query_params(page=non_object)
            assert exc_info.value.status_code == 422, f"Expected 422 for page={non_object!r}"
