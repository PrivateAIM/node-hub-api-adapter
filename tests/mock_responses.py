"""Collection of mock responses to provide the unit tests."""

from httpx import Response

from tests.constants import ANALYSIS_NODES_RESP, KONG_ANALYSIS_SUCCESS_RESP, KONG_GET_ROUTE_RESPONSE

mock_analysis_nodes_response = Response(
    status_code=200,
    json=ANALYSIS_NODES_RESP,
)

mock_kong_analysis_creation_response = Response(
    status_code=201,
    json=KONG_ANALYSIS_SUCCESS_RESP,
)

mock_kong_project_list = Response(
    status_code=200,
    json=KONG_GET_ROUTE_RESPONSE,
)
