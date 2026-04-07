"""Test the pod orchestrator eps."""

from hub_adapter.routers.podorc import po_router
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_PO_ROUTE_CONFIG


class TestPodOrc:
    """Pod orchestration tests."""

    def test_route_configs(self, test_client, mock_event_logger):
        """Test end point configurations for the PodOrc gateway routes."""
        check_routes(po_router, EXPECTED_PO_ROUTE_CONFIG, test_client, mock_event_logger)
