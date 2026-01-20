"""String constants for tests."""

import uuid
from datetime import datetime, timezone

from flame_hub._core_client import Node
from kong_admin_client import ACL, KeyAuth

from hub_adapter.models.conf import OIDCConfiguration

DS_TYPE = "fhir"
NODE_TYPE = "default"

TEST_URL = "https://api.example.com"
TEST_OIDC = OIDCConfiguration(
    issuer=TEST_URL,
    authorization_endpoint=TEST_URL,
    token_endpoint=TEST_URL,
    jwks_uri=TEST_URL,
    userinfo_endpoint=TEST_URL,
)
TEST_SVC_URL = "https://service.example"
TEST_SVC_OIDC = OIDCConfiguration(
    issuer=TEST_SVC_URL,
    authorization_endpoint=TEST_SVC_URL,
    token_endpoint=TEST_SVC_URL,
    jwks_uri=TEST_SVC_URL,
    userinfo_endpoint=TEST_SVC_URL,
)


TEST_MOCK_ANALYSIS_ID = "1c9cb547-4afc-4398-bcb6-954bc61a1bb1"
TEST_MOCK_PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
TEST_MOCK_NODE_ID = "9c521144-364d-4cdc-8ec4-cb62a537f10c"

TEST_MOCK_ROBOT_USER = "096434d8-1e26-4594-9883-64ca1d55e129"

TEST_MOCK_NODE = Node(
    id=uuid.UUID(TEST_MOCK_NODE_ID),
    public_key="fakeKey",
    online=True,
    registry=None,
    registry_project_id=uuid.UUID(TEST_MOCK_PROJECT_ID),
    robot_id=uuid.UUID(TEST_MOCK_ROBOT_USER),
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
    external_name=None,
    hidden=False,
    name=TEST_MOCK_NODE_ID,
    realm_id=None,
    registry_id=None,
    type=NODE_TYPE,
)

ANALYSIS_NODES_RESP = [
    {
        "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "created_at": 1756790836,
        "updated_at": 1756790836,
        "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "analysis_id": "1452cf2d-e9d5-4a2d-822a-fc0a3b8cd2fd",
        "node_id": TEST_MOCK_NODE_ID,
        "approval_status": "approved",
        "run_status": "finished",  # Shouldn't start because finished
        "analysis": {
            "name": "autostart-test",
            "project_id": TEST_MOCK_PROJECT_ID,
            "build_status": "finished",
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
        },
    },
    {  # Ready to start
        "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "created_at": datetime.now(timezone.utc),
        "updated_at": 1756790836,
        "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "analysis_id": TEST_MOCK_ANALYSIS_ID,
        "node_id": TEST_MOCK_NODE_ID,
        "approval_status": "approved",
        "run_status": None,
        "analysis": {
            "project_id": TEST_MOCK_PROJECT_ID,
            "build_status": "finished",
            "created_at": datetime.now(timezone.utc),
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
            "name": None,
        },
    },
    {
        "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "created_at": 1756790836,  # Should fail since too old
        "updated_at": 1756790836,
        "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "analysis_id": TEST_MOCK_ANALYSIS_ID,
        "node_id": TEST_MOCK_NODE_ID,
        "approval_status": "approved",
        "run_status": None,
        "analysis": {
            "project_id": TEST_MOCK_PROJECT_ID,
            "build_status": "finished",
            "created_at": 1756790836,  # Should fail since too old
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
            "name": None,
        },
    },
    {
        "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "created_at": 1756790836,
        "updated_at": 1756790836,
        "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "analysis_id": "e4b9d64a-6619-4b31-9897-a85f37c83087",
        "node_id": TEST_MOCK_NODE_ID,
        "approval_status": "approved",
        "run_status": None,
        "analysis": {
            "project_id": TEST_MOCK_PROJECT_ID,
            "build_status": "starting",  # Shouldn't start because build isn't finished
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
            "name": None,
        },
    },
    {
        "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "created_at": 1756790836,
        "updated_at": 1756790836,
        "analysis_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "node_realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "analysis_id": "a727fecb-bb28-4d9a-9a6e-6410a99de34a",
        "node_id": TEST_MOCK_NODE_ID,
        "approval_status": "rejected",  # Shouldn't start because rejected
        "run_status": None,
        "analysis": {
            "project_id": TEST_MOCK_PROJECT_ID,
            "build_status": "finished",
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
            "name": None,
        },
    },
    {
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
        "run_status": None,
        "analysis": {
            "project_id": "16cdb4d5-a4ee-47c4-822f-c0bfd4271ce2",  # Shouldn't start because project ID isn't in kong
            "build_status": "finished",
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "configuration_locked": True,
            "nodes": 2,
            "realm_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "user_id": "ac776c7f-c39d-4484-9a37-fa7109017192",
            "description": None,
            "master_image_id": None,
            "registry_id": None,
            "run_status": None,
            "name": None,
        },
    },
]

