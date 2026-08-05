"""Background routine that probes the downstream microservices and stores the results in Postgres."""

import asyncio
import logging
import uuid
from collections.abc import Iterable
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from time import perf_counter

import httpx2
import peewee as pw
from playhouse.postgres_ext import DateTimeTZField

from hub_adapter.conf import ServiceHealthSettings, Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.database import get_node_database
from hub_adapter.dependencies import get_proxy_client, get_settings
from hub_adapter.middleware import log_event
from hub_adapter.schemas.health import ServiceCheckStatus
from hub_adapter.user_settings import load_persistent_settings

logger = logging.getLogger(__name__)

PROBE_TIMEOUT = 10.0  # seconds
MESSAGE_MAX_LENGTH = 500  # keep an upstream HTML error page from bloating the table
PRUNE_INTERVAL = timedelta(hours=1)

DEFAULT_INTERVAL = 60
DEFAULT_RETENTION_DAYS = 30

# Services that are only probed when the node has a URL for them
OPTIONAL_SERVICES = ("victoria_logs", "message_broker", "s3", "fhir")


def _health_url(base: str | None, suffix: str = "") -> str | None:
    """Build a health endpoint URL, or None if the service has no URL configured."""
    if not base:
        return None

    return base.rstrip("/") + suffix


def build_probe_targets(settings: Settings) -> dict[str, str | None]:
    """Map every known downstream service to its health endpoint.

    Returns
    -------
    dict[str, str | None]
        Service name to health endpoint URL. A None means no URL is configured for that service, i.e. it's
        disabled on this node and will not be probed.
    """
    return {
        "po": _health_url(settings.podorc_service_url, "/po/healthz"),
        "storage": _health_url(settings.storage_service_url, "/healthz"),
        "hub_core": settings.hub_service_url or None,
        "hub_auth": settings.hub_auth_service_url or None,
        "kong": _health_url(settings.kong_admin_service_url, "/status"),
        "idp": _health_url(settings.idp_url, "/.well-known/openid-configuration"),
        "victoria_logs": _health_url(settings.victoria_logs_url, "/health"),
        "message_broker": _health_url(settings.message_broker_url, "/health"),
        "s3": _health_url(settings.s3_url, "/healthz"),
        "fhir": _health_url(settings.fhir_url, "/health"),
    }


async def probe_service(client: httpx2.AsyncClient, service: str, url: str) -> dict:
    """Probe a single service and time how long it took to answer.

    Returns
    -------
    dict
        Keys: status, status_code, message, latency_ms, url
    """
    status_code, svc_status, message, resp = None, None, None, None
    start = perf_counter()

    try:
        resp = await client.get(url, timeout=PROBE_TIMEOUT)
        status_code = resp.status_code
        if resp.status_code == httpx2.codes.OK:
            svc_status = ServiceCheckStatus.OK

        else:
            svc_status = ServiceCheckStatus.ERROR
            message = resp.text

    # InvalidURL is not an HTTPError subclass, so a misconfigured URL has to be named separately
    except (httpx2.HTTPError, httpx2.InvalidURL) as e:
        logger.error(f"Error connecting to {service} service: {e!r}")
        status_code = 503
        svc_status = ServiceCheckStatus.ERROR
        message = repr(e)

    latency_ms = round((perf_counter() - start) * 1000, 2)

    if service == "kong" and resp is not None and svc_status == ServiceCheckStatus.OK:
        # Kong answers 200 even when it cannot reach its own database
        kong_body = {}
        with suppress(ValueError):
            kong_body = resp.json()

        if not kong_body.get("database", {}).get("reachable", True):
            svc_status = ServiceCheckStatus.ERROR
            message = "Kong cannot reach its database"
            status_code = 503

    if message is not None:
        message = message[:MESSAGE_MAX_LENGTH]

    return {
        "status": svc_status,
        "status_code": status_code,
        "message": message,
        "latency_ms": latency_ms,
        "url": url,
    }


async def probe_all(settings: Settings) -> dict[str, dict]:
    """Probe every configured downstream service concurrently. Missing services are skipped."""
    targets = {service: url for service, url in build_probe_targets(settings).items() if url}

    client = get_proxy_client()
    # An unexpected failure in one probe must not throw away the results of the whole sweep
    results = await asyncio.gather(
        *(probe_service(client, svc, url) for svc, url in targets.items()),
        return_exceptions=True,
    )

    probed: dict[str, dict] = {}
    for (service, url), result in zip(targets.items(), results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, asyncio.CancelledError):
                raise result  # the app is shutting down, not a service outage

            logger.error(f"Unexpected error probing {service} service: {result!r}")
            result = {
                "status": ServiceCheckStatus.ERROR,
                "status_code": 503,
                "message": repr(result)[:MESSAGE_MAX_LENGTH],
                "latency_ms": None,
                "url": url,
            }

        probed[service] = result

    return probed


