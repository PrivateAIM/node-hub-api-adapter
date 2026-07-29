"""Collection of unit tests for the Kong consumer cleanup sweep."""

import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from kong_admin_client import ApiException, Consumer
from starlette import status

from hub_adapter.maintenance import (
    EXECUTED_AFTER_RUNNING_GRACE,
    NEVER_RAN_GRACE,
    KongCleanupManager,
    KongConsumerReaper,
)
from tests.constants import TEST_MOCK_ANALYSIS_ID, TEST_MOCK_NODE_ID, TEST_MOCK_PROJECT_ID


def _consumer(analysis_id: str, project_id: str = TEST_MOCK_PROJECT_ID) -> Consumer:
    return Consumer(
        id=str(uuid.uuid4()),
        username=f"analysis-{analysis_id}",
        tags=[f"project:{project_id}", f"analysis:{analysis_id}"],
    )


def _analysis_node(analysis_id: str, execution_status: str | None):
    return SimpleNamespace(analysis_id=uuid.UUID(analysis_id), execution_status=execution_status)


class TestKongConsumerReaperProcess:
    """Unit tests for the pure per-analysis decision logic."""

    def setup_method(self):
        self.gather_deps_patcher = patch.object(KongConsumerReaper, "gather_deps")
        self.gather_deps_patcher.start()
        self.reaper = KongConsumerReaper()

    def teardown_method(self):
        self.gather_deps_patcher.stop()

    @pytest.mark.asyncio
    async def test_executing_marks_seen_and_does_not_delete(self):
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "executing", datetime.now(UTC))
        assert deleted is False
        assert self.reaper._history[TEST_MOCK_ANALYSIS_ID]["seen_executing"] is True
        assert self.reaper._history[TEST_MOCK_ANALYSIS_ID]["terminal_since"] is None

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_executed_deletes_immediately(self, mock_delete):
        mock_delete.return_value = True
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "executed", datetime.now(UTC))
        assert deleted is True
        mock_delete.assert_awaited_once_with(TEST_MOCK_ANALYSIS_ID, "executed")

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_failed_first_sighting_does_not_delete(self, mock_delete):
        now = datetime.now(UTC)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "failed", now)
        assert deleted is False
        mock_delete.assert_not_called()
        assert self.reaper._history[TEST_MOCK_ANALYSIS_ID]["terminal_since"] == now

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_failed_after_executing_waits_for_grace(self, mock_delete):
        now = datetime.now(UTC)
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": now}

        # Not enough time has passed yet
        still_too_soon = now + EXECUTED_AFTER_RUNNING_GRACE - timedelta(seconds=1)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "failed", still_too_soon)
        assert deleted is False
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_failed_after_executing_deletes_past_grace(self, mock_delete):
        mock_delete.return_value = True
        now = datetime.now(UTC)
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": now}

        past_grace = now + EXECUTED_AFTER_RUNNING_GRACE + timedelta(seconds=1)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "failed", past_grace)
        assert deleted is True
        mock_delete.assert_awaited_once_with(TEST_MOCK_ANALYSIS_ID, "failed-after-executing")

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_failed_never_executed_uses_longer_grace(self, mock_delete):
        now = datetime.now(UTC)
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": False, "terminal_since": now}

        # Past the short grace but not the long one: must not delete yet
        past_short_grace = now + EXECUTED_AFTER_RUNNING_GRACE + timedelta(seconds=1)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "failed", past_short_grace)
        assert deleted is False
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_failed_never_executed_deletes_past_long_grace(self, mock_delete):
        mock_delete.return_value = True
        now = datetime.now(UTC)
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": False, "terminal_since": now}

        past_long_grace = now + NEVER_RAN_GRACE + timedelta(seconds=1)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "failed", past_long_grace)
        assert deleted is True
        mock_delete.assert_awaited_once_with(TEST_MOCK_ANALYSIS_ID, "failed-never-executed")

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_stopped_treated_like_failed(self, mock_delete):
        mock_delete.return_value = True
        now = datetime.now(UTC)
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": now}

        past_grace = now + EXECUTED_AFTER_RUNNING_GRACE + timedelta(seconds=1)
        deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, "stopped", past_grace)
        assert deleted is True
        mock_delete.assert_awaited_once_with(TEST_MOCK_ANALYSIS_ID, "stopped-after-executing")

    @pytest.mark.asyncio
    @patch.object(KongConsumerReaper, "_delete", new_callable=AsyncMock)
    async def test_non_terminal_statuses_are_ignored(self, mock_delete):
        for status_val in ("starting", "started", "stopping", None):
            deleted = await self.reaper._process(TEST_MOCK_ANALYSIS_ID, status_val, datetime.now(UTC))
            assert deleted is False
        mock_delete.assert_not_called()


