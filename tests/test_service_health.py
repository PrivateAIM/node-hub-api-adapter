"""Collection of unit tests for the downstream service health monitoring."""

import tempfile
import threading
import uuid
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import peewee as pw
import pytest
from playhouse.pool import PooledSqliteDatabase

from hub_adapter.conf import Settings, UserSettings
from hub_adapter.dependencies import get_settings
from hub_adapter.schemas.health import (
    ServiceCheckStatus,
    ServiceHealthBucket,
    ServiceHealthSummary,
    ServiceMonitoringStatus,
)
from hub_adapter.service_health import (
    MESSAGE_MAX_LENGTH,
    PRUNE_INTERVAL,
    ServiceHealthCheck,
    ServiceHealthMonitor,
    _bucket_expression,
    _earliest_failure_message,
    _rows_to_buckets,
    bucket_range,
    build_probe_targets,
    probe_all,
    probe_service,
    record_sweep,
)


def _mock_response(status_code: int = 200, text: str = "", json_body: dict | None = None):
    resp = MagicMock(spec=httpx2.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _mock_client(response=None, side_effect=None):
    client = MagicMock(spec=httpx2.AsyncClient)
    client.get = AsyncMock(return_value=response, side_effect=side_effect)
    return client


class TestProbeTargets:
    """The mapping of services to their health endpoints."""

    def test_required_services_get_their_health_suffix(self, test_settings: Settings):
        targets = build_probe_targets(test_settings)

        assert targets["po"].endswith("/po/healthz")
        assert targets["storage"].endswith("/healthz")
        assert targets["kong"].endswith("/status")
        assert targets["idp"].endswith("/.well-known/openid-configuration")
        assert targets["hub_core"] == test_settings.hub_service_url

    def test_unconfigured_optional_services_are_none(self, test_settings: Settings):
        targets = build_probe_targets(test_settings)

        assert targets["victoria_logs"] is None
        assert targets["message_broker"] is None
        assert targets["s3"] is None
        assert targets["fhir"] is None

    def test_configured_optional_service_is_probed(self, test_settings: Settings):
        settings = test_settings.model_copy(update={"fhir_url": "http://fhir.local/"})

        assert build_probe_targets(settings)["fhir"] == "http://fhir.local/health"

    @pytest.mark.asyncio
    async def test_probe_all_skips_unconfigured_services(self, test_settings: Settings):
        client = _mock_client(_mock_response())

        with patch("hub_adapter.service_health.get_proxy_client", return_value=client):
            results = await probe_all(test_settings)

        assert "fhir" not in results
        assert "s3" not in results
        assert set(results) == {"po", "storage", "hub_core", "hub_auth", "kong", "idp"}

    @pytest.mark.asyncio
    async def test_unexpected_probe_error_does_not_lose_the_sweep(self, test_settings: Settings):
        def _get(url, *args, **kwargs):
            if url.endswith("/status"):  # the kong target
                raise RuntimeError("boom")
            return _mock_response()

        client = MagicMock(spec=httpx2.AsyncClient)
        client.get = AsyncMock(side_effect=_get)

        with patch("hub_adapter.service_health.get_proxy_client", return_value=client):
            results = await probe_all(test_settings)

        assert set(results) == {"po", "storage", "hub_core", "hub_auth", "kong", "idp"}
        assert results["kong"]["status"] == "ERROR"
        assert results["kong"]["status_code"] == 503
        assert "RuntimeError" in results["kong"]["message"]
        assert results["kong"]["latency_ms"] is None
        assert results["storage"]["status"] == "OK"


class TestProbeService:
    """Probing a single service."""

    @pytest.mark.asyncio
    async def test_healthy_service(self):
        result = await probe_service(_mock_client(_mock_response()), "storage", "http://storage/healthz")

        assert result["status"] == "OK"
        assert result["status_code"] == 200
        assert result["message"] is None
        assert result["url"] == "http://storage/healthz"
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_non_200_is_an_error_with_the_response_body(self):
        result = await probe_service(_mock_client(_mock_response(500, "boom")), "storage", "http://storage/healthz")

        assert result["status"] == "ERROR"
        assert result["status_code"] == 500
        assert result["message"] == "boom"

    @pytest.mark.asyncio
    async def test_unreachable_service_reports_503_and_still_times_the_attempt(self):
        client = _mock_client(side_effect=httpx2.ConnectError("nope"))
        result = await probe_service(client, "storage", "http://storage/healthz")

        assert result["status"] == "ERROR"
        assert result["status_code"] == 503
        assert "ConnectError" in result["message"]
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_timeout_is_caught(self):
        client = _mock_client(side_effect=httpx2.TimeoutException("too slow"))
        result = await probe_service(client, "po", "http://po/po/healthz")

        assert result["status"] == "ERROR"
        assert result["status_code"] == 503

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            httpx2.UnsupportedProtocol("missing scheme"),
            httpx2.TooManyRedirects("redirect loop"),
            httpx2.ReadError("connection reset"),
            httpx2.InvalidURL("not a url"),  # not an HTTPError subclass
        ],
    )
    async def test_other_request_failures_are_caught(self, error):
        client = _mock_client(side_effect=error)
        result = await probe_service(client, "storage", "http://storage/healthz")

        assert result["status"] == "ERROR"
        assert result["status_code"] == 503
        assert type(error).__name__ in result["message"]

    @pytest.mark.asyncio
    async def test_kong_with_unreachable_database_is_an_error(self):
        response = _mock_response(json_body={"database": {"reachable": False}})
        result = await probe_service(_mock_client(response), "kong", "http://kong/status")

        assert result["status"] == "ERROR"
        assert result["status_code"] == 503
        assert result["message"] == "Kong cannot reach its database"

    @pytest.mark.asyncio
    async def test_kong_with_reachable_database_is_healthy(self):
        response = _mock_response(json_body={"database": {"reachable": True}})
        result = await probe_service(_mock_client(response), "kong", "http://kong/status")

        assert result["status"] == "OK"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_kong_with_unparseable_body_stays_healthy(self):
        response = _mock_response()
        response.json.side_effect = ValueError("not json")
        result = await probe_service(_mock_client(response), "kong", "http://kong/status")

        assert result["status"] == "OK"

    @pytest.mark.asyncio
    async def test_long_error_message_is_truncated(self):
        response = _mock_response(500, "x" * (MESSAGE_MAX_LENGTH + 100))
        result = await probe_service(_mock_client(response), "storage", "http://storage/healthz")

        assert len(result["message"]) == MESSAGE_MAX_LENGTH


