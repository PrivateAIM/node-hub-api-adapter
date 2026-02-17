# Node Hub API Adapter

## Description

Service that proxies certain resources from the Hub Core API (projects, analysis, nodes) and queries other node
services (Storage, Pod Orchestration, Kong) for the Node UI. Needs to check for authorization, e.g. analysis should only
be allowed to see other nodes participating in the current analysis.

## Testing

This module assumes there is a running Keycloak instance available. One can be quickly created with an appropriate test
realm and user using the [docker-compose file](./docker/docker-compose.yml) which will populate the keycloak instance
using the [instance export file](docker/test-realm.json).

Once started, the API can be found at http://127.0.0.1:5000 with a GUI for the API available
at http://127.0.0.1:5000/docs. Here,
users must authorize themselves with the deployed keycloak instance
(from the [docker-compose file](./docker/docker-compose.yml)) to run protected endpoints:

* Test User: `flameuser`
* Test pwd: `flamepwd`

## Environment

The following environment variables need to be set for operation, find a detailed description of each in the table
further down:

```bash
IDP_URL="https://my.user.keycloak.com/realms/flame"  # URL to the IDP used for user authentication. If the IDP is Keycloak, be sure to include the realm
API_ROOT_PATH=""  # Subpath to serve the API on    
PODORC_SERVICE_URL="http://localhost:18080"  # URL to Pod Orchestration service
STORAGE_SERVICE_URL="http://localhost:8000"  # URL to the Storage service
KONG_ADMIN_SERVICE_URL="http://localhost:8000"  # URL to the Kong admin service
KONG_PROXY_SERVICE_URL="http://localhost:8000"  # URL to the Kong proxy service
HUB_AUTH_SERVICE_URL="https://auth.privateaim.dev"  # URL for auth EPs for the Hub
HUB_SERVICE_URL="https://core.privateaim.dev"  # URL for project/analysis EPs for the Hub
HUB_NODE_CLIENT_ID=""  # Client UUID for a registered node
HUB_NODE_CLIENT_SECRET=""  # Client secret for a registered node 
API_CLIENT_ID="hub-adapter"  # IDP Client ID for this hub-adapter service, this must be the client ID specified 
API_CLIENT_SECRET=""  # IDP Client Secret for this hub-adapter service
#NODE_SVC_OIDC_URL="https://data-center.node.com/keycloak/realms/flame"  # The internal IDP used by other Node microsvcs
OVERRIDE_JWKS=""  # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
HTTP_PROXY=""  # Forward proxy address for HTTP requests
HTTPS_PROXY=""  # Forward proxy address for HTTPS requests
AUTOSTART=false  # Whether the API should also operate in "autostart" mode where it'll start analyses automatically
AUTOSTART_INTERVAL=60  # How often (in seconds) the server should check for new analyses
EXTRA_CA_CERTS=""  # Path to a concatenated file containing all of the additional SSL certificates needed for communication
ROLE_CLAIM_NAME="" # Period separated list of keys leading to the role value for a user e.g. "resource_access.node-ui.role"
ADMIN_ROLE="admin"  # Role name for users who have full access and control as defined in the IDP
STEWARD_ROLE="steward"  # Role name for users who can only modify data stores as defined in the IDP
RESEARCHER_ROLE="researcher"  # Role name for users who can only modify analyses as defined in the IDP
```

