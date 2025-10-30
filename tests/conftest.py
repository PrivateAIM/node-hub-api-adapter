"""Test FastAPI app instance."""

from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from hub_adapter.auth import verify_idp_token
from hub_adapter.conf import Settings
from tests.constants import (
    FAKE_USER,
    TEST_MOCK_ROBOT_USER,
    TEST_URL,
)


@pytest.fixture(scope="session")
def test_client():
    """Test API client."""
    from hub_adapter.server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def authorized_test_client():
    """Test API client."""
    from hub_adapter.server import app

    def mock_verify_token():
        return FAKE_USER

    app.dependency_overrides[verify_idp_token] = mock_verify_token

    with TestClient(app) as authorized_client:
        yield authorized_client

    app.dependency_overrides = {}  # Best to remove it


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
            RESULTS_SERVICE_URL="http://localhost:8005",
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
        )
