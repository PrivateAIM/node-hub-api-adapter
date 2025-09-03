"""String constants for tests."""

TEST_DS = "unitTestDataStore"
TEST_PROJECT = "unittestproject"  # Must be all lower case for podorc unittests
TEST_ANALYSIS = "unittestanalysis"  # Must be all lower case for podorc unittests

TEST_MOCK_ANALYSIS_ID = "1c9cb547-4afc-4398-bcb6-954bc61a1bb1"
TEST_MOCK_PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
TEST_MOCK_NODE_ID = "9c521144-364d-4cdc-8ec4-cb62a537f10c"

ANALYSIS_NODES_RESP = [
    {
        "analysis_id": "4d59c590-2eda-41b4-bda1-6b7ac6dda08f",
        "node_id": TEST_MOCK_NODE_ID,
        "id": "0ca712c6-6205-460b-b5f0-8dab1e10b38a",
        "approval_status": "approved",
        "run_status": "finished",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "created_at": "2025-09-02T09:41:18.301000Z",
        "updated_at": "2025-09-02T10:22:47Z",
        "analysis": {
            "description": None,
            "name": "headless-test",
            "project_id": TEST_MOCK_PROJECT_ID,
            "master_image_id": "0c7f5fce-0d95-49cc-b9af-b3be76dc6dbe",
            "registry_id": "e388588d-75b7-426c-8f51-cdd939aee665",
            "image_command_arguments": [],
            "id": "4d59c590-2eda-41b4-bda1-6b7ac6dda08f",
            "configuration_locked": True,
            "nodes": 2,
            "build_status": "finished",
            "run_status": None,
            "created_at": "2025-09-02T09:41:15.036000Z",
            "updated_at": "2025-09-02T09:56:57Z",
            "registry": None,
            "realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
            "user_id": "d9c50964-77d1-4619-a18d-26b1250d634f",
            "project": None,
            "master_image": None,
        },
        "node": {
            "external_name": "bruce-default-1",
            "hidden": False,
            "name": "bruce1",
            "realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
            "registry_id": "e388588d-75b7-426c-8f51-cdd939aee665",
            "type": "default",
            "id": TEST_MOCK_NODE_ID,
            "public_key": "2d2d2d2d2d424547494e205055424c4943204b45592d2d2d2d2d0a4d466b77457759484b6f5a497a6a3043415159494b6f5a497a6a30444151634451674145787a31397a6c6263393838703237756c466c66776650454a61334d4c67325743514d6d69314a63486d723262716b36584461655265304462524433414d6667344b42506d56744451723162696a6a6e454157442f4d773d3d0a2d2d2d2d2d454e44205055424c4943204b45592d2d2d2d2d",
            "online": False,
            "registry": None,
            "registry_project_id": "6f63f32b-ac73-4d26-b5c0-597fbff037c2",
            "registry_project": None,
            "robot_id": "f793cfce-b7a7-4ba0-be28-846b36bc2410",
            "created_at": "2025-08-27T12:14:14.009000Z",
            "updated_at": "2025-08-28T09:08:45Z",
        },
        "analysis_realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
        "node_realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
    },
    {
        "analysis_id": TEST_MOCK_ANALYSIS_ID,
        "node_id": TEST_MOCK_NODE_ID,
        "id": "0ebf5044-d368-4ebc-9a21-1578cc2f40a6",
        "approval_status": "approved",
        "run_status": "failed",
        "comment": None,
        "artifact_tag": None,
        "artifact_digest": None,
        "created_at": "2025-09-02T08:06:21.023000Z",
        "updated_at": "2025-09-02T09:19:35Z",
        "analysis": {
            "description": None,
            "name": "image-test",
            "project_id": TEST_MOCK_PROJECT_ID,
            "master_image_id": "b58ba169-2038-4269-a312-5cb5791d3138",
            "registry_id": "e388588d-75b7-426c-8f51-cdd939aee665",
            "image_command_arguments": [],
            "id": TEST_MOCK_ANALYSIS_ID,
            "configuration_locked": True,
            "nodes": 2,
            "build_status": "finished",
            "run_status": None,
            "created_at": "2025-09-02T08:06:17.939000Z",
            "updated_at": "2025-09-02T09:18:06Z",
            "registry": None,
            "realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
            "user_id": "d9c50964-77d1-4619-a18d-26b1250d634f",
            "project": None,
            "master_image": None,
        },
        "node": {
            "external_name": "bruce-default-1",
            "hidden": False,
            "name": "bruce1",
            "realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
            "registry_id": "e388588d-75b7-426c-8f51-cdd939aee665",
            "type": "default",
            "id": TEST_MOCK_NODE_ID,
            "public_key": "2d2d2d2d2d424547494e205055424c4943204b45592d2d2d2d2d0a4d466b77457759484b6f5a497a6a3043415159494b6f5a497a6a30444151634451674145787a31397a6c6263393838703237756c466c66776650454a61334d4c67325743514d6d69314a63486d723262716b36584461655265304462524433414d6667344b42506d56744451723162696a6a6e454157442f4d773d3d0a2d2d2d2d2d454e44205055424c4943204b45592d2d2d2d2d",
            "online": False,
            "registry": None,
            "registry_project_id": "6f63f32b-ac73-4d26-b5c0-597fbff037c2",
            "registry_project": None,
            "robot_id": "f793cfce-b7a7-4ba0-be28-846b36bc2410",
            "created_at": "2025-08-27T12:14:14.009000Z",
            "updated_at": "2025-08-28T09:08:45Z",
        },
        "analysis_realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
        "node_realm_id": "0d87f3f1-b39c-4ff8-8c3e-917de86cd041",
    },
]

