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

The following environment variables need to be set for operation:

```bash
IDP_URL="https://my.user.keycloak.com/realms/flame"  # Path to IDP for user auth (if keycloak then include realm) 
API_ROOT_PATH=""  # Change the root path where the API is served from, useful for k8s ingress
PODORC_SERVICE_URL="http://localhost:18080"  # URL to Pod Orchestration service
RESULTS_SERVICE_URL="http://localhost:8000"  # URL to the Results service
KONG_ADMIN_SERVICE_URL="http://localhost:8000"  # URL to the Kong gateway service
HUB_AUTH_SERVICE_URL="https://auth.privateaim.dev"  # URL for auth EPs for the Hub
HUB_SERVICE_URL="https://core.privateaim.dev"  # URL for project/analysis EPs for the Hub
HUB_ROBOT_USER="hubusername"  # Need to get credentials from myself or hub team
HUB_ROBOT_SECRET="hubpassword"  # These will be removed later once users are registered in both node and hub IDP
API_CLIENT_ID="hub-adapter"  # Client name of this API as defined in keycloak
API_CLIENT_SECRET="someSecret"  # Client secret of this API as defined in keycloak
#NODE_SVC_OIDC_URL="https://data-center.node.com/keycloak/realms/flame"  # The internal IDP used by other Node microsvcs
OVERRIDE_JWKS=""  # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
HA_HTTP_PROXY=""  # Forward proxy address for HTTP requests
HA_HTTPS_PROXY=""  # Forward proxy address for HTTPS requests
STRICT_INTERNAL="false"  # If deployed in a containerized setting e.g. docker or k8s, then set this to True to ensure internal communication
```