class ServiceHealthCheck(pw.Model):
    """Database table schema for a single downstream service probe.

    Attributes
    ----------
    sweep_id : uuid.UUID
        Groups every service probed in the same cycle, so a node-wide outage can be told apart
        from a single service being down.
    service : str
        Name of the downstream service, e.g. "kong".
    url : str
        Health endpoint that was actually probed, which makes configuration drift visible after the fact.
    checked_at : datetime
        UTC timestamp of the sweep the probe belongs to.
    status : str
        Either "OK" or "ERROR".
    status_code : int | None
        HTTP status returned by the service, or 503 when it could not be reached at all.
    latency_ms : float | None
        Round trip time in milliseconds.
    message : str | None
        Error text, truncated to MESSAGE_MAX_LENGTH characters.
    """

    id = pw.BigAutoField()
    sweep_id = pw.UUIDField()
    service = pw.CharField(max_length=64)
    url = pw.TextField()
    checked_at = DateTimeTZField(index=True)
    status = pw.CharField(max_length=16)
    status_code = pw.IntegerField(null=True)
    latency_ms = pw.DoubleField(null=True)
    message = pw.TextField(null=True)

    class Meta:
        table_name = "service_health_check"
        indexes = ((("service", "checked_at"), False),)


@contextmanager
def bind_service_health(db: pw.Database):
    """Bind the health check model to a database, creating the table if it does not exist yet."""
    with db.bind_ctx((ServiceHealthCheck,)):
        db.create_tables((ServiceHealthCheck,))
        yield


def record_sweep(db: pw.Database, results: dict[str, dict], checked_at: datetime | None = None) -> uuid.UUID:
    """Persist the results of one probe cycle. Every row shares a sweep ID and timestamp."""
    checked_at = checked_at or datetime.now(UTC)
    sweep_id = uuid.uuid4()

    rows = [
        {
            "sweep_id": sweep_id,
            "service": service,
            "url": result["url"],
            "checked_at": checked_at,
            "status": result["status"],
            "status_code": result["status_code"],
            "latency_ms": result["latency_ms"],
            "message": result["message"],
        }
        for service, result in results.items()
    ]

    with bind_service_health(db):
        ServiceHealthCheck.insert_many(rows).execute()

    return sweep_id


