"""Unit tests for the logs router."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette import status

from hub_adapter.routers.logs import (
    _group_by_run,
    get_analysis_log_history,
    get_analysis_logs,
    get_events,
    logs_router,
)
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_LOGS_ROUTE_CONFIG


class TestLogs:
    """Logs endpoint configuration and behaviour tests."""

    def test_route_configs(self, test_client):
        """Test endpoint configurations for the logs router."""
        check_routes(logs_router, EXPECTED_LOGS_ROUTE_CONFIG, test_client)

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_get_events_503_when_victoria_logs_url_not_set(self, mock_get_settings):
        """get_events raises 503 when victoria_logs_url is None."""
        mock_get_settings.return_value.victoria_logs_url = None

        with pytest.raises(HTTPException) as exc_info:
            await get_events()

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc_info.value.detail == "Event log service is not configured"

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.count_logs")
    @patch("hub_adapter.routers.logs.query_logs")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_get_events_returns_data_when_configured(
        self, mock_get_settings, mock_query_logs, mock_count_logs
    ):
        """get_events returns paginated data when victoria_logs_url is configured."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_query_logs.return_value = [{"event_name": "hub.project.get", "message": "test"}]
        mock_count_logs.return_value = 1

        result = await get_events(limit=10, offset=0)

        assert result["meta"]["total"] == 1
        assert result["meta"]["count"] == 1
        assert result["meta"]["limit"] == 10
        assert result["meta"]["offset"] == 0
        assert len(result["data"]) == 1


class TestGroupByRun:
    """Tests for the _group_by_run helper."""

    def test_groups_nginx_and_analysis_containers_by_run_number(self):
        """_group_by_run correctly assigns nginx and analysis containers to run buckets."""
        names = [
            "nginx-analysis-abc-0",
            "analysis-abc-0",
            "nginx-analysis-abc-1",
            "analysis-abc-1",
        ]
        runs = _group_by_run(names)

        assert runs[0] == {"nginx": "nginx-analysis-abc-0", "analysis": "analysis-abc-0"}
        assert runs[1] == {"nginx": "nginx-analysis-abc-1", "analysis": "analysis-abc-1"}

    def test_ignores_containers_without_numeric_suffix(self):
        """_group_by_run skips containers whose names have no trailing digit."""
        names = ["nginx-analysis-abc", "some-other-container"]
        runs = _group_by_run(names)

        assert runs == {}

    def test_handles_only_analysis_container(self):
        """_group_by_run creates a run entry with only analysis when nginx is absent."""
        names = ["analysis-abc-2"]
        runs = _group_by_run(names)

        assert runs[2] == {"analysis": "analysis-abc-2"}
        assert "nginx" not in runs[2]

    def test_returns_empty_dict_for_empty_input(self):
        """_group_by_run returns an empty dict when given no container names."""
        assert _group_by_run([]) == {}


class TestGetAnalysisLogs:
    """Tests for the get_analysis_logs endpoint."""

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_raises_503_when_victoria_logs_url_not_set(self, mock_get_settings):
        """get_analysis_logs raises 503 when victoria_logs_url is None."""
        mock_get_settings.return_value.victoria_logs_url = None
        analysis_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await get_analysis_logs(analysis_id)

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc_info.value.detail == "Log service is not configured"

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._get_analysis_container_names")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_raises_404_when_no_containers_found(self, mock_get_settings, mock_get_names):
        """get_analysis_logs raises 404 when no matching containers exist."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = []
        analysis_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await get_analysis_logs(analysis_id)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._query_pod_logs")
    @patch("hub_adapter.routers.logs._get_analysis_container_names")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_latest_run_logs(self, mock_get_settings, mock_get_names, mock_query_logs):
        """get_analysis_logs returns logs for the highest run number only."""
        analysis_id = uuid.uuid4()
        analysis_id_str = str(analysis_id)
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = [
            f"nginx-analysis-{analysis_id_str}-0",
            f"analysis-{analysis_id_str}-0",
            f"nginx-analysis-{analysis_id_str}-1",
            f"analysis-{analysis_id_str}-1",
        ]
        nginx_logs = [{"timestamp": "2024-01-01T00:00:00Z", "message": "nginx log"}]
        analysis_logs = [{"timestamp": "2024-01-01T00:00:01Z", "message": "analysis log"}]
        mock_query_logs.side_effect = lambda name: nginx_logs if "nginx" in name else analysis_logs

        result = await get_analysis_logs(analysis_id)

        assert result["analysis_id"] == analysis_id
        assert result["run_number"] == 1
        assert result["nginx_logs"] == nginx_logs
        assert result["analysis_logs"] == analysis_logs

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._query_pod_logs")
    @patch("hub_adapter.routers.logs._get_analysis_container_names")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_empty_lists_when_container_type_absent(
        self, mock_get_settings, mock_get_names, mock_query_logs
    ):
        """get_analysis_logs returns empty lists for container types not present in the run."""
        analysis_id = uuid.uuid4()
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = [f"analysis-{analysis_id}-0"]
        mock_query_logs.return_value = [{"timestamp": "2024-01-01T00:00:00Z", "message": "log"}]

        result = await get_analysis_logs(analysis_id)

        assert result["nginx_logs"] == []
        assert len(result["analysis_logs"]) == 1


class TestGetAnalysisLogHistory:
    """Tests for the get_analysis_log_history endpoint."""

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_raises_503_when_victoria_logs_url_not_set(self, mock_get_settings):
        """get_analysis_log_history raises 503 when victoria_logs_url is None."""
        mock_get_settings.return_value.victoria_logs_url = None
        analysis_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await get_analysis_log_history(analysis_id)

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc_info.value.detail == "Log service is not configured"

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._query_pod_logs")
    @patch("hub_adapter.routers.logs._get_analysis_container_names")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_all_runs_sorted_ascending(
        self, mock_get_settings, mock_get_names, mock_query_logs
    ):
        """get_analysis_log_history returns every run ordered by run number ascending."""
        analysis_id = uuid.uuid4()
        analysis_id_str = str(analysis_id)
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = [
            f"analysis-{analysis_id_str}-2",
            f"analysis-{analysis_id_str}-0",
            f"analysis-{analysis_id_str}-1",
        ]
        mock_query_logs.return_value = []

        result = await get_analysis_log_history(analysis_id)

        assert result["analysis_id"] == analysis_id
        run_numbers = [r["run_number"] for r in result["runs"]]
        assert run_numbers == [0, 1, 2]

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._get_analysis_container_names")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_empty_runs_list_when_no_containers_found(
        self, mock_get_settings, mock_get_names
    ):
        """get_analysis_log_history returns an empty runs list when no containers exist."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = []
        analysis_id = uuid.uuid4()

        result = await get_analysis_log_history(analysis_id)

        assert result["analysis_id"] == analysis_id
        assert result["runs"] == []
