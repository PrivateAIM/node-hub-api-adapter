"""Test FastAPI app instance."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.testclient import TestClient
from starlette.requests import Request

import hub_adapter.server as server
from hub_adapter.auth import verify_idp_token
from hub_adapter.conf import Settings
from hub_adapter.models.events import AGNOSTIC_EVENTS
from tests.constants import (
    FAKE_USER,
    TEST_MOCK_ROBOT_USER,
    TEST_URL,
)


@pytest.fixture
def mock_event_logger():
    """Create a mock event logger."""
    mock_logger = Mock()
    mock_logger.log_fastapi_request = Mock()
    return mock_logger


@pytest.fixture(scope="session")
def test_client():
    """Test API client."""

    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def authorized_test_client():
    """Test API client."""

    def mock_verify_token():
        return FAKE_USER

    server.app.dependency_overrides[verify_idp_token] = mock_verify_token

    with TestClient(server.app) as authorized_client:
        yield authorized_client

    server.app.dependency_overrides = {}  # Best to remove it


@pytest.fixture(scope="package")
def test_settings() -> Settings:
    """Create fake settings for testing."""
    env_test_path = Path(__file__).parent.joinpath(".env.test")
    if env_test_path.exists():
        load_dotenv(env_test_path)
        return Settings()

    else:
        return Settings(
            IDP_URL=TEST_URL,
            API_ROOT_PATH="",
            PODORC_SERVICE_URL="http://localhost:8000",
            STORAGE_SERVICE_URL="http://localhost:8005",
            KONG_ADMIN_SERVICE_URL="http://localhost:8001",
            KONG_PROXY_SERVICE_URL="http://localhost:8002",
            HUB_AUTH_SERVICE_URL="https://auth.privateaim.dev",
            HUB_SERVICE_URL="https://core.privateaim.dev",
            HUB_ROBOT_USER=TEST_MOCK_ROBOT_USER,  # fake uuid
            HUB_ROBOT_SECRET="foobar",
            API_CLIENT_ID="hub-adapter-test",
            API_CLIENT_SECRET="notASecret",
            HTTP_PROXY="http://squid.proxy:3128",
            HTTPS_PROXY="http://squid.proxy:3128",
            NODE_SVC_OIDC_URL=TEST_URL,
            POSTGRES_EVENT_DB="test_db",
            POSTGRES_EVENT_USER="test_user",
            POSTGRES_EVENT_PASSWORD="test_password",
            POSTGRES_EVENT_HOST="localhost",
            POSTGRES_EVENT_PORT="5432",
            DATA_REQUIRED=True,
        )


def middleware_event_test(endpoint: str, test_client, mock_event_logger):
    """Method for testing if an endpoint triggers the event logging middleware."""
    with patch("hub_adapter.server.get_event_logger", return_value=mock_event_logger):
        response = test_client.get(endpoint)

        mock_event_logger.log_fastapi_request.assert_called()

        call_args = mock_event_logger.log_fastapi_request.call_args
        request = call_args[0][0]
        status_code = call_args[0][1]

        assert isinstance(request, Request)
        assert status_code == response.status_code  # should match


def check_routes(router: APIRouter, expected_routes: tuple, test_client, mock_event_logger):
    """Go through observed routes and compare them against what is expected."""
    for route in router.routes:
        observed_route = {
            "path": route.path,
            "name": route.name,
            "methods": route.methods,
            "status_code": route.status_code,
            "response_model": route.response_model,
        }
        assert route.name in AGNOSTIC_EVENTS
        assert observed_route in expected_routes
        middleware_event_test(route.path, test_client, mock_event_logger)  # check if event middleware called