class TestMonitorLifecycle:
    """Starting, stopping and degrading the monitoring loop."""

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.load_persistent_settings", return_value=UserSettings())
    @patch("hub_adapter.service_health.get_node_database", return_value=None)
    async def test_unconfigured_database_leaves_monitoring_disabled(self, _mock_db, _mock_settings, test_settings):
        unconfigured = test_settings.model_copy(
            update={"postgres_db": None, "postgres_user": None, "postgres_password": None}
        )
        monitor = ServiceHealthMonitor()

        with patch("hub_adapter.service_health.get_settings", return_value=unconfigured):
            await monitor.start()

        assert monitor.enabled is False
        assert monitor._task is None
        assert "not configured" in monitor.disabled_reason

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.load_persistent_settings", return_value=UserSettings())
    @patch("hub_adapter.service_health.get_node_database", return_value=None)
    async def test_unreachable_database_is_reported_differently(self, _mock_db, _mock_settings, test_settings):
        """A fully configured but unreachable database gets its own reason."""
        configured = test_settings.model_copy(
            update={"postgres_db": "node", "postgres_user": "node", "postgres_password": "secret"}
        )
        monitor = ServiceHealthMonitor()

        with patch("hub_adapter.service_health.get_settings", return_value=configured):
            await monitor.start()

        assert monitor.enabled is False
        assert "Unable to connect to Postgres" in monitor.disabled_reason

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.load_persistent_settings", return_value=UserSettings())
    @patch("hub_adapter.service_health.get_node_database", return_value=None)
    async def test_connection_is_only_attempted_once(self, mock_db, _mock_settings):
        monitor = ServiceHealthMonitor()
        await monitor.start()
        await monitor.start()

        assert mock_db.call_count == 1
        assert monitor.enabled is False

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.load_persistent_settings", return_value=UserSettings())
    @patch("hub_adapter.service_health.bind_service_health")
    @patch("hub_adapter.service_health.get_node_database")
    async def test_available_database_starts_the_loop(self, mock_db, _mock_bind, _mock_settings):
        mock_db.return_value = MagicMock(spec=pw.PostgresqlDatabase)
        monitor = ServiceHealthMonitor()

        with patch.object(ServiceHealthMonitor, "sweep", new_callable=AsyncMock):
            await monitor.start()

            assert monitor.enabled is True
            assert monitor._task is not None
            assert monitor.interval == UserSettings().service_health.interval

            await monitor.stop()

        assert monitor._task is None

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.load_persistent_settings", return_value=UserSettings())
    @patch("hub_adapter.service_health.bind_service_health", side_effect=pw.OperationalError("dead"))
    @patch("hub_adapter.service_health.get_node_database")
    async def test_table_creation_failure_disables_monitoring(self, mock_db, _mock_bind, _mock_settings):
        mock_db.return_value = MagicMock(spec=pw.PostgresqlDatabase)
        monitor = ServiceHealthMonitor()
        await monitor.start()

        assert monitor.enabled is False
        assert "Unable to prepare the service health table" in monitor.disabled_reason