class TestKongConsumerReaperDelete:
    """Unit tests for the actual delete call and its bookkeeping."""

    def setup_method(self):
        self.gather_deps_patcher = patch.object(KongConsumerReaper, "gather_deps")
        self.gather_deps_patcher.start()
        self.reaper = KongConsumerReaper()

    def teardown_method(self):
        self.gather_deps_patcher.stop()

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    async def test_delete_success_clears_history(self, mock_delete_analysis, mock_log_event):
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": None}
        result = await self.reaper._delete(TEST_MOCK_ANALYSIS_ID, "executed")

        assert result is True
        assert TEST_MOCK_ANALYSIS_ID not in self.reaper._history
        mock_log_event.assert_any_call(
            "kong_cleanup.consumer_deleted",
            event_description=f"Deleted Kong consumer for analysis {TEST_MOCK_ANALYSIS_ID} (executed)",
            level=logging.INFO,
            service=ANY,
        )

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    async def test_delete_failure_keeps_history_and_logs(self, mock_delete_analysis, mock_log_event):
        mock_delete_analysis.side_effect = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="gone")
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": None}

        result = await self.reaper._delete(TEST_MOCK_ANALYSIS_ID, "executed")

        assert result is False
        assert TEST_MOCK_ANALYSIS_ID in self.reaper._history
        mock_log_event.assert_any_call(
            "kong_cleanup.delete_error",
            event_description=ANY,
            level=logging.ERROR,
            service=ANY,
        )


class TestKongConsumerReaperSweep:
    """Unit tests for a full sweep pass, with the Hub/Kong calls mocked out."""

    def setup_method(self):
        self.gather_deps_patcher = patch.object(KongConsumerReaper, "gather_deps")
        self.gather_deps_patcher.start()
        self.reaper = KongConsumerReaper()

    def teardown_method(self):
        self.gather_deps_patcher.stop()

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.list_analysis_nodes", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_node_id", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_deletes_executed_consumer(
        self, mock_get_analyses, mock_get_node_id, mock_list_nodes, mock_delete_analysis
    ):
        mock_get_analyses.return_value = {"data": [_consumer(TEST_MOCK_ANALYSIS_ID)]}
        mock_get_node_id.return_value = TEST_MOCK_NODE_ID
        mock_list_nodes.return_value = [_analysis_node(TEST_MOCK_ANALYSIS_ID, "executed")]

        deleted = await self.reaper.sweep()

        assert deleted == {TEST_MOCK_ANALYSIS_ID}
        mock_delete_analysis.assert_awaited_once_with(settings=self.reaper.settings, analysis_id=TEST_MOCK_ANALYSIS_ID)

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.list_analysis_nodes", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_node_id", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_leaves_running_consumer_alone(
        self, mock_get_analyses, mock_get_node_id, mock_list_nodes, mock_delete_analysis
    ):
        mock_get_analyses.return_value = {"data": [_consumer(TEST_MOCK_ANALYSIS_ID)]}
        mock_get_node_id.return_value = TEST_MOCK_NODE_ID
        mock_list_nodes.return_value = [_analysis_node(TEST_MOCK_ANALYSIS_ID, "executing")]

        deleted = await self.reaper.sweep()

        assert deleted == set()
        mock_delete_analysis.assert_not_called()
        assert self.reaper._history[TEST_MOCK_ANALYSIS_ID]["seen_executing"] is True

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.list_analysis_nodes", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_node_id", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_prunes_history_for_gone_consumers(
        self, mock_get_analyses, mock_get_node_id, mock_list_nodes, mock_delete_analysis
    ):
        other_id = "00000000-0000-0000-0000-000000000999"
        self.reaper._history[other_id] = {"seen_executing": True, "terminal_since": None}

        mock_get_analyses.return_value = {"data": [_consumer(TEST_MOCK_ANALYSIS_ID)]}
        mock_get_node_id.return_value = TEST_MOCK_NODE_ID
        mock_list_nodes.return_value = [_analysis_node(TEST_MOCK_ANALYSIS_ID, "starting")]

        await self.reaper.sweep()

        assert other_id not in self.reaper._history

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_handles_kong_fetch_error(self, mock_get_analyses, mock_log_event):
        mock_get_analyses.side_effect = ApiException(status=503, reason="Kong down")

        deleted = await self.reaper.sweep()

        assert deleted == set()
        mock_log_event.assert_any_call(
            "kong_cleanup.kong_fetch_error",
            event_description=ANY,
            level=logging.ERROR,
            service=ANY,
        )

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.get_node_id", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_handles_hub_fetch_error(self, mock_get_analyses, mock_get_node_id, mock_log_event):
        mock_get_analyses.return_value = {"data": [_consumer(TEST_MOCK_ANALYSIS_ID)]}
        mock_get_node_id.side_effect = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="down")

        deleted = await self.reaper.sweep()

        assert deleted == set()
        mock_log_event.assert_any_call(
            "kong_cleanup.hub_fetch_error",
            event_description=ANY,
            level=logging.ERROR,
            service=ANY,
        )

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_with_no_consumers_clears_history(self, mock_get_analyses):
        self.reaper._history[TEST_MOCK_ANALYSIS_ID] = {"seen_executing": True, "terminal_since": None}
        mock_get_analyses.return_value = {"data": []}

        deleted = await self.reaper.sweep()

        assert deleted == set()
        assert self.reaper._history == {}

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.delete_analysis", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.list_analysis_nodes", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_node_id", new_callable=AsyncMock)
    @patch("hub_adapter.maintenance.get_analyses")
    async def test_sweep_ignores_consumer_without_analysis_tag(
        self, mock_get_analyses, mock_get_node_id, mock_list_nodes, mock_delete_analysis
    ):
        untagged = Consumer(
            id=str(uuid.uuid4()), username="health-x", tags=["health", f"project:{TEST_MOCK_PROJECT_ID}"]
        )
        mock_get_analyses.return_value = {"data": [untagged]}
        mock_get_node_id.return_value = TEST_MOCK_NODE_ID
        mock_list_nodes.return_value = []

        deleted = await self.reaper.sweep()

        assert deleted == set()
        mock_delete_analysis.assert_not_called()


