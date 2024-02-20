"""Test FastAPI app instance."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient
from gateway.server import app
from tests.pseudo_auth import get_oid_test_jwk


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