class TestMonitorSweep:
    """One probe cycle."""

    def _monitor(self) -> ServiceHealthMonitor:
        monitor = ServiceHealthMonitor()
        monitor._db = MagicMock(spec=pw.PostgresqlDatabase)
        return monitor

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.get_settings")
    @patch("hub_adapter.service_health.prune_old_checks", return_value=0)
    @patch("hub_adapter.service_health.record_sweep")
    @patch("hub_adapter.service_health.probe_all", new_callable=AsyncMock)
    async def test_results_are_persisted(self, mock_probe, mock_record, _mock_prune, _mock_settings):
        mock_probe.return_value = {
            "kong": {"status": "OK", "status_code": 200, "message": None, "latency_ms": 1.0, "url": "u"}
        }
        monitor = self._monitor()
        await monitor.sweep()

        mock_record.assert_called_once_with(monitor._db, mock_probe.return_value)

    @pytest.mark.asyncio
    @patch("hub_adapter.service_health.get_settings")
    @patch("hub_adapter.service_health.record_sweep", side_effect=pw.OperationalError("gone"))
    @patch("hub_adapter.service_health.probe_all", new_callable=AsyncMock)
    async def test_database_error_does_not_break_the_sweep(self, mock_probe, _mock_record, _mock_settings):
        mock_probe.return_value = {
            "kong": {"status": "OK", "status_code": 200, "message": None, "latency_ms": 1.0, "url": "u"}
        }

        results = await self._monitor().sweep()  # must not raise

        assert results == mock_probe.return_value

    @patch("hub_adapter.service_health.log_event")
    def test_status_change_is_logged_once_per_transition(self, mock_log):
        monitor = self._monitor()
        healthy = {"kong": {"status": "OK", "status_code": 200, "message": None}}
        broken = {"kong": {"status": "ERROR", "status_code": 503, "message": "down"}}

        monitor._log_status_changes(healthy)  # first observation is not a transition
        monitor._log_status_changes(healthy)
        assert mock_log.call_count == 0

        monitor._log_status_changes(broken)
        monitor._log_status_changes(broken)
        assert mock_log.call_count == 1
        assert "went from OK to ERROR" in mock_log.call_args.kwargs["event_description"]

        monitor._log_status_changes(healthy)
        assert mock_log.call_count == 2

    @patch("hub_adapter.service_health.prune_old_checks", return_value=3)
    def test_pruning_is_throttled(self, mock_prune):
        monitor = self._monitor()

        monitor._prune_if_due()
        monitor._prune_if_due()
        assert mock_prune.call_count == 1

        monitor._last_prune = datetime.now(UTC) - PRUNE_INTERVAL - timedelta(seconds=1)
        monitor._prune_if_due()
        assert mock_prune.call_count == 2


