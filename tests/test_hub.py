"""Test the Hub endpoints."""
from starlette import status


class TestHub:
    """Hub EP tests. Dependent on having HUB_USERNAME and HUB_PASSWORD in ENV variables."""

    @staticmethod
    def list_all(test_client, hub_token, ep: str, valid_include: str):
        """Wrapper for checking list_all methods."""
        r = test_client.get(ep, auth=hub_token)
        assert r.status_code == status.HTTP_200_OK

        data = r.json()
        assert len(data)  # {"data" : []}

        assert isinstance(data["data"], list)

        # Try include
        r_include = test_client.get(ep, auth=hub_token, params={"include": valid_include})
        assert r_include.status_code == status.HTTP_200_OK

        # Try wrong include string
        r_include_fail = test_client.get(ep, auth=hub_token, params={"include": "foo"})
        assert r_include_fail.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @staticmethod
    def list_specific(test_client, hub_token, ep: str):
        """Wrapper for checking list_specific methods."""
        r = test_client.get(ep, auth=hub_token)
        assert r.status_code == status.HTTP_200_OK

        data = r.json()
        assert data["data"]
        sample_object = data["data"][0]
        sample_object_id = sample_object["id"]

        # Try specific project
        r_specific = test_client.get(f"{ep}/{sample_object_id}", auth=hub_token)
        assert r_specific.status_code == status.HTTP_200_OK
        specific_data = r_specific.json()

        assert specific_data  # shouldn't be empty
        assert isinstance(specific_data, dict)

    @staticmethod
    def accept_reject(test_client, hub_token, ep: str):
        """Test the accept_reject methods."""
        opposite_approval = {
            "approved": "rejected",
            "rejected": "approved",
        }
        r = test_client.get(ep, auth=hub_token)
        assert r.status_code == status.HTTP_200_OK

        data = r.json()
        assert len(data)  # {"data" : []}

        assert isinstance(data["data"], list)
        sample_object = data["data"][0]
        sample_object_id = sample_object["id"]
        sample_object_approval = sample_object["approval_status"]

        r_change = test_client.post(
            f"{ep}/{sample_object_id}",
            auth=hub_token,
            params={"approval_status": opposite_approval[sample_object_approval]},
        )
        assert r_change.status_code == status.HTTP_202_ACCEPTED
        r_change_data = r_change.json()
        assert r_change_data
        assert isinstance(r_change_data, dict)
        assert r_change_data["approval_status"] == opposite_approval[sample_object_approval]

        # change it back
        r_revert = test_client.post(
            f"{ep}/{sample_object_id}",
            auth=hub_token,
            params={"approval_status": sample_object_approval},
        )
        assert r_revert.status_code == status.HTTP_202_ACCEPTED
        r_reverted = r_revert.json()
        assert r_reverted
        assert isinstance(r_reverted, dict)
        assert r_reverted["approval_status"] == sample_object_approval

    def test_list_all_projects(self, test_client, hub_token):
        """Test the list_all_projects method."""
        self.list_all(test_client, hub_token, ep="/projects", valid_include="master_image")

    def test_list_specific_project(self, test_client, hub_token):
        """Test the list_specific_project method."""
        self.list_specific(test_client, hub_token, ep="/projects")

    def test_list_projects_and_nodes(self, test_client, hub_token):
        """Test the list_projects_and_nodes method."""
        r = test_client.get("/project-nodes", auth=hub_token)
        assert r.status_code == status.HTTP_200_OK

        project_data = r.json()
        assert len(project_data)  # {"data" : []}

        assert isinstance(project_data["data"], list)
        sample_node_id = project_data["data"][0]["node_id"]

        # Test filter by node ID
        r_node_filter = test_client.get("/project-nodes", auth=hub_token, params={"filter_node_id": sample_node_id})
        assert r_node_filter.status_code == status.HTTP_200_OK
        node_filtered = r_node_filter.json()
        assert node_filtered["data"]

        for project in node_filtered["data"]:
            assert project["node_id"] == sample_node_id

    def test_accept_reject_project_node(self, test_client, hub_token):
        """Test the accept_reject_project_node method."""
        self.accept_reject(test_client, hub_token, ep="/project-nodes")

    def test_list_analyses_of_nodes(self, test_client, hub_token):
        """Test the list_analyses_of_nodes method."""
        self.list_all(test_client, hub_token, ep="/analysis-nodes", valid_include="node")

    def test_list_specific_analysis(self, test_client, hub_token):
        """Test the list_specific_analysis method."""
        self.list_specific(test_client, hub_token, ep="/analysis-nodes")

    def test_accept_reject_analysis_node(self, test_client, hub_token):
        """Test the accept_reject_analysis_node method."""
        self.accept_reject(test_client, hub_token, ep="/analysis-nodes")
