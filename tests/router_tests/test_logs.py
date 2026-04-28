"""Unit tests for the logs router."""

import datetime
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette import status

from hub_adapter.routers.logs import (
    _group_by_run,
    get_analysis_log_history,
    get_analysis_logs,
    get_api_requests,
    get_events,
    logs_router,
    raw_log_query,
)
from hub_adapter.schemas.logs import ApiRequestCountResponse, LogQLQueryRequest
from tests.conftest import check_routes
from tests.router_tests.routes import EXPECTED_LOGS_ROUTE_CONFIG


class TestApiRequestCountSchemas:
    """Tests for ApiRequestCountResponse Pydantic model."""

    def test_api_request_count_response_fields(self):
        """ApiRequestCountResponse stores total and a dict mapping path to method counts."""
        response = ApiRequestCountResponse(
            total=12,
            data={"/node/settings": {"GET": 12, "total": 12}},
        )
        assert response.total == 12
        assert response.data["/node/settings"]["GET"] == 12
        assert response.data["/node/settings"]["total"] == 12


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
    async def test_get_events_returns_data_when_configured(self, mock_get_settings, mock_query_logs, mock_count_logs):
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
    async def test_returns_all_runs_sorted_ascending(self, mock_get_settings, mock_get_names, mock_query_logs):
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
    async def test_returns_empty_runs_list_when_no_containers_found(self, mock_get_settings, mock_get_names):
        """get_analysis_log_history returns an empty runs list when no containers exist."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_get_names.return_value = []
        analysis_id = uuid.uuid4()

        result = await get_analysis_log_history(analysis_id)

        assert result["analysis_id"] == analysis_id
        assert result["runs"] == []


class TestRawLogQuery:
    """Tests for the POST /logs/query endpoint."""

    def test_route_configs(self, test_client):
        """Test endpoint configurations for the logs router."""
        check_routes(logs_router, EXPECTED_LOGS_ROUTE_CONFIG, test_client)

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_raises_503_when_victoria_logs_url_not_set(self, mock_get_settings):
        """raw_log_query raises 503 when victoria_logs_url is None."""
        mock_get_settings.return_value.victoria_logs_url = None

        with pytest.raises(HTTPException) as exc_info:
            await raw_log_query(LogQLQueryRequest(query="*"))

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc_info.value.detail == "Log service is not configured"

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.count_logs")
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_paginated_data_when_configured(self, mock_get_settings, mock_execute, mock_count):
        """raw_log_query returns data and meta envelope when configured."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [{"_msg": "hello", "level": "info"}]
        mock_count.return_value = 1

        body = LogQLQueryRequest(query="*", limit=10, offset=0)
        result = await raw_log_query(body)

        assert result["meta"]["total"] == 1
        assert result["meta"]["count"] == 1
        assert result["meta"]["limit"] == 10
        assert result["meta"]["offset"] == 0
        assert len(result["data"]) == 1
        assert result["data"][0] == {"_msg": "hello", "level": "info"}