class TestHistoryEndpoint:
    """The endpoint serving the recorded health history."""

    ROUTE = "/health/services/history"

    @pytest.fixture(autouse=True)
    def _pinned_settings(self, test_client, test_settings):
        """Keep a developer's local .env from switching the optional services on."""
        test_client.app.dependency_overrides[get_settings] = lambda: test_settings
        yield
        test_client.app.dependency_overrides.pop(get_settings, None)

    def _monitor(self, enabled: bool, reason: str | None = None) -> MagicMock:
        monitor = MagicMock(spec=ServiceHealthMonitor)
        monitor.enabled = enabled
        monitor.disabled_reason = reason
        monitor.interval = 60
        monitor.retention_days = 30
        monitor.database = MagicMock(spec=pw.PostgresqlDatabase)
        return monitor

    def test_reports_that_monitoring_is_disabled(self, test_client):
        monitor = self._monitor(False, "Postgres is not configured, service health is not being recorded")

        with patch("hub_adapter.managers.service_health_monitor", monitor):
            resp = test_client.get(self.ROUTE)

        assert resp.status_code == 200
        body = resp.json()
        assert body["monitoring_enabled"] is False
        assert "Postgres is not configured" in body["monitoring_detail"]
        assert body["interval_seconds"] is None
        assert body["services"]["kong"]["status"] == "ACTIVE"
        assert body["services"]["kong"]["total_checks"] == 0

    def test_unconfigured_optional_services_are_reported_as_disabled(self, test_client):
        with patch("hub_adapter.managers.service_health_monitor", self._monitor(False, "no db")):
            resp = test_client.get(self.ROUTE)

        fhir = resp.json()["services"]["fhir"]
        assert fhir["configured"] is False
        assert fhir["status"] == "DISABLED"
        assert "No URL configured" in fhir["detail"]

    def test_summary_and_datapoints(self, test_client):
        monitor = self._monitor(True)
        checked_at = datetime.now(UTC)
        summaries = {
            "kong": {
                "total_checks": 10,
                "successful_checks": 9,
                "failed_checks": 1,
                "uptime_percentage": 90.0,
                "min_latency_ms": 1.5,
                "avg_latency_ms": 12.25,
                "max_latency_ms": 100.0,
            }
        }
        last = {
            "kong": {
                "status": "ERROR",
                "status_code": 503,
                "checked_at": checked_at,
                "message": "Kong cannot reach its database",
            }
        }
        checks = {
            "kong": [
                {
                    "checked_at": checked_at,
                    "status": "ERROR",
                    "status_code": 503,
                    "latency_ms": 8.0,
                    "message": "Kong cannot reach its database",
                    "sweep_id": uuid.uuid4(),
                }
            ]
        }

        with (
            patch("hub_adapter.managers.service_health_monitor", monitor),
            patch("hub_adapter.routers.health.summarize_range", return_value=summaries),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value=last),
            patch("hub_adapter.routers.health.fetch_checks", return_value=checks) as mock_fetch,
        ):
            resp = test_client.get(self.ROUTE, params={"service": "kong", "limit": 5})

        assert resp.status_code == 200
        body = resp.json()
        assert body["monitoring_enabled"] is True
        assert body["interval_seconds"] == 60
        assert set(body["services"]) == {"kong"}

        kong = body["services"]["kong"]
        assert kong["uptime_percentage"] == 90.0
        assert kong["failed_checks"] == 1
        assert kong["avg_latency_ms"] == 12.25
        assert kong["last_status"] == "ERROR"
        assert kong["last_error"] == "Kong cannot reach its database"
        assert kong["checks_returned"] == 1
        assert kong["checks"][0]["latency_ms"] == 8.0
        assert mock_fetch.call_args.args[-1] == 5  # limit is passed through

    def test_last_status_is_coerced_to_the_enum(self, test_client):
        """The database hands back a plain string, which must not reach the serializer untyped."""
        last = {
            "kong": {
                "status": "OK",
                "status_code": 200,
                "checked_at": datetime.now(UTC),
                "message": None,
            }
        }

        with (
            patch("hub_adapter.managers.service_health_monitor", self._monitor(True)),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value=last),
            patch("hub_adapter.routers.health.fetch_checks", return_value={}),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("error", UserWarning)
            resp = test_client.get(self.ROUTE, params={"service": "kong"})

        assert resp.status_code == 200
        assert resp.json()["services"]["kong"]["last_status"] == "OK"

    def test_service_without_recorded_checks_stays_empty(self, test_client):
        with (
            patch("hub_adapter.managers.service_health_monitor", self._monitor(True)),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value={}),
            patch("hub_adapter.routers.health.fetch_checks", return_value={}),
        ):
            resp = test_client.get(self.ROUTE, params={"service": "kong"})

        kong = resp.json()["services"]["kong"]
        assert kong["total_checks"] == 0
        assert kong["uptime_percentage"] is None
        assert kong["last_status"] is None
        assert kong["checks"] == []

    def test_checks_can_be_excluded(self, test_client):
        with (
            patch("hub_adapter.managers.service_health_monitor", self._monitor(True)),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value={}),
            patch("hub_adapter.routers.health.fetch_checks") as mock_fetch,
        ):
            resp = test_client.get(self.ROUTE, params={"include_checks": False})

        assert resp.status_code == 200
        mock_fetch.assert_not_called()

    def test_default_timeframe_is_the_last_day(self, test_client):
        with patch("hub_adapter.managers.service_health_monitor", self._monitor(False, "no db")):
            body = test_client.get(self.ROUTE).json()

        start = datetime.fromisoformat(body["start"])
        end = datetime.fromisoformat(body["end"])
        assert timedelta(hours=23, minutes=59) < end - start <= timedelta(days=1)

    def test_unknown_service_is_rejected(self, test_client):
        with patch("hub_adapter.managers.service_health_monitor", self._monitor(True)):
            resp = test_client.get(self.ROUTE, params={"service": "not_a_service"})

        assert resp.status_code == 422
        assert "not_a_service" in resp.json()["detail"]["message"]

    def test_inverted_timeframe_is_rejected(self, test_client):
        with patch("hub_adapter.managers.service_health_monitor", self._monitor(True)):
            resp = test_client.get(
                self.ROUTE,
                params={"start_date": "2026-07-30T00:00:00Z", "end_date": "2026-07-29T00:00:00Z"},
            )

        assert resp.status_code == 422

    def test_database_error_reports_service_unavailable(self, test_client):
        with (
            patch("hub_adapter.managers.service_health_monitor", self._monitor(True)),
            patch("hub_adapter.routers.health.summarize_range", side_effect=pw.OperationalError("gone")),
        ):
            resp = test_client.get(self.ROUTE)

        assert resp.status_code == 503

    def test_resolution_populates_buckets(self, test_client):
        monitor = self._monitor(True)
        buckets = {
            "kong": [
                {
                    "start": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
                    "end": datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
                    "total": 5, "successful": 4, "failed": 1,
                    "max_latency_ms": 1204.0, "avg_latency_ms": 310.5,
                    "worst_status": ServiceCheckStatus.ERROR,
                    "message": "Connection refused",
                }
            ]
        }

        with (
            patch("hub_adapter.managers.service_health_monitor", monitor),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value={}),
            patch("hub_adapter.routers.health.bucket_range", return_value=buckets),
        ):
            resp = test_client.get(self.ROUTE, params={"resolution": 300})

        assert resp.status_code == 200
        kong = resp.json()["services"]["kong"]
        assert len(kong["buckets"]) == 1
        assert kong["buckets"][0]["failed"] == 1
        assert kong["buckets"][0]["message"] == "Connection refused"

    def test_buckets_are_empty_without_a_resolution(self, test_client):
        monitor = self._monitor(True)

        with (
            patch("hub_adapter.managers.service_health_monitor", monitor),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value={}),
            patch("hub_adapter.routers.health.fetch_checks", return_value={}),
            patch("hub_adapter.routers.health.bucket_range") as mock_bucket,
        ):
            resp = test_client.get(self.ROUTE)

        assert resp.status_code == 200
        mock_bucket.assert_not_called()
        assert resp.json()["services"]["kong"]["buckets"] == []

    def test_resolution_must_be_positive(self, test_client):
        monitor = self._monitor(True)

        with patch("hub_adapter.managers.service_health_monitor", monitor):
            resp = test_client.get(self.ROUTE, params={"resolution": 0})

        assert resp.status_code == 422

    def test_resolution_skips_raw_checks(self, test_client):
        """Asking for buckets should not also drag back every raw datapoint."""
        monitor = self._monitor(True)

        with (
            patch("hub_adapter.managers.service_health_monitor", monitor),
            patch("hub_adapter.routers.health.summarize_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_last_checks", return_value={}),
            patch("hub_adapter.routers.health.bucket_range", return_value={}),
            patch("hub_adapter.routers.health.fetch_checks") as mock_fetch,
        ):
            resp = test_client.get(self.ROUTE, params={"resolution": 300})

        assert resp.status_code == 200
        mock_fetch.assert_not_called()


