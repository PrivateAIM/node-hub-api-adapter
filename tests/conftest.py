"""Test FastAPI app instance."""
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from gateway.conf import gateway_settings
from gateway.server import app
from tests.pseudo_auth import get_oid_test_jwk, BearerAuth


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
    HUB_USERNAME, HUB_PASSWORD = os.getenv("HUB_USERNAME"), os.getenv("HUB_PASSWORD")
    HUB_AUTH_API = gateway_settings.HUB_AUTH_SERVICE_URL
    HUB_TOKEN_EP = HUB_AUTH_API + "/token"

    resp = requests.post(HUB_TOKEN_EP, data={"username": HUB_USERNAME, "password": HUB_PASSWORD})
    assert resp.ok

    token = resp.json()["access_token"]
    assert token

    return BearerAuth(token)
