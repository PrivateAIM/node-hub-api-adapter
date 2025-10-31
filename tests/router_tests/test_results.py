from hub_adapter.routers.results import results_router

EXPECTED_RESULTS_ROUTE_CONFIG = {
    "delete_local_results": {
        "path": "/local/{project_id}",
        "methods": {"DELETE"},
        "status_code": 200,
        "response_model": None,
    },
}


class TestResults:
    """Result service endpoint configuration tests."""

    def test_route_configs(self):
        """Test end point configurations for the Hub gateway routes."""
        observed = {}
        for route in results_router.routes:
            observed[route.name] = {
                "path": route.path,
                "methods": route.methods,
                "status_code": route.status_code,
                "response_model": route.response_model,
            }
        assert observed == EXPECTED_RESULTS_ROUTE_CONFIG