class TestServiceHealthBucket:
    """The per-slice aggregate returned when a resolution is requested."""

    def test_summary_has_no_buckets_by_default(self):
        summary = ServiceHealthSummary(configured=True, status=ServiceMonitoringStatus.ACTIVE)
        assert summary.buckets == []

    def test_bucket_round_trips(self):
        bucket = ServiceHealthBucket(
            start=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
            end=datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
            total=5,
            successful=4,
            failed=1,
            max_latency_ms=1204.0,
            avg_latency_ms=310.5,
            worst_status=ServiceCheckStatus.ERROR,
            message="Connection refused",
        )
        assert bucket.worst_status == ServiceCheckStatus.ERROR
        assert bucket.failed == 1

    def test_rows_fold_into_per_service_buckets(self):
        rows = [
            {
                "service": "kong",
                "bucket": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
                "total": 5, "successful": 5,
                "max_latency_ms": 40.0, "avg_latency_ms": 30.0,
                "message": None,
            },
            {
                "service": "kong",
                "bucket": datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
                "total": 5, "successful": 3,
                "max_latency_ms": 1204.0, "avg_latency_ms": 500.0,
                "message": "Connection refused",
            },
        ]

        folded = _rows_to_buckets(rows, 300)

        assert list(folded) == ["kong"]
        first, second = folded["kong"]

        assert first["failed"] == 0
        assert first["worst_status"] == ServiceCheckStatus.OK
        assert first["message"] is None
        assert first["end"] == datetime(2026, 7, 30, 12, 5, tzinfo=UTC)

        assert second["failed"] == 2
        assert second["worst_status"] == ServiceCheckStatus.ERROR
        assert second["message"] == "Connection refused"

    def test_rows_are_sorted_by_slice_start(self):
        rows = [
            {"service": "s3", "bucket": datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
             "total": 1, "successful": 1, "max_latency_ms": 1.0, "avg_latency_ms": 1.0, "message": None},
            {"service": "s3", "bucket": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
             "total": 1, "successful": 1, "max_latency_ms": 1.0, "avg_latency_ms": 1.0, "message": None},
        ]

        folded = _rows_to_buckets(rows, 300)

        starts = [bucket["start"] for bucket in folded["s3"]]
        assert starts == sorted(starts)

    def test_message_is_dropped_when_nothing_failed(self):
        rows = [
            {"service": "kong", "bucket": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
             "total": 3, "successful": 3, "max_latency_ms": 40.0, "avg_latency_ms": 30.0,
             "message": "stale text"},
        ]

        folded = _rows_to_buckets(rows, 300)

        assert folded["kong"][0]["failed"] == 0
        assert folded["kong"][0]["message"] is None

    def test_null_latency_aggregates_survive(self):
        rows = [
            {"service": "fhir", "bucket": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
             "total": 2, "successful": 0, "max_latency_ms": None, "avg_latency_ms": None,
             "message": "timed out"},
        ]

        folded = _rows_to_buckets(rows, 300)

        assert folded["fhir"][0]["max_latency_ms"] is None
        assert folded["fhir"][0]["worst_status"] == ServiceCheckStatus.ERROR


