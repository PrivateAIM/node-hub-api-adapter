"""Unit tests for middleware.py."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.middleware import RequestLoggingMiddleware, _set_user_context


def _make_request(method: str = "GET", path: str = "/", auth_header: str | None = None) -> Request:
    """Build a minimal Starlette Request for testing."""
    headers = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "query_string": b"",
        "asgi": {"version": "3.0"},
    }
    return Request(scope)


class TestSetUserContext:
    """Tests for the _set_user_context helper."""

    def test_no_authorization_header_leaves_context_unset(self):
        """_set_user_context does nothing when no Authorization header is present."""
        from hub_adapter import current_user_id

        current_user_id.set(None)
        request = _make_request()
        _set_user_context(request)

        assert current_user_id.get() is None

    def test_invalid_jwt_does_not_raise(self):
        """_set_user_context swallows exceptions from malformed JWTs."""
        request = _make_request(auth_header="Bearer not.a.valid.jwt.at.all")
        _set_user_context(request)  # must not raise

    def test_valid_jwt_sets_preferred_username(self):
        """_set_user_context sets current_user_id to preferred_username from token claims."""
        import jwt as pyjwt

        from hub_adapter import current_user_id

        token = pyjwt.encode({"preferred_username": "testuser", "sub": "abc123"}, key="x" * 32, algorithm="HS256")
        request = _make_request(auth_header=f"Bearer {token}")
        _set_user_context(request)

        assert current_user_id.get() == "testuser"

    def test_jwt_with_sub_but_no_preferred_username_uses_sub(self):
        """_set_user_context falls back to sub when preferred_username is absent."""
        import jwt as pyjwt

        from hub_adapter import current_user_id

        token = pyjwt.encode({"sub": "user-uuid-123"}, key="x" * 32, algorithm="HS256")
        request = _make_request(auth_header=f"Bearer {token}")
        _set_user_context(request)

        assert current_user_id.get() == "user-uuid-123"


class TestRequestLoggingMiddlewareDispatch:
    """Tests for RequestLoggingMiddleware.dispatch branches."""

    def _make_middleware(self, log_health_checks: bool = False) -> RequestLoggingMiddleware:
        return RequestLoggingMiddleware(app=MagicMock(), log_health_checks=log_health_checks)

    @pytest.mark.asyncio
    async def test_non_standard_method_returns_without_logging(self):
        """dispatch returns immediately for non-standard HTTP methods."""
        middleware = self._make_middleware()
        request = _make_request(method="OPTIONS")
        mock_response = Response(status_code=200)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.log_event") as mock_log:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_docs_path_logs_ui_access_and_returns(self):
        """dispatch logs api.ui.access for /docs and returns without calling log_event."""
        middleware = self._make_middleware()
        request = _make_request(path="/docs")
        mock_response = Response(status_code=200)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.logger") as mock_logger:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_logger.info.assert_called_once()
        assert mock_logger.info.call_args[0][0] == "api.ui.access"

    @pytest.mark.asyncio
    async def test_route_none_returns_without_logging(self):
        """dispatch returns without logging when the request has no matched route."""
        middleware = self._make_middleware()
        request = _make_request(path="/nonexistent-path")
        mock_response = Response(status_code=404)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.log_event") as mock_log:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_skipped_when_log_health_checks_false(self):
        """dispatch skips logging for health.status.get when log_health_checks=False."""
        middleware = self._make_middleware(log_health_checks=False)
        request = _make_request(path="/healthz")

        mock_route = MagicMock()
        mock_route.name = "health.status.get"
        request.scope["route"] = mock_route

        mock_response = Response(status_code=200)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.log_event") as mock_log:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_podorc_status_skipped(self):
        """dispatch skips logging for podorc.status.get."""
        middleware = self._make_middleware()
        request = _make_request(path="/po/status")

        mock_route = MagicMock()
        mock_route.name = "podorc.status.get"
        request.scope["route"] = mock_route

        mock_response = Response(status_code=200)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.log_event") as mock_log:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_untracked_event_skips_logging(self):
        """dispatch skips log_event for routes whose name is not in TRACKED_EVENTS."""
        middleware = self._make_middleware()
        request = _make_request(path="/some/internal/path")

        mock_route = MagicMock()
        mock_route.name = "not.a.tracked.event"
        request.scope["route"] = mock_route

        mock_response = Response(status_code=200)

        async def call_next(_):
            return mock_response

        with patch("hub_adapter.middleware.log_event") as mock_log:
            response = await middleware.dispatch(request, call_next)

        assert response is mock_response
        mock_log.assert_not_called()
