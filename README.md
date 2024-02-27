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
users must authorize themselves in keycloak to run protected endpoints:

* Test User: `flameuser`
* Test pwd: `flamepwd`

## Environment

The following environment variables need to be set for operation:

```bash
IDP_URL="http://localhost:8080"  # e.g. Keycloak
IDP_REALM="flame"  # If different realm used in keycloak else defaults to master
K8S_API_KEY="foo"  # An API key for k8s is only needed if a sidecar proxy container isn't used
PODORC_SERVICE_URL="http://localhost:18080"  # URL to Pod Orchestration service
RESULTS_SERVICE_URL="http://localhost:8000"  # URL to the Results service
HUB_SERVICE_URL="http://localhost:8888"  # URL to the Hub API
UI_CLIENT_ID=test-client  # Client name of UI as defined in keycloak
UI_CLIENT_SECRET=lhjYYgU5e1GQtfrs3YsTiESGpzqE8YSb  # Client secret for UI
```
