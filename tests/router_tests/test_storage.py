from hub_adapter.routers.storage import storage_router
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_STORAGE_ROUTE_CONFIG


class TestStorage:
    """Storage service endpoint configuration tests."""

    def test_route_configs(self, test_client, mock_event_logger):
        """Test end point configurations for the Hub gateway routes."""
        check_routes(storage_router, EXPECTED_STORAGE_ROUTE_CONFIG, test_client, mock_event_logger)
