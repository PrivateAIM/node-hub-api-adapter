"""String constants for tests."""

import uuid
from datetime import datetime, timezone

from dateutil.tz import UTC
from flame_hub.models import Node

from hub_adapter.schemas.conf import OIDCConfiguration
from hub_adapter.schemas.podorc import PodStatus

DS_TYPE = "fhir"

TEST_URL = "https://api.example.com"
TEST_OIDC = OIDCConfiguration(
    issuer=TEST_URL,
    authorization_endpoint=TEST_URL,
    token_endpoint=f"{TEST_URL}/protocol/openid-connect/token",
    jwks_uri=TEST_URL,
    userinfo_endpoint=TEST_URL,
)
TEST_SVC_URL = "https://service.example"
TEST_SVC_OIDC = OIDCConfiguration(
    issuer=TEST_SVC_URL,
    authorization_endpoint=TEST_SVC_URL,
    token_endpoint=f"{TEST_SVC_URL}/protocol/openid-connect/token",
    jwks_uri=TEST_SVC_URL,
    userinfo_endpoint=TEST_SVC_URL,
)

TEST_MOCK_ANALYSIS_ID = "1c9cb547-4afc-4398-bcb6-954bc61a1bb1"
TEST_MOCK_PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
TEST_MOCK_NODE_ID = "9c521144-364d-4cdc-8ec4-cb62a537f10c"

TEST_MOCK_NODE_CLIENT_ID = "096434d8-1e26-4594-9883-64ca1d55e129"

TEST_KONG_SERVICE_ID = "c2bfa0be-e8ff-4c82-be50-734432dd4579"  # fake uuid

TEST_MOCK_NODE = Node(
    id=uuid.UUID(TEST_MOCK_NODE_ID),
    public_key="fakeKey",
    online=True,
    registry=None,
    registry_project_id=uuid.UUID(TEST_MOCK_PROJECT_ID),
    client_id=uuid.UUID(TEST_MOCK_NODE_CLIENT_ID),
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
    external_name=None,
    hidden=False,
    name=TEST_MOCK_NODE_ID,
    realm_id=None,
    registry_id=None,
    type="default",
    robot_id=None,  # deprecated
)

MOCK_ANALYSIS = {
    "name": None,
    "display_name": "mock-analysis",
    "project_id": TEST_MOCK_PROJECT_ID,
    "build_status": "executed",
    "created_at": 1756790836,
    "updated_at": 1756790836,
    "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "configuration_locked": True,
    "nodes": 2,
    "nodes_approved": 2,
    "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "description": None,
    "master_image_id": None,
    "registry_id": None,
    "configuration_entrypoint_valid": False,
    "configuration_image_valid": True,
    "configuration_node_aggregator_valid": True,
    "configuration_node_default_valid": True,
    "configuration_nodes_valid": False,
    "build_nodes_valid": True,
    "build_progress": None,
    "build_hash": None,
    "build_os": None,
    "build_size": None,
    "distribution_status": "executed",
    "distribution_progress": None,
    "execution_status": None,
    "execution_progress": 0,
    "client_id": "9cdbb3eb-ea20-45e5-9b5b-ba18b760e4db",
}

MOCK_PROJECT = {
    "id": TEST_MOCK_PROJECT_ID,
    "name": "mock-project",
    "display_name": "mock-project",
    "description": None,
    "master_image_id": None,
    "analyses": 1,
    "nodes": MOCK_ANALYSIS["nodes"],
    "created_at": MOCK_ANALYSIS["created_at"],
    "updated_at": MOCK_ANALYSIS["updated_at"],
    "realm_id": MOCK_ANALYSIS["realm_id"],
    "user_id": MOCK_ANALYSIS["user_id"],
    "robot_id": None,
}

MOCK_PROJECT_NODE = {
    "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "created_at": MOCK_ANALYSIS["created_at"],
    "updated_at": MOCK_ANALYSIS["updated_at"],
    "project_realm_id": MOCK_ANALYSIS["realm_id"],
    "node_realm_id": MOCK_ANALYSIS["realm_id"],
    "comment": None,
    "project_id": TEST_MOCK_PROJECT_ID,
    "node_id": TEST_MOCK_NODE_ID,
    "approval_status": "approved",
}

