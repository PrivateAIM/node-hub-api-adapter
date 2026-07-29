"""Background sweep that deletes Kong analysis consumers once their analysis has reached a status
that means the consumer will never be used again, and would otherwise sit in Kong forever.

`execution_status` on each analysis is used as the source of truth rather than the PO's own live status endpoint.
The PO deletes its own record for an analysis almost immediately after it reaches "executed", so polling the PO
risks missing that transition entirely.
"""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from kong_admin_client import ApiException

from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import (
    get_core_client,
    get_flame_hub_auth_flow,
    get_node_id,
    get_settings,
    get_ssl_context,
)
from hub_adapter.middleware import log_event
from hub_adapter.routers.hub import _parse_query_params, list_analysis_nodes
from hub_adapter.routers.kong import delete_analysis, get_analyses
from hub_adapter.user_settings import load_persistent_settings
from hub_adapter.utils import parse_tags

logger = logging.getLogger(__name__)

EXECUTED_AFTER_RUNNING_GRACE = timedelta(seconds=60)
NEVER_RAN_GRACE = timedelta(minutes=10)

# Hub execution_status values that mean the analysis is done and won't run again.
_TERMINAL_STATUSES = {"failed", "stopped"}


class KongConsumerReaper:
    """Sweeps Kong analysis consumers and deletes the ones whose analysis has finished for good."""

    def __init__(self):
        self.settings = None
        self.core_client = None
        # analysis_id -> {"seen_executing": bool, "terminal_since": datetime | None}
        self._history: dict[str, dict] = {}

        self.gather_deps()  # populate self.settings and self.core_client

    def gather_deps(self):
        """Gather all the dependencies needed to run the cleanup sweep."""
        settings = get_settings()
        ssl_ctx = get_ssl_context(settings)
        hub_auth = get_flame_hub_auth_flow(ssl_ctx, settings)
        core_client = get_core_client(hub_auth, ssl_ctx, settings)

        self.settings = settings
        self.core_client = core_client

    async def sweep(self) -> set[str]:
        """Run one cleanup pass, returning the set of analysis_ids whose consumer was deleted."""
        deleted: set[str] = set()

        try:
            consumers = get_analyses(self.settings)

        except (ApiException, HTTPException) as e:
            log_event(
                "kong_cleanup.kong_fetch_error",
                event_description=f"Unable to list Kong analysis consumers: {e}",
                level=logging.ERROR,
                service=ServiceTag.KONG_CLEANUP,
            )
            return deleted

        analysis_ids = {parse_tags(c.tags).get("analysis") for c in consumers["data"]}
        analysis_ids.discard(None)

        if not analysis_ids:
            self._history.clear()
            return deleted

        try:
            node_id = await get_node_id(core_client=self.core_client, settings=self.settings)
            analysis_nodes = await list_analysis_nodes(
                node_id=node_id,
                query_params=_parse_query_params(),
                core_client=self.core_client,
            )

        except HTTPException as e:
            log_event(
                "kong_cleanup.hub_fetch_error",
                event_description=f"Unable to fetch analysis statuses from the Hub: {e}",
                level=logging.ERROR,
                service=ServiceTag.KONG_CLEANUP,
            )
            return deleted

        statuses = {str(entry.analysis_id): entry.execution_status for entry in analysis_nodes if entry.analysis_id}

        now = datetime.now(UTC)
        for analysis_id in analysis_ids:
            if await self._process(analysis_id, statuses.get(analysis_id), now):
                deleted.add(analysis_id)

        # Bound memory to consumers that still exist; anything else is stale tracking.
        for stale_id in set(self._history) - analysis_ids:
            del self._history[stale_id]

        return deleted

    async def _process(self, analysis_id: str, execution_status: str | None, now: datetime) -> bool:
        """Apply the cleanup decision for a single analysis. Returns True if its consumer was deleted."""
        entry = self._history.setdefault(analysis_id, {"seen_executing": False, "terminal_since": None})

        if execution_status == "executing":
            entry["seen_executing"] = True
            entry["terminal_since"] = None
            return False

        if execution_status == "executed":
            return await self._delete(analysis_id, "executed")

        if execution_status in _TERMINAL_STATUSES:
            if entry["terminal_since"] is None:
                entry["terminal_since"] = now
                return False

            grace = EXECUTED_AFTER_RUNNING_GRACE if entry["seen_executing"] else NEVER_RAN_GRACE
            if now - entry["terminal_since"] >= grace:
                reason = f"{execution_status}-{'after-executing' if entry['seen_executing'] else 'never-executed'}"
                return await self._delete(analysis_id, reason)

            return False

        # starting/started/stopping/no Hub record: not terminal, leave the consumer alone
        return False

    async def _delete(self, analysis_id: str, reason: str) -> bool:
        try:
            await delete_analysis(settings=self.settings, analysis_id=analysis_id)

        except HTTPException as e:
            log_event(
                "kong_cleanup.delete_error",
                event_description=f"Failed to delete Kong consumer for analysis {analysis_id}: {e}",
                level=logging.ERROR,
                service=ServiceTag.KONG_CLEANUP,
            )
            return False

        log_event(
            "kong_cleanup.consumer_deleted",
            event_description=f"Deleted Kong consumer for analysis {analysis_id} ({reason})",
            level=logging.INFO,
            service=ServiceTag.KONG_CLEANUP,
        )
        self._history.pop(analysis_id, None)
        return True


class KongCleanupManager:
    """Manages the Kong consumer cleanup task lifecycle.

    Unlike autostart, this is not user-toggleable: it always runs for the lifetime of the app.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the cleanup loop, restarting it if it's already running with a different interval."""
        settings = load_persistent_settings()
        interval = settings.kong_cleanup.interval if settings.kong_cleanup else 30

        restarting = self._task is not None
        await self._cancel_current_task()

        log_event(
            "kong_cleanup.restarted" if restarting else "kong_cleanup.started",
            event_description=f"{'Restarting' if restarting else 'Starting'} Kong consumer cleanup "
            f"with interval {interval}s",
            level=logging.INFO,
            service=ServiceTag.KONG_CLEANUP,
        )
        self._task = asyncio.create_task(self._run_cleanup(interval))

    async def _run_cleanup(self, interval: int) -> None:
        """Run the cleanup sweep loop."""
        reaper = KongConsumerReaper()
        while True:
            try:
                log_event(
                    "kong_cleanup.poll",
                    event_description="Sweeping for stale Kong analysis consumers",
                    level=logging.DEBUG,
                    service=ServiceTag.KONG_CLEANUP,
                )
                await reaper.sweep()

            except Exception as e:
                log_event(
                    "kong_cleanup.error",
                    event_description=f"Error during Kong consumer cleanup: {e}",
                    level=logging.ERROR,
                    service=ServiceTag.KONG_CLEANUP,
                )

            await asyncio.sleep(interval)

    async def _cancel_current_task(self) -> None:
        """Cancel and await the current task if one exists."""
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError, RuntimeError):
                await self._task

        self._task = None

    async def stop(self) -> None:
        """Stop the cleanup task."""
        was_running = self._task is not None
        await self._cancel_current_task()

        if was_running:
            log_event(
                "kong_cleanup.stopped",
                event_description="Stopping Kong consumer cleanup",
                level=logging.INFO,
                service=ServiceTag.KONG_CLEANUP,
            )