| EnvVar                  | Description                                                                                                       |           Default           | Required |
|-------------------------|-------------------------------------------------------------------------------------------------------------------|:---------------------------:|:--------:|
| IDP_URL                 | URL to the IDP used for user authentication. If the IDP is Keycloak, be sure to include the realm                 |                             |    x     |
| API_ROOT_PATH           | Subpath to serve the API on                                                                                       |                             |          |
| PODORC_SERVICE_URL      | URL to the pod orchestrator service                                                                               |                             |    x     |
| STORAGE_SERVICE_URL     | URL to the Storage service                                                                                        |                             |    x     |
| KONG_ADMIN_SERVICE_URL  | URL to the Kong admin service                                                                                     |                             |    x     |
| KONG_PROXY_SERVICE_URL  | URL to the Kong proxy service                                                                                     |                             |    x     |
| HUB_SERVICE_URL         | URL to the core Hub service                                                                                       | https://core.privateaim.dev |    x     |
| HUB_AUTH_SERVICE_URL    | URL to the auth Hub service                                                                                       | https://auth.privateaim.dev |    x     |
| HUB_NODE_CLIENT_ID      | Client UUID for a registered node                                                                                 |                             |    x     |
| HUB_NODE_CLIENT_SECRET  | Client secret for a registered node                                                                               |                             |    x     |
| API_CLIENT_ID           | IDP Client ID for this hub-adapter service, should be the same (internal) IDP used by the other node services     |         hub-adapter         |    x     |
| API_CLIENT_SECRET       | IDP Client Secret for this hub-adapter service, should be the same (internal) IDP used by the other node services |                             |    x     |
| NODE_SVC_OIDC_URL       | The (internal) IDP URL used by the other Node services when different from the IDP used for user authentication.  |                             |          |
| OVERRIDE_JWKS           | JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)                          |                             |          |
| HTTP_PROXY              | Forward proxy address for HTTP requests                                                                           |                             |          |
| HTTPS_PROXY             | Forward proxy address for HTTPS requests                                                                          |                             |          |
| AUTOSTART               | Whether the API should also operate in "autostart" mode where it'll start analyses automatically                  |            false            |          |
| AUTOSTART_INTERVAL      | How often (in seconds) the server should check for new analyses                                                   |             60              |          |
| EXTRA_CA_CERTS          | Path to a concatenated file containing all of the additional SSL certificates needed for communication            |                             |          |
| ROLE_CLAIM_NAME         | Period separated list of keys leading to the role value for a user e.g. "resource_access.node-ui.roles"           |                             |          |
| ADMIN_ROLE              | Role name for users who have full access and control as defined in the IDP                                        |            admin            |          |
| STEWARD_ROLE            | Role name for users who can only modify data stores as defined in the IDP                                         |                             |          |
| RESEARCHER_ROLE         | Role name for users who can only modify analyses as defined in the IDP                                            |                             |          |
| POSTGRES_EVENT_USER     | Username for connecting to the postgres database which logs events                                                |                             |          |
| POSTGRES_EVENT_PASSWORD | Password for connecting to the postgres database which logs events                                                |                             |          |
| POSTGRES_EVENT_DB       | Name of the postgres database which logs events                                                                   |                             |          |
| POSTGRES_EVENT_HOST     | Hostname of the postgres database which logs events                                                               |          localhost          |          |
| POSTGRES_EVENT_PORT     | Port of the postgres database which logs events                                                                   |            5432             |          |

## RBAC

The hub adapter supports the use of role-based access control (RBAC) by incorporating specific roles into the JWT. One
can specify up to 3 different roles:

* `ADMIN_ROLE`: Role name for users who have full access and control as defined in the IDP
* `STEWARD_ROLE`: Role name for users who can only modify data stores as defined in the IDP
* `RESEARCHER_ROLE`: Role name for users who can only modify analyses as defined in the IDP

Because this is meant to be IDP-agnostic, the `ROLE_CLAIM_NAME` must be set to indicate where the role names should be
found within the JWT provided by the IDP.
This value should be a period "." separated series of keys. For example, if the returned token is formatted as such:

```json
{
  "sub": "1234567890",
  "name": "John Doe",
  "iat": 1516239022,
  "resource_access": {
    "node-ui": {
      "roles": [
        "steward"
      ]
    }
  },
  "scope": "openid email profile",
  "email_verified": true
}
```

then the `ROLE_CLAIM_NAME` should be set to `"resource_access.node-ui.roles"` (can be a list or single string value).
If the `ROLE_CLAIM_NAME` is not set, then RBAC is disabled.

Additionally, if the `STEWARD_ROLE` is not set during deployment, it is assumed all users are permitted to modify the
data stores, likewise for `RESEARCHER_ROLE` and modifying analyses. Otherwise, the hub adapter will parse the roles
found using `ROLE_CLAIM_NAME` and check whether either the `ADMIN_ROLE` or `STEWARD_ROLE`/`RESEARCHER_ROLE` is present
in the role list.

## Autostart

The `AUTOSTART` feature of the hub adapter can be enabled to set the software to monitor the Hub for new analyses, and
once detected, it will automatically send the initiate command to the pod orchestrator. For an analysis to qualify as
being ready to start, it must meet the following criteria:

* It was created in the last 24 hours
* Its `approval_status` as reported by the Hub is set to "approved"
* The `build_status` is set to "executed"
* If the node on which the hub adapter is deployed is a "default" node, then a data store is available for the analysis
* The analysis was never previously started on the node

To enable this feature, set `AUTOSTART=true`, and how often (in seconds) the hub adapter will probe the Hub for new
analyses can be set with `AUTOSTART_INTERVAL`.