MOCK_ANALYSIS_NODE = {
    "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "created_at": 1756790836,
    "updated_at": 1756790836,
    "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
    "comment": None,
    "artifact_tag": None,
    "artifact_digest": None,
    "analysis_id": TEST_MOCK_ANALYSIS_ID,
    "node_id": TEST_MOCK_NODE_ID,
    "approval_status": "approved",
    "execution_status": None,
    "execution_progress": 0,
    "analysis": MOCK_ANALYSIS,
}

ANALYSIS_NODES_RESP = [
    {
        # Shouldn't start because executed
        **MOCK_ANALYSIS_NODE,
        "analysis": {**MOCK_ANALYSIS, "name": "autostart-test"},
        "execution_status": "executed",
    },
    {
        # Ready to start
        **MOCK_ANALYSIS_NODE,
        "analysis": {**MOCK_ANALYSIS, "created_at": datetime.now(timezone.utc)},
        "created_at": datetime.now(timezone.utc),
    },
    {
        # Should fail since too old
        **MOCK_ANALYSIS_NODE,
    },
    {
        # Shouldn't start since still building
        **MOCK_ANALYSIS_NODE,
        "analysis": {**MOCK_ANALYSIS, "build_status": PodStatus.STARTING},
    },
    {
        # Shouldn't start because rejected
        **MOCK_ANALYSIS_NODE,
        "approval_status": "rejected",
    },
    {
        # Shouldn't start because project ID isn't in kong
        **MOCK_ANALYSIS_NODE,
        "analysis": {**MOCK_ANALYSIS, "project_id": "16cdb4d5-a4ee-47c4-822f-c0bfd4271ce2"},
    },
]

KONG_GET_ROUTE_RESPONSE = {
    "data": [
        {
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "response_buffering": True,
            "headers": None,
            "paths": [f"/{TEST_MOCK_PROJECT_ID}/{TEST_KONG_SERVICE_ID}"],
            "hosts": None,
            "path_handling": "v0",
            "https_redirect_status_code": 426,
            "service": {"id": "5156f9e8-229d-4752-90a5-e1991b9263ee"},
            "id": "e4a421d3-7e74-4af7-85a2-a3b509c455f8",
            "sources": None,
            "strip_path": True,
            "preserve_host": False,
            "snis": None,
            "destinations": None,
            "protocols": ["http"],
            "tags": [f"project:{TEST_MOCK_PROJECT_ID}", f"datastore:{TEST_KONG_SERVICE_ID}", "type:fhir"],
            "name": None,
            "methods": ["GET"],
            "request_buffering": True,
            "regex_priority": 0,
        }
    ],
    "next": None,
}

KONG_ANALYSIS_SUCCESS_RESP = {
    "consumer": {
        "created_at": 1756891221,
        "custom_id": f"analysis-{TEST_MOCK_ANALYSIS_ID}",
        "id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c",
        "tags": [f"project:{TEST_MOCK_PROJECT_ID}", f"analysis:{TEST_MOCK_ANALYSIS_ID}"],
        "username": f"analysis-{TEST_MOCK_ANALYSIS_ID}",
    },
    "keyauth": {
        "consumer": {"id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c"},
        "created_at": 1756891221,
        "id": "9c3f6705-f06d-4164-b828-62714f2ddce7",
        "key": "bdgTKiDd2J1XNzgrK8K6QQYtVjNx9Nyo",
        "tags": [f"project:{TEST_MOCK_PROJECT_ID}"],
    },
    "acl": {
        "consumer": {"id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c"},
        "created_at": 1756891221,
        "id": "3075a2ca-8760-4db7-a81b-6a963a03e0aa",
        "group": TEST_MOCK_PROJECT_ID,
        "tags": [f"project:{TEST_MOCK_PROJECT_ID}"],
    },
}

