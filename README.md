# Node Hub API Adapter

## Description

Service that proxies certain resources from the Hub Core API (projects, analysis, nodes) and queries other node
services (Results, Pod Orchestration, Kong) for the Node UI. Needs to check for authorization, e.g. analysis should only
be allowed to see other nodes participating in the current analysis.

## Testing

This module assumes there is a running Keycloak instance available. One can be quickly created with an appropriate test
realm and user using the [docker-compose file](./docker/docker-compose.yml) which will populate the keycloak instance
using the [instance export file](docker/test-realm.json).

Once started, the API can be found at http://127.0.0.1:8081 with a GUI for the API available
at http://127.0.0.1:8081/docs. Here,
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
RESULTS_SERVICE_URL="http://localhost:8000"  # URL to the Results service
KONG_ADMIN_SERVICE_URL="http://localhost:8000"  # URL to the Kong gateway service
HUB_AUTH_SERVICE_URL="https://auth.privateaim.dev"  # URL for auth EPs for the Hub
HUB_SERVICE_URL="https://core.privateaim.dev"  # URL for project/analysis EPs for the Hub
HUB_ROBOT_USER=""  # Robot UUID for a registered node
HUB_ROBOT_SECRET=""  # Robot secret for a registered node
API_CLIENT_ID="hub-adapter"  # IDP Client ID for this hub-adapter service, this must be the client ID specified 
API_CLIENT_SECRET=""  # IDP Client Secret for this hub-adapter service
#NODE_SVC_OIDC_URL="https://data-center.node.com/keycloak/realms/flame"  # The internal IDP used by other Node microsvcs
OVERRIDE_JWKS=""  # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
HTTP_PROXY=""  # Forward proxy address for HTTP requests
HTTPS_PROXY=""  # Forward proxy address for HTTPS requests
HEADLESS=false  # Whether the API should also operate in "headless" mode where it'll start analyses automatically
HEADLESS_INTERVAL=60  # How often (in seconds) the server should check for new analyses
```

| EnvVar                 | Description                                                                                                       |           Default           | Required |
|------------------------|-------------------------------------------------------------------------------------------------------------------|:---------------------------:|:--------:|
| IDP_URL                | URL to the IDP used for user authentication. If the IDP is Keycloak, be sure to include the realm                 |                             |    x     |
| API_ROOT_PATH          | Subpath to serve the API on                                                                                       |                             |          |
| PODORC_SERVICE_URL     | URL to the pod orchestrator service                                                                               |                             |    x     |
| RESULTS_SERVICE_URL    | URL to the Results service                                                                                        |                             |    x     |
| KONG_ADMIN_SERVICE_URL | URL to the Kong gateway service                                                                                   |                             |    x     |
| HUB_SERVICE_URL        | URL to the core Hub service                                                                                       | https://core.privateaim.dev |    x     |
| HUB_AUTH_SERVICE_URL   | URL to the auth Hub service                                                                                       | https://auth.privateaim.dev |    x     |
| HUB_ROBOT_USER         | Robot UUID for a registered node                                                                                  |                             |    x     |
| HUB_ROBOT_SECRET       | Robot secret for a registered node                                                                                |                             |    x     |
| API_CLIENT_ID          | IDP Client ID for this hub-adapter service, should be the same (internal) IDP used by the other node services     |         hub-adapter         |    x     |
| API_CLIENT_SECRET      | IDP Client Secret for this hub-adapter service, should be the same (internal) IDP used by the other node services |                             |    x     |
| NODE_SVC_OIDC_URL      | The (internal) IDP URL used by the other Node services when different from the IDP used for user authentication.  |                             |          |
| OVERRIDE_JWKS          | JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)                          |                             |          |
| HTTP_PROXY             | Forward proxy address for HTTP requests                                                                           |                             |          |
| HTTPS_PROXY            | Forward proxy address for HTTPS requests                                                                          |                             |          |
| HEADLESS               | Whether the API should also operate in "headless" mode where it'll start analyses automatically                   |            false            |          |
| HEADLESS_INTERVAL      | How often (in seconds) the server should check for new analyses                                                   |             60              |          |