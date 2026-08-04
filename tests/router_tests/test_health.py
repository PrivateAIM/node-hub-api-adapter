"""Unit tests for the health router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx2 import ConnectError
from starlette import status

from hub_adapter.routers.health import get_health, get_health_downstream_services, health_router
from hub_adapter.schemas.health import DownstreamHealthCheck, HealthCheck, ServiceHealthHistory
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


def _patch_probe_client(return_value=None, side_effect=None):
    """Patch the async client used for probing, returning the patcher and the client mock."""
    client = MagicMock()
    client.get = AsyncMock(return_value=return_value, side_effect=side_effect)

    patcher = patch("hub_adapter.service_health.get_proxy_client", return_value=client)
    patcher.start()

    return patcher, client


def _fake_kong_get(reachable: bool):
    """Client side effect where only the kong admin /status endpoint reports database reachability."""

    async def fake_get(url, *args, **kwargs):
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
    {
        "path": "/health/services/history",
        "name": "health.status.services.history.get",
        "methods": {"GET"},
        "status_code": status.HTTP_200_OK,
        "response_model": ServiceHealthHistory,
    },
)


class TestOpenApiStatusEnums:
    """The status values must reach openapi.json as named schemas.

    The frontend imports them from the types generated off openapi.json, so they cannot be inline
    Literals: those produce anonymous unions with nothing to import.
    """

    EXPECTED_ENUMS = {
        "HealthStatus": ["OK", "WARNING", "ERROR", "CRITICAL"],
        "ServiceCheckStatus": ["OK", "ERROR"],
        "ServiceMonitoringStatus": ["ACTIVE", "DISABLED"],
    }

    EXPECTED_REFS = {
        ("HealthCheck", "status"): "HealthStatus",
        ("ServiceHealthPoint", "status"): "ServiceCheckStatus",
        ("ServiceHealthSummary", "status"): "ServiceMonitoringStatus",
    }

    def test_status_enums_are_named_schemas(self, test_client):
        schemas = test_client.app.openapi()["components"]["schemas"]

        for name, values in self.EXPECTED_ENUMS.items():
            assert name in schemas, f"{name} is missing from components.schemas"
            assert schemas[name]["enum"] == values

    def test_status_fields_reference_the_named_schemas(self, test_client):
        schemas = test_client.app.openapi()["components"]["schemas"]

        for (model, field), enum_name in self.EXPECTED_REFS.items():
            ref = schemas[model]["properties"][field].get("$ref")
            assert ref == f"#/components/schemas/{enum_name}", f"{model}.{field} is not a $ref to {enum_name}"

    def test_nullable_status_field_still_references_the_enum(self, test_client):
        schemas = test_client.app.openapi()["components"]["schemas"]
        last_status = schemas["ServiceHealthSummary"]["properties"]["last_status"]

        refs = {option.get("$ref") for option in last_status["anyOf"]}
        assert "#/components/schemas/ServiceCheckStatus" in refs


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

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_all_ok(self, test_settings):
        """get_health_downstream_services returns an entry for every mandatory service."""
        patcher, _ = _patch_probe_client(_mock_response(json={"status": "ok"}))

        try:
            result = await get_health_downstream_services(settings=test_settings)

        finally:
            patcher.stop()

        assert set(result.keys()) == set(MANDATORY_SERVICES)
        for svc in MANDATORY_SERVICES:
            assert result[svc]["status"] == "OK"
            assert result[svc]["status_code"] == status.HTTP_200_OK
            assert result[svc]["message"] is None
            assert result[svc]["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_includes_optional_services(self, test_settings):
        """Optional services are only probed when their URL is configured."""
        patcher, client = _patch_probe_client(_mock_response(json={"status": "ok"}))
        settings = test_settings.model_copy(
            update={
                "victoria_logs_url": "http://localhost:9428",
                "message_broker_url": "http://localhost:8090",
                "s3_url": "http://localhost:8333",
                "fhir_url": "http://localhost:8004/",
            }
        )

        try:
            result = await get_health_downstream_services(settings=settings)

        finally:
            patcher.stop()

        assert set(result.keys()) == set(MANDATORY_SERVICES) | set(OPTIONAL_SERVICES)

        probed_urls = {call.args[0] for call in client.get.call_args_list}
        assert "http://localhost:9428/health" in probed_urls
        assert "http://localhost:8090/health" in probed_urls
        assert "http://localhost:8333/healthz" in probed_urls
        assert "http://localhost:8004/health" in probed_urls

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_connect_error_returns_error(self, test_settings):
        """get_health_downstream_services reports 503 when a service is unreachable."""
        patcher, _ = _patch_probe_client(side_effect=ConnectError("Connection refused"))

        try:
            result = await get_health_downstream_services(settings=test_settings)

        finally:
            patcher.stop()

        for svc in MANDATORY_SERVICES:
            assert svc in result
            assert result[svc]["status"] == "ERROR"
            assert result[svc]["status_code"] == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Connection refused" in result[svc]["message"]

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_non_ok_status(self, test_settings):
        """A non-200 response is reported as ERROR along with the response body."""
        response = _mock_response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, text="something broke")
        patcher, _ = _patch_probe_client(response)

        try:
            result = await get_health_downstream_services(settings=test_settings)

        finally:
            patcher.stop()

        assert result["po"]["status"] == "ERROR"
        assert result["po"]["message"] == "something broke"
        assert result["po"]["status_code"] == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_kong_reachable(self, test_settings):
        """Kong reporting database.reachable=True keeps the kong entry OK."""
        patcher, _ = _patch_probe_client(side_effect=_fake_kong_get(reachable=True))

        try:
            result = await get_health_downstream_services(settings=test_settings)

        finally:
            patcher.stop()

        assert result["kong"]["status"] == "OK"
        assert result["kong"]["status_code"] == status.HTTP_200_OK
        assert result["kong"]["message"] is None

    @pytest.mark.asyncio
    async def test_get_health_downstream_services_kong_unreachable(self, test_settings):
        """Kong reporting database.reachable=False flips the kong entry to ERROR."""
        patcher, _ = _patch_probe_client(side_effect=_fake_kong_get(reachable=False))

        try:
            result = await get_health_downstream_services(settings=test_settings)

        finally:
            patcher.stop()

        assert result["kong"]["status"] == "ERROR"
        assert result["kong"]["status_code"] == status.HTTP_503_SERVICE_UNAVAILABLE
        # The other services are unaffected by kong's database state
        assert result["po"]["status"] == "OK"