TEST_JWKS_RESPONSE = {
    "keys": [
        {
            "key_ops": ["verify"],
            "ext": "true",
            "kty": "RSA",
            "n": "0KXvS0gNKz9GO1S-R3FwPCP45IbGr3xYpkNa-_QcvT1bWykB_pCHGRNHAXvAvDrkFqwEYrNJVq20RD_pafxXy12axj_oSg1XJprUmsGEgmU9JEo1PIWyo49uJHiiolMaNwsSZS-v0L0RDWlXtTh5YNgN0kt2awjd4oz8836CH2c94qXSbtfmcBkh2AY4EzZfEwbWfJPS6FcWUr9hM_pBXB69anb35mp-UN_ndYP_nnFbieA1W3IFB3DK6siNZEZTiZxiBP1-VR3Qpzahr_qWxVv6KfWQ5ixMfu5mQpGFjjy_jzckxtr-f3zO0MIKCe_cdTj77KsIaeGtrVdWP_UN-Q",
            "e": "AQAB",
            "alg": "RS256",
            "kid": "3d08b96f-ceb8-43e2-912b-10df205ae4d4",
        }
    ]
}

TEST_OIDC_RESPONSE = {
    "authorization_endpoint": TEST_URL,
    "issuer": TEST_URL,
    "jwks_uri": TEST_URL,
    "token_endpoint": f"{TEST_URL}/protocol/openid-connect/token",
    "userinfo_endpoint": TEST_URL,
}

TEST_OIDC_SVC_RESPONSE = {
    "authorization_endpoint": TEST_SVC_URL,
    "issuer": TEST_SVC_URL,
    "jwks_uri": TEST_SVC_URL,
    "token_endpoint": f"{TEST_SVC_URL}/protocol/openid-connect/token",
    "userinfo_endpoint": TEST_SVC_URL,
}

TEST_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMn0.KMUFsIDTnFmyG3nMiGM6H9FNFUROf3wh7SmqJp-QV30"

# RBAC
ADMIN_ROLE = "admin"
STEWARD_ROLE = "steward"
RESEARCHER_ROLE = "researcher"

TEST_ADMIN_DECRYPTED_JWT = {"resource_access": {"node-ui": {"roles": [ADMIN_ROLE]}}}
TEST_STEWARD_DECRYPTED_JWT = {"resource_access": {"node-ui": {"roles": [STEWARD_ROLE]}}}
TEST_RESEARCHER_DECRYPTED_JWT = {"resource_access": {"node-ui": {"roles": [RESEARCHER_ROLE]}}}

FAKE_USER = {
    "acr": "1",
    "allowed-origins": ["/*"],
    "aud": "account",
    "azp": "hub-adapter-test",
    "email": "foo@gmail.com",
    "email_verified": True,
    "exp": 1761749936,
    "family_name": "Test",
    "given_name": "Adapter",
    "iat": 1761742736,
    "iss": f"{TEST_URL}",
    "name": "Adapter Test",
    "preferred_username": "testuser",
    "realm_access": {"roles": ["offline_access", "default-roles-flame", "uma_authorization"]},
    "resource_access": {"account": {"roles": ["manage-account", "manage-account-links", "view-profile"]}},
    "scope": "openid email profile",
    "sid": "7135cb16-fbcd-4c5d-8c1f-0f6b5764c718",
    "sub": "e4fe638c-c94e-4094-8c2f-793ff69def0b",
    "typ": "Bearer",
}

