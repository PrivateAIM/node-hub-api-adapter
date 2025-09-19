"""Test FastAPI app instance."""

import os
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.constants import DS_TYPE, TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID
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
    test_user, test_pwd = os.getenv("IDP_USER"), os.getenv("IDP_PWD")
    assert test_user
    assert test_pwd

    resp = test_client.post("/token", data={"username": test_user, "password": test_pwd})
    assert resp.status_code == httpx.codes.OK
    token = resp.json()["access_token"]
    return BearerAuth(token=token)


@pytest.fixture(scope="module")
def setup_kong(test_client, test_token):
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
