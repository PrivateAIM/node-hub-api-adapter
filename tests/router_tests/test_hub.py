"""Test the Hub eps."""

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
