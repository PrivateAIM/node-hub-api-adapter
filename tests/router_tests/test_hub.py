"""Test the Hub eps."""

from hub_adapter.routers.hub import _format_query_params, hub_router
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_HUB_ROUTE_CONFIG


class TestHub:
    """Hub endpoint configuration tests."""

    def test_route_configs(self, test_client, mock_event_logger):
        """Test end point configurations for the Meta gateway routes."""
        check_routes(hub_router, EXPECTED_HUB_ROUTE_CONFIG, test_client, mock_event_logger)

    def test_format_query_params(self):
        """Test endpoint formatting query params."""
        test_params = {"page": '{"limit": 2, "offset": 3}', "sort": "-id", "fields": "id,ninja"}
        expected_formatted_params = {
            "page": {"limit": 2, "offset": 3},
            "fields": ["id", "ninja"],
            "sort": {"by": "id", "order": "descending"},
        }
        assert _format_query_params(test_params) == expected_formatted_params

        # Missing page
        test_2 = {"sort": "+ninja", "fields": "foo,ninja"}
        expected_formatted_params_2 = {
            "fields": ["foo", "ninja"],
            "sort": {"by": "ninja", "order": "ascending"},
        }
        assert _format_query_params(test_2) == expected_formatted_params_2