KONG_GET_SERVICES_RESPONSE = {
    "data": [
        {
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "path": "/fhir",
            "connect_timeout": 6000,
            "read_timeout": 6000,
            "host": "node-datastore-blaze",
            "tls_verify": None,
            "enabled": True,
            "tls_verify_depth": None,
            "id": "5156f9e8-229d-4752-90a5-e1991b9263ee",
            "retries": 5,
            "write_timeout": 6000,
            "protocol": "http",
            "tags": [TEST_MOCK_PROJECT_ID, "9cbefefe-2420-4b8e-8ac1-f48148a9fd40-fhir"],
            "name": "9cbefefe-2420-4b8e-8ac1-f48148a9fd40-fhir",
            "ca_certificates": None,
            "port": 80,
            "client_certificate": None,
        }
    ],
    "next": None,
}

KONG_GET_ROUTE_RESPONSE = {
    "data": [
        {
            "created_at": 1756790836,
            "updated_at": 1756790836,
            "response_buffering": True,
            "headers": None,
            "paths": ["/9cbefefe-2420-4b8e-8ac1-f48148a9fd40-fhir/fhir"],
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
            "name": "9cbefefe-2420-4b8e-8ac1-f48148a9fd40-fhir",
            "methods": ["GET"],
            "request_buffering": True,
            "regex_priority": 0,
        }
    ],
    "next": None,
}

KONG_GET_CONSUMER_RESPONSE = {
    "data": [
        {
            "created_at": 1756891221,
            "updated_at": 1756891221,
            "id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c",
            "tags": [TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID],
            "username": "1c9cb547-4afc-4398-bcb6-954bc61a1bb1-flame",
            "custom_id": "1c9cb547-4afc-4398-bcb6-954bc61a1bb1-flame",
        },
    ],
    "next": None,
}

KONG_ANALYSIS_SUCCESS_RESP = {
    "consumer": {
        "created_at": 1756891221,
        "custom_id": "1c9cb547-4afc-4398-bcb6-954bc61a1bb1-flame",
        "id": "6544a9a6-19af-4bfe-a6c2-a88c7d0dc12c",
        "tags": [TEST_MOCK_PROJECT_ID, TEST_MOCK_ANALYSIS_ID],
        "username": "1c9cb547-4afc-4398-bcb6-954bc61a1bb1-flame",
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
