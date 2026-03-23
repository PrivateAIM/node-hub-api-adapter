"""Test FastAPI app instance."""

from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.testclient import TestClient

import hub_adapter.server as server
from hub_adapter.auth import verify_idp_token
from hub_adapter.conf import Settings
from tests.constants import (
    FAKE_USER,
    TEST_MOCK_NODE_CLIENT_ID,
    TEST_URL,
)


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


@pytest.fixture(scope="session", autouse=True)
def test_settings() -> Settings:
    """Create fake settings for testing."""
    env_test_path = Path(__file__).parent.joinpath(".env.test")
    if env_test_path.exists():
        load_dotenv(env_test_path)
        return Settings()

    else:
        return Settings(
            idp_url=TEST_URL,
            api_root_path="",
            podorc_service_url="http://localhost:8000",
            storage_service_url="http://localhost:8005",
            kong_admin_service_url="http://localhost:8001",
            kong_proxy_service_url="http://localhost:8002",
            hub_auth_service_url="https://auth.privateaim.dev",
            hub_service_url="https://core.privateaim.dev",
            hub_node_client_id=TEST_MOCK_NODE_CLIENT_ID,  # fake uuid
            hub_node_client_secret="foobar",
            api_client_id="hub-adapter-test",
            api_client_secret="notASecret",
            http_proxy="http://squid.proxy:3128",
            https_proxy="http://squid.proxy:3128",
            node_svc_oidc_url=TEST_URL,
        )


def check_routes(router: APIRouter, expected_routes: tuple, test_client):
    """Go through observed routes and compare them against what is expected."""
    for route in router.routes:
        observed_route = {
            "path": route.path,
            "name": route.name,
            "methods": route.methods,
            "status_code": route.status_code,
            "response_model": route.response_model,
        }
        assert observed_route in expected_routes