# --- New tag-based Kong scheme (multi-datastore) ---
TEST_KONG_DS_NAME = "test-fhir-store"
KONG_DS_SERVICE_DATA = {
    "connect_timeout": 6000,
    "enabled": True,
    "host": "node-datastore-blaze",
    "id": TEST_KONG_SERVICE_ID,
    "name": TEST_KONG_DS_NAME,
    "path": f"/{DS_TYPE}",
    "port": 80,
    "protocol": "http",
    "read_timeout": 6000,
    "retries": 5,
    "write_timeout": 6000,
    "tags": [f"type:{DS_TYPE}"],
}
KONG_DS_CREATE_REQUEST = {
    "datastore": {
        "name": TEST_KONG_DS_NAME,
        "host": "node-datastore-blaze",
        "port": 80,
        "protocol": "http",
        "path": f"/{DS_TYPE}",
    },
    "ds_type": DS_TYPE,
}
KONG_LINK_ROUTE_DATA = {
    "id": "0f8a44eb-2647-4fd8-8b45-b0f92e5477a5",
    "name": None,
    "paths": [f"/{TEST_MOCK_PROJECT_ID}/{TEST_KONG_SERVICE_ID}"],
    "protocols": ["http"],
    "methods": ["GET"],
    "https_redirect_status_code": 426,
    "preserve_host": False,
    "request_buffering": True,
    "response_buffering": True,
    "tags": [
        f"project:{TEST_MOCK_PROJECT_ID}",
        f"datastore:{TEST_KONG_SERVICE_ID}",
        f"type:{DS_TYPE}",
    ],
    "service": {"id": TEST_KONG_SERVICE_ID},
}

KONG_ANALYSIS_CONSUMER_DATA = {
    "id": "d0c1e6a1-33cf-4b43-a3d1-8e2b1c7a9f10",
    "username": f"analysis-{TEST_MOCK_ANALYSIS_ID}",
    "custom_id": f"analysis-{TEST_MOCK_ANALYSIS_ID}",
    "tags": [f"project:{TEST_MOCK_PROJECT_ID}", f"analysis:{TEST_MOCK_ANALYSIS_ID}"],
}

TEST_MOCK_EVENTS = [
    {
        "id": 75,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:28:55.712858",
        "body": "http://localhost:5000/events?limit=50&start_date=2026-01-20T11%3A27%3A07",
        "attributes": {
            "path": "/events",
            "user": None,
            "client": ["127.0.0.1", 40144],
            "method": "GET",
            "service": "events",
            "status_code": 200,
        },
    },
    {
        "id": 74,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:28:41.045536",
        "body": "http://localhost:5000/events?limit=50&start_date=2026-01-20T05%3A53%3A00%2B05%3A00",
        "attributes": {
            "path": "/events",
            "user": None,
            "client": ["127.0.0.1", 51462],
            "method": "GET",
            "service": "events",
            "status_code": 200,
        },
    },
    {
        "id": 73,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:27:11.612876",
        "body": "http://localhost:5000/events?limit=50",
        "attributes": {
            "path": "/events",
            "user": None,
            "client": ["127.0.0.1", 55068],
            "method": "GET",
            "service": "events",
            "status_code": 200,
        },
    },
    {
        "id": 72,
        "event_name": "api.ui.access",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:27:07.770171",
        "body": "http://localhost:5000/openapi.json",
        "attributes": {
            "path": "/openapi.json",
            "user": None,
            "client": ["127.0.0.1", 55068],
            "method": "GET",
            "service": "hub_adapter",
            "status_code": 200,
        },
    },
    {
        "id": 71,
        "event_name": "api.ui.access",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:27:07.617104",
        "body": "http://localhost:5000/docs",
        "attributes": {
            "path": "/docs",
            "user": None,
            "client": ["127.0.0.1", 55068],
            "method": "GET",
            "service": "hub_adapter",
            "status_code": 200,
        },
    },
    {
        "id": 70,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:22:51.485849",
        "body": "http://localhost:5000/events?limit=50&filter_username=flameuser",
        "attributes": {
            "path": "/events",
            "user": None,
            "client": ["127.0.0.1", 57762],
            "method": "GET",
            "service": "events",
            "status_code": 200,
        },
    },
    {
        "id": 69,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:22:43.836330",
        "body": "http://localhost:5000/events?limit=50&filter_username=fart",
        "attributes": {
            "path": "/events",
            "user": None,
            "client": ["127.0.0.1", 58516],
            "method": "GET",
            "service": "events",
            "status_code": 200,
        },
    },
]
