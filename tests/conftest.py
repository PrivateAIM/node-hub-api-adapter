"""Test FastAPI app instance."""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from starlette import status

from gateway.conf import gateway_settings
from gateway.server import app
from tests.constants import TEST_DS, TEST_PROJECT, TEST_ANALYSIS
from tests.pseudo_auth import get_oid_test_jwk, BearerAuth, fakeauth


@pytest.fixture(scope="package")
def test_client():
    """Test API client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="package", autouse=True)
def setup_jwks_endpoint():
    """Create an endpoint by which to test the valid JWKS."""
    jwks = get_oid_test_jwk()

    class JWKSHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(str(jwks).encode("utf-8"))

    httpd = HTTPServer(("localhost", 18554), JWKSHandler)

    t = threading.Thread(target=httpd.serve_forever)
    t.start()

    yield

    httpd.shutdown()


@pytest.fixture(scope="module")
def hub_token() -> BearerAuth:
    """Create an endpoint by which to test the valid JWKS."""
    load_dotenv(dotenv_path="../env/.env.dev")
    # TODO: replace with robot account
    hub_username, hub_password = os.getenv("HUB_USERNAME"), os.getenv("HUB_PASSWORD")
    hub_auth_api = gateway_settings.HUB_AUTH_SERVICE_URL
    hub_token_ep = hub_auth_api + "/token"

    resp = requests.post(hub_token_ep, data={"username": hub_username, "password": hub_password})
    assert resp.ok

    token = resp.json()["access_token"]
    assert token

    return BearerAuth(token)


@pytest.fixture(scope="module")
def setup_kong(test_client):
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
        "methods": [
            "GET",
            "POST",
            "PUT",
            "DELETE"
        ],
        "ds_type": "fhir",
        "protocols": ["http"],
    }

    test_client.post("/datastore", auth=fakeauth, json=test_datastore)
    test_client.post("/datastore/project", auth=fakeauth, json=test_project_link)

    yield

    test_client.put(f"/disconnect/{TEST_PROJECT}", auth=fakeauth)
    test_client.delete(f"/datastore/{TEST_DS}", auth=fakeauth)


@pytest.fixture(scope="module")
def setup_po(test_client):
    """Setup pod orchestrator instance with test data."""
    test_pod = {
        "analysis_id": TEST_ANALYSIS,
        "project_id": TEST_PROJECT,
    }

    r = test_client.post("/po", auth=fakeauth, json=test_pod)
    assert r.status_code == status.HTTP_200_OK
    time.sleep(2)  # Need time for k8s

    yield

    test_client.delete(f"/po/{TEST_ANALYSIS}/delete", auth=fakeauth)