class TestBucketRange:
    """The GROUP BY service, slice aggregation."""

    def test_bucket_expression_floors_to_the_slice_width(self):
        db = pw.PostgresqlDatabase("unused")

        with db.bind_ctx((ServiceHealthCheck,)):
            query = ServiceHealthCheck.select(
                ServiceHealthCheck.service, _bucket_expression(300)
            )
            sql, params = query.sql()

        assert "to_timestamp" in sql
        assert "FLOOR" in sql
        assert "EXTRACT(epoch FROM checked_at)" in sql
        # the slice width must be bound as a parameter, never interpolated
        assert "300" not in sql
        assert params == [300, 300]

    def test_bucket_expression_is_parameterised_for_any_width(self):
        db = pw.PostgresqlDatabase("unused")

        with db.bind_ctx((ServiceHealthCheck,)):
            sql, params = ServiceHealthCheck.select(_bucket_expression(3600)).sql()

        assert params == [3600, 3600]
        assert "3600" not in sql

    def test_message_aggregate_picks_the_earliest_failure(self):
        """With several distinct failure messages in one slice, the slice must report the one that came first.

        MIN() would hand back the alphabetically smallest message instead, so the aggregate has to order the
        failures by checked_at and take the head.
        """
        db = pw.PostgresqlDatabase("unused")

        with db.bind_ctx((ServiceHealthCheck,)):
            sql, params = ServiceHealthCheck.select(_earliest_failure_message()).sql()

        assert 'array_agg("t1"."message" ORDER BY "t1"."checked_at")' in sql
        assert ')[1] AS "message"' in sql
        # only failed checks contribute, so a slice without any yields NULL
        assert 'FILTER (WHERE ("t1"."status" != %s))' in sql
        assert params == [ServiceCheckStatus.OK]
        assert "MIN" not in sql

    def test_bucket_range_selects_the_earliest_failure_message(self):
        db = MagicMock(spec=pw.PostgresqlDatabase)
        start = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
        end = datetime(2026, 7, 30, 13, 0, tzinfo=UTC)

        with (
            patch("hub_adapter.service_health.bind_service_health"),
            patch("hub_adapter.service_health._range_filter"),
            patch("hub_adapter.service_health._earliest_failure_message") as mock_message,
            patch("hub_adapter.service_health.ServiceHealthCheck") as mock_model,
        ):
            mock_model.select.return_value.where.return_value.group_by.return_value.dicts.return_value = []
            bucket_range(db, start, end, ["kong"], 300)

        mock_message.assert_called_once_with()
        assert mock_message.return_value in mock_model.select.call_args.args

    def test_bucket_range_folds_the_query_rows(self):
        rows = [
            {"service": "kong", "bucket": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
             "total": 5, "successful": 4, "max_latency_ms": 900.0,
             "avg_latency_ms": 200.0, "message": "boom"},
        ]
        db = MagicMock(spec=pw.PostgresqlDatabase)

        start = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
        end = datetime(2026, 7, 30, 13, 0, tzinfo=UTC)

        with (
            patch("hub_adapter.service_health.bind_service_health"),
            patch("hub_adapter.service_health.ServiceHealthCheck") as mock_model,
            # _range_filter compares ServiceHealthCheck.checked_at to real datetimes; a bare
            # MagicMock has no usable __ge__/__le__ for that, so it's stubbed out here since
            # this test is about the row-folding, not the WHERE clause (covered elsewhere).
            patch("hub_adapter.service_health._range_filter") as mock_range_filter,
        ):
            mock_model.select.return_value.where.return_value.group_by.return_value.dicts.return_value = rows
            result = bucket_range(db, start, end, ["kong"], 300)

        mock_range_filter.assert_called_once_with(start, end, ["kong"])
        assert result["kong"][0]["failed"] == 1
        assert result["kong"][0]["worst_status"] == ServiceCheckStatus.ERROR
        assert result["kong"][0]["message"] == "boom"

    def test_bucket_range_with_no_rows_returns_empty(self):
        db = MagicMock(spec=pw.PostgresqlDatabase)
        start = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
        end = datetime(2026, 7, 30, 13, 0, tzinfo=UTC)

        with (
            patch("hub_adapter.service_health.bind_service_health"),
            patch("hub_adapter.service_health.ServiceHealthCheck") as mock_model,
            patch("hub_adapter.service_health._range_filter") as mock_range_filter,
        ):
            mock_model.select.return_value.where.return_value.group_by.return_value.dicts.return_value = []
            result = bucket_range(db, start, end, ["kong"], 300)

        mock_range_filter.assert_called_once_with(start, end, ["kong"])
        assert result == {}


