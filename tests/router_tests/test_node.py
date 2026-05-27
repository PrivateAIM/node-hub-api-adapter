"""Unit tests for the node settings router."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette import status

from hub_adapter.conf import AutostartSettings, UserSettings
from hub_adapter.routers.node import get_node_settings, node_router, update_node_settings
from tests.conftest import check_routes

EXPECTED_NODE_ROUTE_CONFIG = (
    {
        "path": "/node/settings",
        "name": "node.settings.update",
        "methods": {"POST"},
        "status_code": status.HTTP_202_ACCEPTED,
        "response_model": UserSettings,
    },
    {
        "path": "/node/settings",
        "name": "node.settings.get",
        "methods": {"GET"},
        "status_code": status.HTTP_200_OK,
        "response_model": UserSettings,
    },
)

_DEFAULT_SETTINGS = UserSettings(require_data_store=True, autostart=AutostartSettings())


class TestNodeSettings:
    """Node settings endpoint tests."""

    def test_route_configs(self, test_client):
        """Test endpoint configurations for the node settings router."""
        check_routes(node_router, EXPECTED_NODE_ROUTE_CONFIG, test_client)

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.node.load_persistent_settings")
    async def test_get_node_settings_returns_current_settings(self, mock_load):
        """get_node_settings returns whatever load_persistent_settings returns."""
        mock_load.return_value = _DEFAULT_SETTINGS

        result = await get_node_settings()

        assert result == _DEFAULT_SETTINGS
        mock_load.assert_called_once()

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.node.update_settings")
    async def test_update_node_settings_success(self, mock_update_settings):
        """update_node_settings applies the patch and returns the updated settings."""
        updated = UserSettings(require_data_store=False, autostart=AutostartSettings())
        mock_update_settings.return_value = updated

        payload = UserSettings(require_data_store=False)
        result = await update_node_settings(node_settings=payload)

        assert result == updated
        called_patch = mock_update_settings.call_args[0][0]
        assert called_patch["require_data_store"] is False

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.node.update_settings")
    async def test_update_node_settings_autostart_triggers_manager_update(self, mock_update_settings):
        """update_node_settings calls autostart_manager.update() when autostart key is present."""
        mock_update_settings.return_value = _DEFAULT_SETTINGS

        with patch("hub_adapter.server.autostart_manager") as mock_manager:
            mock_manager.update = AsyncMock()
            payload = UserSettings(autostart=AutostartSettings(enabled=True, interval=30))
            await update_node_settings(node_settings=payload)
            mock_manager.update.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("hub_adapter.routers.node.update_settings")
    async def test_update_node_settings_validation_error_raises_422(self, mock_update_settings):
        """update_node_settings raises HTTP 422 when update_settings raises ValidationError."""
        from pydantic import ValidationError as PydanticValidationError

        class _Bad:
            x: int

        def raise_validation(_):
            from pydantic import BaseModel

            class M(BaseModel):
                model_config = {"extra": "forbid"}
                x: int

            M(x="bad")  # triggers ValidationError

        mock_update_settings.side_effect = raise_validation

        with pytest.raises(HTTPException) as exc_info:
            await update_node_settings(node_settings=UserSettings())

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
