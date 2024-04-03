# Testing

Running the unit tests for this API gateway requires that all the dependent microservices be up and running as well
as properly configured in the environment variables as indicated in the [project's README](../README.md). These
tests assume you have imported the [test-realm](../docker/test-realm.json) into the keycloak instance, or at least
added `flameuser` and `flamepwd` as a test user (which should be deleted immediately afterward).