def _probe_result() -> dict[str, dict]:
    """One healthy probe result in the shape record_sweep expects."""
    return {
        "kong": {
            "url": "http://kong/health",
            "status": ServiceCheckStatus.OK,
            "status_code": 200,
            "latency_ms": 4.2,
            "message": None,
        }
    }


class TestConnectionPooling:
    """The pooled connection has to go back to the pool once the work is done."""

    @staticmethod
    @pytest.fixture
    def pooled_db():
        """A tiny pooled database standing in for the node Postgres."""
        db = PooledSqliteDatabase(str(Path(tempfile.mkdtemp()) / "health.db"), max_connections=2, stale_timeout=300)
        yield db
        db.close_all()

    def test_connection_is_returned_to_the_pool(self, pooled_db):
        """A completed write leaves no connection checked out."""
        record_sweep(pooled_db, _probe_result())

        assert len(pooled_db._in_use) == 0

    def test_pool_survives_more_sweeps_than_connections(self, pooled_db):
        """Worker threads come and go, so the pool must not leak one connection per thread."""
        errors = []
        results = _probe_result()

        def sweep():
            try:
                record_sweep(pooled_db, results)

            except Exception as err:  # noqa: BLE001 - the failure is the assertion
                errors.append(err)

        for _ in range(pooled_db._max_connections + 3):
            worker = threading.Thread(target=sweep)
            worker.start()
            worker.join()

        assert not errors, f"pool exhausted after {len(errors)} sweeps: {errors[0]}"