def prune_old_checks(db: pw.Database, retention_days: int) -> int:
    """Delete checks older than the retention window, returning the number of rows removed."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    with bind_service_health(db):
        return ServiceHealthCheck.delete().where(ServiceHealthCheck.checked_at < cutoff).execute()


def _range_filter(start: datetime, end: datetime, services: Iterable[str] | None):
    """Build the shared WHERE clause for the history queries."""
    clause = (ServiceHealthCheck.checked_at >= start) & (ServiceHealthCheck.checked_at <= end)
    if services:
        clause &= ServiceHealthCheck.service.in_(list(services))

    return clause


def _bucket_expression(bucket_seconds: int):
    """Generate bucket from SQL epoch"""
    epoch = pw.fn.EXTRACT(pw.SQL("epoch FROM checked_at"))

    return pw.fn.to_timestamp(pw.fn.FLOOR(epoch / bucket_seconds) * bucket_seconds).alias("bucket")


def _earliest_failure_message():
    """Message of the earliest failed check in a group, or NULL when nothing failed.

    MIN() returns the smallest message alphabetically instead of the one that actually came first.
    """
    failures = (
        pw.fn.array_agg(ServiceHealthCheck.message)
        .order_by(ServiceHealthCheck.checked_at)
        .filter(ServiceHealthCheck.status != ServiceCheckStatus.OK)
    )

    # Need to use parantheses otherwise Postgres complains about subscripts
    return pw.NodeList((pw.SQL("("), failures, pw.SQL(")[1]")), glue="").alias("message")


def _as_float(value, ndigits: int | None = None) -> float | None:
    """Force to a result from a query to float to avoid downstream issues."""
    if value is None:
        return None

    return round(float(value), ndigits) if ndigits is not None else float(value)


def _rows_to_buckets(rows: list[dict], bucket_seconds: int) -> dict[str, list[dict]]:
    """Slice aggregates by service into buckets."""
    width = timedelta(seconds=bucket_seconds)
    buckets: dict[str, list[dict]] = {}

    for row in rows:
        total = int(row["total"] or 0)
        successful = int(row["successful"] or 0)
        failed = total - successful
        start = row["bucket"]

        buckets.setdefault(row["service"], []).append(
            {
                "start": start,
                "end": start + width,
                "total": total,
                "successful": successful,
                "failed": failed,
                "max_latency_ms": _as_float(row["max_latency_ms"]),
                "avg_latency_ms": _as_float(row["avg_latency_ms"], ndigits=2),
                "worst_status": ServiceCheckStatus.ERROR if failed else ServiceCheckStatus.OK,
                "message": row["message"] if failed else None,
            }
        )

    for service_buckets in buckets.values():
        service_buckets.sort(key=lambda bucket: bucket["start"])

    return buckets


def summarize_range(
    db: pw.Database, start: datetime, end: datetime, services: Iterable[str] | None = None
) -> dict[str, dict]:
    """Summarize results by time range."""
    successes = pw.Case(None, [(ServiceHealthCheck.status == ServiceCheckStatus.OK, 1)], 0)

    # The query has to be built inside the bind context, otherwise it is not bound to a database
    with bind_service_health(db):
        query = (
            ServiceHealthCheck.select(
                ServiceHealthCheck.service,
                pw.fn.COUNT(ServiceHealthCheck.id).alias("total_checks"),
                pw.fn.SUM(successes).alias("successful_checks"),
                pw.fn.MIN(ServiceHealthCheck.latency_ms).alias("min_latency_ms"),
                pw.fn.AVG(ServiceHealthCheck.latency_ms).alias("avg_latency_ms"),
                pw.fn.MAX(ServiceHealthCheck.latency_ms).alias("max_latency_ms"),
            )
            .where(_range_filter(start, end, services))
            .group_by(ServiceHealthCheck.service)
        )
        rows = list(query.dicts())

    summaries = {}
    for row in rows:
        total = int(row["total_checks"] or 0)
        successful = int(row["successful_checks"] or 0)
        summaries[row["service"]] = {
            "total_checks": total,
            "successful_checks": successful,
            "failed_checks": total - successful,
            "uptime_percentage": round(successful / total * 100, 2) if total else None,
            "min_latency_ms": _as_float(row["min_latency_ms"]),
            "avg_latency_ms": _as_float(row["avg_latency_ms"], ndigits=2),
            "max_latency_ms": _as_float(row["max_latency_ms"]),
        }

    return summaries


def bucket_range(
    db: pw.Database,
    start: datetime,
    end: datetime,
    services: Iterable[str] | None,
    bucket_seconds: int,
) -> dict[str, list[dict]]:
    """Aggregate the stored checks per service into time slices."""
    successes = pw.Case(None, [(ServiceHealthCheck.status == ServiceCheckStatus.OK, 1)], 0)
    bucket = _bucket_expression(bucket_seconds)

    with bind_service_health(db):
        query = (
            ServiceHealthCheck.select(
                ServiceHealthCheck.service,
                bucket,
                pw.fn.COUNT(ServiceHealthCheck.id).alias("total"),
                pw.fn.SUM(successes).alias("successful"),
                pw.fn.MAX(ServiceHealthCheck.latency_ms).alias("max_latency_ms"),
                pw.fn.AVG(ServiceHealthCheck.latency_ms).alias("avg_latency_ms"),
                _earliest_failure_message(),
            )
            .where(_range_filter(start, end, services))
            .group_by(ServiceHealthCheck.service, pw.SQL("bucket"))
        )
        rows = list(query.dicts())

    return _rows_to_buckets(rows, bucket_seconds)


def fetch_last_checks(
    db: pw.Database, start: datetime, end: datetime, services: Iterable[str] | None = None
) -> dict[str, dict]:
    """Return the most recent check per service within the timeframe."""
    with bind_service_health(db):
        query = (
            ServiceHealthCheck.select()
            .where(_range_filter(start, end, services))
            .distinct([ServiceHealthCheck.service])
            .order_by(ServiceHealthCheck.service, ServiceHealthCheck.checked_at.desc())
        )
        return {row["service"]: row for row in query.dicts()}


def fetch_checks(
    db: pw.Database,
    start: datetime,
    end: datetime,
    services: Iterable[str],
    limit: int,
) -> dict[str, list[dict]]:
    """Return the raw datapoints per service, newest first and capped at limit per service."""
    checks: dict[str, list[dict]] = {}

    with bind_service_health(db):
        for service in services:
            query = (
                ServiceHealthCheck.select()
                .where(_range_filter(start, end, (service,)))
                .order_by(ServiceHealthCheck.checked_at.desc())
                .limit(limit)
            )
            checks[service] = list(query.dicts())

    return checks


class ServiceHealthMonitor:
    """Manages the downstream service health monitoring loop."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._db: pw.PostgresqlDatabase | None = None
        self._connection_attempted = False
        self._last_prune: datetime | None = None
        self._last_status: dict[str, str] = {}
        self.disabled_reason: str | None = None
        self.interval: int = DEFAULT_INTERVAL
        self.retention_days: int = DEFAULT_RETENTION_DAYS

    @property
    def enabled(self) -> bool:
        """Whether health checks are being recorded."""
        return self._db is not None

    @property
    def database(self) -> pw.PostgresqlDatabase | None:
        """The database holding the health history, or None when monitoring is disabled."""
        return self._db

    def _connect(self) -> pw.PostgresqlDatabase | None:
        """Connect to Postgres and make sure the health check table exists."""
        db = get_node_database()

        if db is None:
            settings = get_settings()
            configured = all(
                (
                    settings.postgres_db,
                    settings.postgres_user,
                    settings.postgres_password,
                    settings.postgres_host,
                    settings.postgres_port,
                )
            )
            self.disabled_reason = (
                "Postgres is not configured, service health is not being recorded"
                if not configured
                else "Unable to connect to Postgres at startup, service health is not being recorded"
            )
            return None

        try:
            with bind_service_health(db):  # creates the table if it is not there yet
                pass

        except pw.PeeweeException as db_err:
            self.disabled_reason = (
                f"Unable to prepare the service health table at startup, service health is not being recorded: {db_err}"
            )
            return None

        self.disabled_reason = None
        return db

    async def start(self) -> None:
        """Start the monitoring loop, restarting it if it is already running with a different interval."""
        settings = load_persistent_settings()
        config = settings.service_health or ServiceHealthSettings()
        self.interval = config.interval or DEFAULT_INTERVAL
        self.retention_days = config.retention_days or DEFAULT_RETENTION_DAYS

        restarting = self._task is not None
        await self._cancel_current_task()

        if not self._connection_attempted:
            self._connection_attempted = True
            self._db = self._connect()

        if self._db is None:
            log_event(
                "service_health.disabled",
                event_description=self.disabled_reason or "Service health monitoring is disabled",
                level=logging.WARNING,
                service=ServiceTag.HEALTH,
            )
            return

        log_event(
            "service_health.restarted" if restarting else "service_health.started",
            event_description=f"{'Restarting' if restarting else 'Starting'} downstream service health monitoring "
            f"with interval {self.interval}s and a {self.retention_days} day retention",
            level=logging.INFO,
            service=ServiceTag.HEALTH,
        )
        self._task = asyncio.create_task(self._run_monitor())

    async def _run_monitor(self) -> None:
        """Probe the downstream services on a loop and store the results."""
        while True:
            try:
                await self.sweep()

            except Exception as e:
                log_event(
                    "service_health.error",
                    event_description=f"Error during service health monitoring: {e}",
                    level=logging.ERROR,
                    service=ServiceTag.HEALTH,
                )

            await asyncio.sleep(self.interval)

    async def sweep(self) -> dict[str, dict]:
        """Run one probe cycle, persist it, and prune expired rows when due."""
        results = await probe_all(get_settings())
        self._log_status_changes(results)

        try:
            record_sweep(self._db, results)
            self._prune_if_due()

        except pw.PeeweeException as db_err:
            # A transient database problem must not take monitoring down for good
            log_event(
                "service_health.write_error",
                event_description=f"Unable to store service health results: {db_err}",
                level=logging.ERROR,
                service=ServiceTag.HEALTH,
            )

        return results

    def _log_status_changes(self, results: dict[str, dict]) -> None:
        """Emit an event whenever a service flips between OK and ERROR."""
        for service, result in results.items():
            previous = self._last_status.get(service)
            current = result["status"]
            if previous is not None and previous != current:
                log_event(
                    "service_health.status_change",
                    event_description=f"Service {service} went from {previous} to {current}"
                    + (f": {result['message']}" if result["message"] else ""),
                    level=logging.WARNING if current == ServiceCheckStatus.ERROR else logging.INFO,
                    status_code=result["status_code"],
                    service=ServiceTag.HEALTH,
                )
            self._last_status[service] = current

    def _prune_if_due(self) -> None:
        """Delete expired rows, at most once per PRUNE_INTERVAL."""
        now = datetime.now(UTC)
        if self._last_prune is not None and now - self._last_prune < PRUNE_INTERVAL:
            return

        deleted = prune_old_checks(self._db, self.retention_days)
        self._last_prune = now

        if deleted:
            log_event(
                "service_health.pruned",
                event_description=f"Deleted {deleted} service health checks older than {self.retention_days} days",
                level=logging.DEBUG,
                service=ServiceTag.HEALTH,
            )

    async def _cancel_current_task(self) -> None:
        """Cancel and await the current task if one exists."""
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError, RuntimeError):
                await self._task

        self._task = None

    async def stop(self) -> None:
        """Stop the monitoring task."""
        was_running = self._task is not None
        await self._cancel_current_task()

        if was_running:
            log_event(
                "service_health.stopped",
                event_description="Stopping downstream service health monitoring",
                level=logging.INFO,
                service=ServiceTag.HEALTH,
            )