class TestGetApiRequests:
    """Tests for the GET /requests endpoint."""

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_raises_503_when_victoria_logs_url_not_set(self, mock_get_settings):
        """get_api_requests raises 503 when victoria_logs_url is None."""
        mock_get_settings.return_value.victoria_logs_url = None

        with pytest.raises(HTTPException) as exc_info:
            await get_api_requests()

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc_info.value.detail == "Event log service is not configured"

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_total_and_per_endpoint_breakdown(self, mock_get_settings, mock_execute):
        """get_api_requests returns the sum total and one dict entry per endpoint."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/node/settings", "requests": "12"},
            {"method": "POST", "path": "/events/signin", "requests": "6"},
        ]

        result = await get_api_requests()

        assert result["total"] == 18
        assert len(result["data"]) == 2
        assert result["data"]["/node/settings"] == {"GET": 12, "total": 12}
        assert result["data"]["/events/signin"] == {"POST": 6, "total": 6}

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_strips_query_params_and_reaggregates(self, mock_get_settings, mock_execute):
        """get_api_requests strips query strings and merges counts for the same base path."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/analysis-nodes?include=analysis,node", "requests": "8"},
            {"method": "GET", "path": "/analysis-nodes?sort=-updated_at", "requests": "3"},
        ]

        result = await get_api_requests()

        assert result["total"] == 11
        assert len(result["data"]) == 1
        assert result["data"]["/analysis-nodes"] == {"GET": 11, "total": 11}

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_multiple_methods_per_endpoint(self, mock_get_settings, mock_execute):
        """get_api_requests groups multiple methods under the same endpoint key."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/node/settings", "requests": "10"},
            {"method": "POST", "path": "/node/settings", "requests": "3"},
        ]

        result = await get_api_requests()

        assert result["total"] == 13
        assert result["data"]["/node/settings"]["GET"] == 10
        assert result["data"]["/node/settings"]["POST"] == 3
        assert result["data"]["/node/settings"]["total"] == 13

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_filters_by_endpoint_prefix(self, mock_get_settings, mock_execute):
        """get_api_requests filters the breakdown and total to paths starting with the given prefix."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/node/settings", "requests": "12"},
            {"method": "GET", "path": "/analysis-nodes", "requests": "8"},
        ]

        result = await get_api_requests(endpoint="/node")

        assert result["total"] == 12
        assert list(result["data"].keys()) == ["/node/settings"]

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_returns_zero_total_when_no_paths_match_prefix(self, mock_get_settings, mock_execute):
        """get_api_requests returns total 0 and empty dict when no paths match the given prefix."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/node/settings", "requests": "12"},
        ]

        result = await get_api_requests(endpoint="/nonexistent")

        assert result["total"] == 0
        assert result["data"] == {}

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_passes_date_range_params_to_query(self, mock_get_settings, mock_execute):
        """get_api_requests forwards start_date and end_date to _execute_raw_query."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = []
        start = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 4, 28, tzinfo=datetime.timezone.utc)

        await get_api_requests(start_date=start, end_date=end)

        passed_params = mock_execute.call_args[0][1]
        assert passed_params["start"] == start.isoformat()
        assert passed_params["end"] == end.isoformat()

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_filters_by_method(self, mock_get_settings, mock_execute):
        """get_api_requests only returns endpoints that have the given method."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "GET", "path": "/node/settings", "requests": "10"},
            {"method": "DELETE", "path": "/local", "requests": "4"},
            {"method": "GET", "path": "/local", "requests": "2"},
        ]

        result = await get_api_requests(method="DELETE")

        assert result["total"] == 4
        assert list(result["data"].keys()) == ["/local"]
        assert result["data"]["/local"] == {"DELETE": 4, "total": 4}

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_method_filter_is_case_insensitive(self, mock_get_settings, mock_execute):
        """get_api_requests uppercases the method filter before comparing."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "DELETE", "path": "/local", "requests": "4"},
        ]

        result = await get_api_requests(method="delete")

        assert result["total"] == 4
        assert "/local" in result["data"]

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.logs._execute_raw_query")
    @patch("hub_adapter.routers.logs.get_settings")
    async def test_filters_by_method_and_endpoint(self, mock_get_settings, mock_execute):
        """get_api_requests applies both method and endpoint filters together."""
        mock_get_settings.return_value.victoria_logs_url = "http://victoria:9428"
        mock_execute.return_value = [
            {"method": "DELETE", "path": "/local", "requests": "4"},
            {"method": "DELETE", "path": "/node/settings", "requests": "1"},
            {"method": "GET", "path": "/node/settings", "requests": "10"},
        ]

        result = await get_api_requests(method="DELETE", endpoint="/node")

        assert result["total"] == 1
        assert list(result["data"].keys()) == ["/node/settings"]
        assert result["data"]["/node/settings"] == {"DELETE": 1, "total": 1}
