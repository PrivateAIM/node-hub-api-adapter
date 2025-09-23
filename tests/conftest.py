"""Test FastAPI app instance."""

import os
import time
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from hub_adapter.conf import Settings
from tests.constants import DS_TYPE, TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID
from tests.pseudo_auth import BearerAuth


@pytest.fixture(scope="session")
def test_client():
    """Test API client."""
    from hub_adapter.server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="package")
def test_settings() -> Settings:
    """Create fake settings for testing."""
    env_test_path = Path(__file__).parent.joinpath(".env.test")
    if env_test_path.exists():
        load_dotenv(env_test_path)
        return Settings()

    else:
        return Settings(
            IDP_URL="https://test.deployment/keycloak/realms/flame",
            API_ROOT_PATH="",
            PODORC_SERVICE_URL="http://localhost:8000",
            RESULTS_SERVICE_URL="http://localhost:8005",
            KONG_ADMIN_SERVICE_URL="http://localhost:8001",
            KONG_PROXY_SERVICE_URL="http://localhost:8002",
            HUB_AUTH_SERVICE_URL="https://auth.privateaim.dev",
            HUB_SERVICE_URL="https://core.privateaim.dev",
            HUB_ROBOT_USER="096434d8-1e26-4594-9883-64ca1d55e129",  # fake uuid
            HUB_ROBOT_SECRET="foobar",
            API_CLIENT_ID="hub-adapter-test",
            API_CLIENT_SECRET="notASecret",
            HTTP_PROXY="http://squid.proxy:3128",
            HTTPS_PROXY="http://squid.proxy:3128",
            NODE_SVC_OIDC_URL="https://test.deployment/keycloak/realms/flame",
        )


@pytest.fixture(scope="package")
def test_token(test_client) -> BearerAuth:
    """Get a new access token from the IDP."""
    test_user, test_pwd = os.getenv("IDP_USER"), os.getenv("IDP_PWD")
    assert test_user
    assert test_pwd

    resp = test_client.post("/token", data={"username": test_user, "password": test_pwd})
    assert resp.status_code == httpx.codes.OK
    token = resp.json()["access_token"]
    return BearerAuth(token=token)


@pytest.fixture(scope="module")
def setup_kong(test_client, test_token, test_settings):
    """Setup Kong instance with test data."""
    test_datastore = {
        "datastore": {
            "name": TEST_MOCK_PROJECT_ID,
            "protocol": "http",
            "host": "test.server",
            "port": 80,
            "path": "/fhir",
        },
        "ds_type": DS_TYPE,
    }
    test_project_link = {
        "data_store_id": f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}",
        "project_id": TEST_MOCK_PROJECT_ID,
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "ds_type": DS_TYPE,
        "protocols": ["http"],
    }

    try:
        ds_resp = test_client.post("/kong/datastore", auth=test_token, json=test_datastore)
        assert ds_resp.status_code == httpx.codes.CREATED

        route_resp = test_client.post("/kong/project", auth=test_token, json=test_project_link)
        assert route_resp.status_code == httpx.codes.CREATED

        yield

    finally:
        test_client.delete(f"/kong/datastore/{TEST_MOCK_PROJECT_ID}-{DS_TYPE}", auth=test_token)


@pytest.fixture(scope="module")
def setup_po(test_client, test_token):
    """Setup pod orchestrator instance with test data."""
    test_pod = {
        "analysis_id": TEST_MOCK_ANALYSIS_ID,
        "project_id": TEST_MOCK_PROJECT_ID,
    }

    r = test_client.post("/po", auth=test_token, json=test_pod)
    assert r.status_code == httpx.codes.OK
    time.sleep(2)  # Need time for k8s

    yield

    test_client.delete(f"/po/{TEST_MOCK_ANALYSIS_ID}/delete", auth=test_token)
