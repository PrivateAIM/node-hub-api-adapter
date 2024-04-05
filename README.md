# Node Hub API Adapter

## Description

Service that proxies certain resources from the Hub Core API (projects, analysis, nodes) and queries other node
services (Results, Pod Orchestration, Data) for the Node UI. Needs to check for authorization, e.g. analysis should only
be allowed to see other nodes participating in the current analysis.

## Testing

This module assumes there is a running Keycloak instance available. One can be quickly created with an appropriate test
realm and user using the [docker-compose file](./docker/docker-compose.yml) which will populate the keycloak instance
using the [instance export file](docker/test-realm.json).

The API can be found at http://127.0.0.1:8081 with a GUI for the API available at http://127.0.0.1:8081/docs. Here,
users must authorize themselves with the deployed keycloak instance
(from the [docker-compose file](./docker/docker-compose.yml)) to run protected endpoints:

* Test User: `flameuser`
* Test pwd: `flamepwd`

## Environment

The following environment variables need to be set for operation:

```bash
IDP_URL="http://localhost:8080"  # e.g. Keycloak
IDP_REALM="flame"  # If different realm used in keycloak else defaults to master
PODORC_SERVICE_URL="http://localhost:18080"  # URL to Pod Orchestration service
RESULTS_SERVICE_URL="http://localhost:8000"  # URL to the Results service
HUB_AUTH_SERVICE_URL="https://auth.privateaim.net"  # URL for auth EPs for the Hub
HUB_SERVICE_URL="https://api.privateaim.net"  # URL for project/analysis EPs for the Hub
HUB_USERNAME="hubusername"  # Need to get credentials from myself or hub team
HUB_PASSWORD="hubpassword"  # These will be removed later once users are registered in both node and hub IDP
API_CLIENT_ID="api-client"  # Client name of this API as defined in keycloak
```
