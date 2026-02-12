"""Test the Hub eps."""

from flame_hub.models import Analysis, AnalysisBucket, AnalysisNode, Node, Project, ProjectNode, RegistryProject

from hub_adapter.models.hub import AnalysisImageUrl, DetailedAnalysis, NodeTypeResponse
from hub_adapter.routers.hub import format_query_params, hub_router

EXPECTED_HUB_ROUTE_CONFIG = {
    "list_all_projects": {"path": "/projects", "methods": {"GET"}, "status_code": 200, "response_model": list[Project]},
    "list_specific_project": {
        "path": "/projects/{project_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": Project,
    },
    "list_project_proposals": {
        "path": "/project-nodes",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": list[ProjectNode],
    },
    "list_project_proposal": {
        "path": "/project-nodes/{project_node_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": ProjectNode,
    },
    "accept_reject_project_proposal": {
        "path": "/project-nodes/{project_node_id}",
        "methods": {"POST"},
        "status_code": 200,
        "response_model": ProjectNode,
    },
    "list_analysis_nodes": {
        "path": "/analysis-nodes",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": list[AnalysisNode],
    },
    "list_specific_analysis_node": {
        "path": "/analysis-nodes/{analysis_node_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": AnalysisNode,
    },
    "accept_reject_analysis_node": {
        "path": "/analysis-nodes/{analysis_node_id}",
        "methods": {"POST"},
        "status_code": 200,
        "response_model": AnalysisNode,
    },
    "list_all_analyses": {
        "path": "/analyses",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": list[Analysis],
    },
    "list_specific_analysis": {
        "path": "/analyses/{analysis_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": Analysis,
    },
    "list_all_nodes": {"path": "/nodes", "methods": {"GET"}, "status_code": 200, "response_model": list[Node]},
    "list_specific_node": {"path": "/nodes/{node_id}", "methods": {"GET"}, "status_code": 200, "response_model": Node},
    "get_node_type": {"path": "/node-type", "methods": {"GET"}, "status_code": 200, "response_model": NodeTypeResponse},
    "update_specific_analysis": {
        "path": "/analyses/{analysis_id}",
        "methods": {"POST"},
        "status_code": 200,
        "response_model": DetailedAnalysis,
    },
    "get_registry_metadata_for_project": {
        "path": "/registry-projects/{registry_project_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": RegistryProject,
    },
    "get_analysis_image_url": {
        "path": "/analysis/image",
        "methods": {"POST"},
        "status_code": None,
        "response_model": AnalysisImageUrl,
    },
    "list_all_analysis_buckets": {
        "path": "/analysis-buckets",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": None,
    },
    "list_specific_analysis_buckets": {
        "path": "/analysis-buckets/{analysis_bucket_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": AnalysisBucket,
    },
    "list_all_analysis_bucket_files": {
        "path": "/analysis-bucket-files",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": None,
    },
    "list_specific_analysis_bucket_file": {
        "path": "/analysis-bucket-files/{analysis_bucket_file_id}",
        "methods": {"GET"},
        "status_code": 200,
        "response_model": None,
    },
}


class TestHub:
    """Hub endpoint configuration tests."""

    def test_route_configs(self):
        """Test end point configurations for the Hub gateway routes."""
        observed = {}
        for route in hub_router.routes:
            observed[route.name] = {
                "path": route.path,
                "methods": route.methods,
                "status_code": route.status_code,
                "response_model": route.response_model,
            }
        assert observed == EXPECTED_HUB_ROUTE_CONFIG

    def test_format_query_params(self):
        """Test endpoint formatting query params."""
        test_params = {"page": '{"limit": 2, "offset": 3}', "sort": "-id", "fields": "id,ninja"}
        expected_formatted_params = {
            "page": {"limit": 2, "offset": 3},
            "fields": ["id", "ninja"],
            "sort": {"by": "id", "order": "descending"},
        }
        assert format_query_params(test_params) == expected_formatted_params

        # Missing page
        test_2 = {"sort": "+ninja", "fields": "foo,ninja"}
        expected_formatted_params_2 = {
            "fields": ["foo", "ninja"],
            "sort": {"by": "ninja", "order": "ascending"},
        }
        assert format_query_params(test_2) == expected_formatted_params_2
