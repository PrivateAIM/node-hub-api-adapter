"""Test FastAPI app instance."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.constants import TEST_ANALYSIS, TEST_DS, TEST_PROJECT
from tests.pseudo_auth import BearerAuth


@pytest.fixture(scope="session")
def test_client():
    """Test API client."""
    from hub_adapter.server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="package")
def test_token(test_client) -> BearerAuth:
    """Get a new access token from the IDP."""
    test_user, test_pwd = "flameuser", "flamepwd"

    resp = test_client.post("/token", data={"username": test_user, "password": test_pwd})
    assert resp.status_code == httpx.codes.OK
    token = resp.json()["access_token"]
    return BearerAuth(token=token)


@pytest.fixture(scope="module")
def setup_kong(test_client, test_token):
    """Setup Kong instance with test data."""
    test_datastore = {
        "name": TEST_DS,
        "protocol": "http",
        "host": "server.fire.ly",
        "port": 80,
        "path": "/mydefinedpath",
    }
    test_project_link = {
        "data_store_id": TEST_DS,
        "project_id": TEST_PROJECT,
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "ds_type": "fhir",
        "protocols": ["http"],
    }

    test_client.post("/kong/datastore", auth=test_token, json=test_datastore)
    test_client.post("/kong/datastore/project", auth=test_token, json=test_project_link)

    yield

    test_client.put(f"/kong/disconnect/{TEST_PROJECT}", auth=test_token)
    test_client.delete(f"/kong/datastore/{TEST_DS}", auth=test_token)


@pytest.fixture(scope="module")
def setup_po(test_client, test_token):
    """Setup pod orchestrator instance with test data."""
    test_pod = {
        "analysis_id": TEST_ANALYSIS,
        "project_id": TEST_PROJECT,
    }

    r = test_client.post("/po", auth=test_token, json=test_pod)
    assert r.status_code == httpx.codes.OK
    time.sleep(2)  # Need time for k8s

    yield

    test_client.delete(f"/po/{TEST_ANALYSIS}/delete", auth=test_token)
