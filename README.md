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

## Discussion

* Create developer/restricted user in k8s for API calls
*