class TestKongCleanupManager:
    """Unit tests for KongCleanupManager. Cleanup is always-on (not user-toggleable), so there's no
    enabled/disabled state to test, only start/restart/stop.
    """

    def test_manager_init(self):
        manager = KongCleanupManager()
        assert manager._task is None

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.load_persistent_settings")
    async def test_manager_start(self, mock_load_settings, mock_log_event):
        manager = KongCleanupManager()
        mock_settings = MagicMock()
        mock_settings.kong_cleanup.interval = 30
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.maintenance.KongConsumerReaper"):
            await manager.start()

            assert manager._task is not None
            mock_log_event.assert_any_call(
                "kong_cleanup.started",
                event_description=ANY,
                level=logging.INFO,
                service=ANY,
            )

        await manager.stop()

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    @patch("hub_adapter.maintenance.load_persistent_settings")
    async def test_manager_start_twice_restarts(self, mock_load_settings, mock_log_event):
        manager = KongCleanupManager()
        mock_settings = MagicMock()
        mock_settings.kong_cleanup.interval = 30
        mock_load_settings.return_value = mock_settings

        with patch("hub_adapter.maintenance.KongConsumerReaper"):
            await manager.start()
            first_task = manager._task

            mock_settings.kong_cleanup.interval = 60
            await manager.start()

            assert manager._task != first_task
            mock_log_event.assert_any_call(
                "kong_cleanup.restarted",
                event_description=ANY,
                level=logging.INFO,
                service=ANY,
            )

        await manager.stop()

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    async def test_manager_stop(self, mock_log_event):
        manager = KongCleanupManager()
        manager._task = asyncio.create_task(asyncio.sleep(10))

        await manager.stop()

        assert manager._task is None
        mock_log_event.assert_any_call(
            "kong_cleanup.stopped",
            event_description=ANY,
            level=logging.INFO,
            service=ANY,
        )

    @pytest.mark.asyncio
    async def test_manager_stop_when_never_started_is_a_noop(self):
        manager = KongCleanupManager()
        await manager.stop()
        assert manager._task is None

    @pytest.mark.asyncio
    @patch("hub_adapter.maintenance.log_event")
    async def test_run_cleanup_error_handling(self, mock_log_event):
        manager = KongCleanupManager()

        with patch("hub_adapter.maintenance.KongConsumerReaper") as mock_reaper_cls:
            mock_instance = MagicMock()
            mock_reaper_cls.return_value = mock_instance
            mock_instance.sweep = AsyncMock(side_effect=Exception("Test error"))

            task = asyncio.create_task(manager._run_cleanup(interval=1))
            await asyncio.sleep(0.5)

            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

            mock_reaper_cls.assert_called()
            mock_instance.sweep.assert_awaited()
            mock_log_event.assert_called()
