"""Test the pod orchestrator eps."""

from hub_adapter.models.podorc import CleanupPodResponse, LogResponse, PodResponse, StatusResponse
from hub_adapter.routers.podorc import po_router

EXPECTED_PO_ROUTE_CONFIG = {
    "/po": {"methods": {"POST"}, "response_model": StatusResponse, "status_code": 200},
    "/po/cleanup/{cleanup_type}": {"methods": {"DELETE"}, "response_model": CleanupPodResponse, "status_code": 200},
    "/po/delete": {"methods": {"DELETE"}, "response_model": StatusResponse, "status_code": 200},
    "/po/delete/{analysis_id}": {"methods": {"DELETE"}, "response_model": StatusResponse, "status_code": 200},
    "/po/history": {"methods": {"GET"}, "response_model": LogResponse, "status_code": 200},
    "/po/history/{analysis_id}": {"methods": {"GET"}, "response_model": LogResponse, "status_code": 200},
    "/po/logs": {"methods": {"GET"}, "response_model": LogResponse, "status_code": 200},
    "/po/logs/{analysis_id}": {"methods": {"GET"}, "response_model": LogResponse, "status_code": 200},
    "/po/pods": {"methods": {"GET"}, "response_model": PodResponse, "status_code": 200},
    "/po/pods/{analysis_id}": {"methods": {"GET"}, "response_model": PodResponse, "status_code": 200},
    "/po/status": {"methods": {"GET"}, "response_model": StatusResponse, "status_code": 200},
    "/po/status/{analysis_id}": {"methods": {"GET"}, "response_model": StatusResponse, "status_code": 200},
    "/po/stop": {"methods": {"PUT"}, "response_model": StatusResponse, "status_code": 200},
    "/po/stop/{analysis_id}": {"methods": {"PUT"}, "response_model": StatusResponse, "status_code": 200},
}


class TestPodOrc:
    """Pod orchestration tests."""

    def test_route_configs(self):
        """Test end point configurations for the PodOrc gateway routes."""
        observed = {}
        for route in po_router.routes:
            observed[route.path] = {
                "methods": route.methods,
                "status_code": route.status_code,
                "response_model": route.response_model,
            }
        assert observed == EXPECTED_PO_ROUTE_CONFIG
