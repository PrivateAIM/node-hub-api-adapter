"""Unit tests for the logs router."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette import status

from hub_adapter.routers.logs import get_events, logs_router
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