KONG_GET_ROUTE_RESPONSE = {
    "data": [
        {
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "response_buffering": True,
            "headers": None,
            "paths": [f"/{TEST_MOCK_PROJECT_ID}-fhir/fhir"],
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
            "tags": [TEST_MOCK_PROJECT_ID, "fhir"],
            "name": f"{TEST_MOCK_PROJECT_ID}-fhir",
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
        "custom_id": f"{TEST_MOCK_ANALYSIS_ID}-flame",
        "id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c",
        "tags": [TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID],
        "username": f"{TEST_MOCK_ANALYSIS_ID}-flame",
    },
    "keyauth": {
        "consumer": {"id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c"},
        "created_at": 1756891221,
        "id": "9c3f6705-f06d-4164-b828-62714f2ddce7",
        "key": "bdgTKiDd2J1XNzgrK8K6QQYtVjNx9Nyo",
        "tags": [TEST_MOCK_PROJECT_ID],
    },
    "acl": {
        "consumer": {"id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c"},
        "created_at": 1756891221,
        "id": "3075a2ca-8760-4db7-a81b-6a963a03e0aa",
        "group": TEST_MOCK_PROJECT_ID,
        "tags": [TEST_MOCK_PROJECT_ID],
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
    "token_endpoint": TEST_URL,
    "userinfo_endpoint": TEST_URL,
}

TEST_OIDC_SVC_RESPONSE = {
    "authorization_endpoint": TEST_SVC_URL,
    "issuer": TEST_SVC_URL,
    "jwks_uri": TEST_SVC_URL,
    "token_endpoint": TEST_SVC_URL,
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

TEST_KONG_CREATE_SERVICE_REQUEST = {
    "datastore": {
        "name": TEST_MOCK_PROJECT_ID,
        "protocol": "http",
        "host": "test.server",
        "port": 80,
        "path": f"/{DS_TYPE}",
    },
    "ds_type": DS_TYPE,
}

TEST_KONG_SERVICE_ID = "c2bfa0be-e8ff-4c82-be50-734432dd4579"  # fake uuid
TEST_KONG_SERVICE_DATA = {
    "ca_certificates": None,
    "client_certificate": None,
    "connect_timeout": 6000,
    "created_at": 1761803230,
    "enabled": True,
    "host": "node-datastore-blaze",
    "id": TEST_KONG_SERVICE_ID,
    "name": f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}",
    "path": f"/{DS_TYPE}",
    "port": 80,
    "protocol": "http",
    "read_timeout": 6000,
    "retries": 5,
    "tags": [f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}", f"{TEST_MOCK_PROJECT_ID}"],
    "tls_verify": None,
    "tls_verify_depth": None,
    "updated_at": 1761803230,
    "url": None,
    "write_timeout": 6000,
}

TEST_KONG_SERVICE_RESPONSE = {
    "data": [TEST_KONG_SERVICE_DATA],
    "offset": None,
}

TEST_KONG_CREATE_ROUTE_REQUEST = {
    "data_store_id": f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}",
    "project_id": TEST_MOCK_PROJECT_ID,
    "methods": ["GET", "POST", "PUT", "DELETE"],
    "ds_type": DS_TYPE,
    "protocols": ["http"],
}

TEST_KONG_ROUTE_DATA = {
    "created_at": 0,
    "destinations": [{"default": "string"}],
    "headers": {},
    "hosts": ["string"],
    "https_redirect_status_code": 426,
    "id": TEST_MOCK_PROJECT_ID,
    "methods": ["string"],
    "name": f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}",
    "path_handling": "v0",
    "paths": [f"/{DS_TYPE}"],
    "preserve_host": False,
    "protocols": ["GET"],
    "regex_priority": 0,
    "request_buffering": True,
    "response_buffering": True,
    "service": {"id": TEST_KONG_SERVICE_ID},
    "snis": ["string"],
    "sources": [{"default": "string"}],
    "strip_path": True,
    "tags": [f"{TEST_MOCK_PROJECT_ID}-{DS_TYPE}", f"{TEST_MOCK_PROJECT_ID}"],
    "updated_at": 0,
}

TEST_KONG_ROUTE_RESPONSE = {
    "route": TEST_KONG_ROUTE_DATA,
    "keyauth": KeyAuth().__dict__,
    "acl": ACL().__dict__,
}

TEST_KONG_CONSUMER_DATA = {
    "consumer": {
        "created_at": 0,
        "custom_id": f"{TEST_MOCK_ANALYSIS_ID}-flame",
        "id": "string",
        "username": f"{TEST_MOCK_ANALYSIS_ID}-flame",
        "tags": [TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID],
    },
    "keyauth": KeyAuth().__dict__,
    "acl": ACL().__dict__,
}


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

TEST_MOCK_EVENTS = [
    {
        "id": 75,
        "event_name": "events.get.success",
        "service_name": "hub_adapter",
        "timestamp": "2026-01-20T11:28:55.712858",
        "body": "http://localhost:8081/events?limit=50&start_date=2026-01-20T11%3A27%3A07",
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
        "body": "http://localhost:8081/events?limit=50&start_date=2026-01-20T05%3A53%3A00%2B05%3A00",
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
        "body": "http://localhost:8081/events?limit=50",
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
        "body": "http://localhost:8081/openapi.json",
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
        "body": "http://localhost:8081/docs",
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
        "body": "http://localhost:8081/events?limit=50&filter_username=flameuser",
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
        "body": "http://localhost:8081/events?limit=50&filter_username=fart",
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
