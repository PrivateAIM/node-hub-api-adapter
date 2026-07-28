"""Unit tests for the health router."""

from unittest.mock import MagicMock, patch

import pytest
from httpx2 import ConnectError
from starlette import status

from hub_adapter.routers.health import get_health, get_health_downstream_services, health_router
from hub_adapter.schemas.health import DownstreamHealthCheck, HealthCheck
from tests.conftest import check_routes

MANDATORY_SERVICES = ("po", "storage", "hub_core", "hub_auth", "kong", "idp")
OPTIONAL_SERVICES = ("victoria_logs", "message_broker", "s3", "fhir")


def _mock_response(status_code: int = status.HTTP_200_OK, json: dict | None = None, text: str = "") -> MagicMock:
    """Build a stand-in for an httpx2.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json if json is not None else {}
    return resp


def _fake_kong_get(reachable: bool):
    """httpx2.get side effect where only the kong admin /status endpoint reports database reachability."""

    def fake_get(url, *args, **kwargs):
        if url.endswith("/status"):  # kong admin /status endpoint
            return _mock_response(json={"database": {"reachable": reachable}})
        return _mock_response(json={"status": "ok"})

    return fake_get


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

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_all_ok(self, mock_get, test_settings):
        """get_health_downstream_services returns an entry for every mandatory service."""
        mock_get.return_value = _mock_response(json={"status": "ok"})

        result = get_health_downstream_services(settings=test_settings)

        assert set(result.keys()) == set(MANDATORY_SERVICES)
        for svc in MANDATORY_SERVICES:
            assert result[svc] == {"status": "OK", "message": None, "status_code": status.HTTP_200_OK}

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_includes_optional_services(self, mock_get, test_settings):
        """Optional services are only probed when their URL is configured."""
        mock_get.return_value = _mock_response(json={"status": "ok"})
        settings = test_settings.model_copy(
            update={
                "victoria_logs_url": "http://localhost:9428",
                "message_broker_url": "http://localhost:8090",
                "s3_url": "http://localhost:8333",
                "fhir_url": "http://localhost:8004/",
            }
        )

        result = get_health_downstream_services(settings=settings)

        assert set(result.keys()) == set(MANDATORY_SERVICES) | set(OPTIONAL_SERVICES)

        probed_urls = {call.args[0] for call in mock_get.call_args_list}
        assert "http://localhost:9428/health" in probed_urls
        assert "http://localhost:8090/health" in probed_urls
        assert "http://localhost:8333/healthz" in probed_urls
        assert "http://localhost:8004/health" in probed_urls

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_connect_error_returns_error(self, mock_get, test_settings):
        """get_health_downstream_services reports 503 when a service is unreachable."""
        mock_get.side_effect = ConnectError("Connection refused")

        result = get_health_downstream_services(settings=test_settings)

        for svc in MANDATORY_SERVICES:
            assert svc in result
            assert result[svc]["status"] == "ERROR"
            assert result[svc]["status_code"] == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Connection refused" in result[svc]["message"]

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_non_ok_status(self, mock_get, test_settings):
        """A non-200 response is reported as ERROR along with the response body."""
        mock_get.return_value = _mock_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, text="something broke"
        )

        result = get_health_downstream_services(settings=test_settings)

        assert result["po"] == {
            "status": "ERROR",
            "message": "something broke",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_kong_reachable(self, mock_get, test_settings):
        """Kong reporting database.reachable=True keeps the kong entry OK."""
        mock_get.side_effect = _fake_kong_get(reachable=True)

        result = get_health_downstream_services(settings=test_settings)

        assert result["kong"] == {"status": "OK", "message": None, "status_code": status.HTTP_200_OK}

    @patch("hub_adapter.routers.health.httpx2.get")
    def test_get_health_downstream_services_kong_unreachable(self, mock_get, test_settings):
        """Kong reporting database.reachable=False flips the kong entry to ERROR."""
        mock_get.side_effect = _fake_kong_get(reachable=False)

        result = get_health_downstream_services(settings=test_settings)

        assert result["kong"]["status"] == "ERROR"
        assert result["kong"]["status_code"] == status.HTTP_503_SERVICE_UNAVAILABLE
        # The other services are unaffected by kong's database state
        assert result["po"]["status"] == "OK"
