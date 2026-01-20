"""Test the event retrieval endpoint."""

from hub_adapter.routers.events import event_router
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_EVENT_ROUTE_CONFIG


class TestEvents:
    """Events endpoint configuration tests."""

    def test_route_configs(self, test_client, mock_event_logger):
        """Test end point configurations for the Meta gateway routes."""
        check_routes(event_router, EXPECTED_EVENT_ROUTE_CONFIG, test_client, mock_event_logger)

    # TODO make unit tests for data retrieval from test DB
