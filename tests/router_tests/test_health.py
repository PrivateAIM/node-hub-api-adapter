"""Unit tests for the health router."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ConnectError
from starlette import status

from hub_adapter.routers.health import get_health, get_health_downstream_services, health_router
from hub_adapter.schemas.health import DownstreamHealthCheck, HealthCheck
from tests.conftest import check_routes

EXPECTED_HEALTH_ROUTE_CONFIG = (
    {
        "path": "/healthz",
        "name": "health.status.get",
        "methods": {"GET"},
        "status_code": status.HTTP_200_OK,
        "response_model": HealthCheck,
    },
    {
        "path": "/health/services",
        "name": "health.status.services.get",
        "methods": {"GET"},
        "status_code": status.HTTP_200_OK,
        "response_model": DownstreamHealthCheck,
    },
)


class TestHealth:
    """Health endpoint configuration and behaviour tests."""

    def test_route_configs(self, test_client):
        """Test endpoint configurations for the health router."""
        check_routes(health_router, EXPECTED_HEALTH_ROUTE_CONFIG, test_client)

    @pytest.mark.asyncio
    async def test_get_health_returns_ok(self):
        """get_health returns HealthCheck with status OK."""
        result = await get_health()
        assert isinstance(result, HealthCheck)
        assert result.status == "OK"

    @patch("hub_adapter.routers.health.httpx.get")
    def test_get_health_downstream_services_all_ok(self, mock_get, test_settings):
        """get_health_downstream_services returns a dict with all three service keys."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_resp

        result = get_health_downstream_services(settings=test_settings)

        assert set(result.keys()) == {"po", "storage", "kong"}

    @patch("hub_adapter.routers.health.httpx.get")
    def test_get_health_downstream_services_connect_error_returns_string(self, mock_get, test_settings):
        """get_health_downstream_services stores the error string when a service is unreachable."""
        mock_get.side_effect = ConnectError("Connection refused")

        result = get_health_downstream_services(settings=test_settings)

        assert isinstance(result["po"], str)
        assert isinstance(result["storage"], str)
        assert isinstance(result["kong"], str)

    @patch("hub_adapter.routers.health.httpx.get")
    def test_get_health_downstream_services_kong_reachable(self, mock_get, test_settings):
        """Kong database.reachable=True results in {'status': 'ok'} for the kong entry."""

        def fake_get(url):
            m = MagicMock()
            if "status" in url:  # kong admin /status endpoint
                m.json.return_value = {"database": {"reachable": True}}
            else:
                m.json.return_value = {"status": "ok"}
            return m

        mock_get.side_effect = fake_get

        result = get_health_downstream_services(settings=test_settings)

        assert result["kong"] == {"status": "ok"}

    @patch("hub_adapter.routers.health.httpx.get")
    def test_get_health_downstream_services_kong_unreachable(self, mock_get, test_settings):
        """Kong database.reachable=False results in {'status': 'fail'} for the kong entry."""

        def fake_get(url):
            m = MagicMock()
            if "status" in url:
                m.json.return_value = {"database": {"reachable": False}}
            else:
                m.json.return_value = {"status": "ok"}
            return m

        mock_get.side_effect = fake_get

        result = get_health_downstream_services(settings=test_settings)

        assert result["kong"] == {"status": "fail"}
