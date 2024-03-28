"""Test the pod orchestrator eps."""
import time

from starlette import status

from tests.constants import TEST_ANALYSIS
from tests.pseudo_auth import fakeauth


class TestPodOrc:
    """Pod orchestration tests."""

    def test_get_po_status(self, test_client, setup_po):
        """Test the get_analysis_status method."""
        r = test_client.get(f"/po/{TEST_ANALYSIS}/status", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        resp = r.json()
        assert "status" in resp
        pod_statuses = resp["status"]
        for pod_name, pod_status in pod_statuses.items():
            assert pod_name.startswith(TEST_ANALYSIS)
            assert pod_status == "running"

    def test_get_po_logs(self, test_client, setup_po):
        """Test the get_analysis_logs method."""
        r = test_client.get(f"/po/{TEST_ANALYSIS}/logs", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        resp = r.json()
        assert "logs" in resp
        pod_logs = resp["logs"]
        for pod_name, pod_log in pod_logs.items():
            assert pod_name.startswith(TEST_ANALYSIS)
            assert isinstance(pod_log, list)

    def test_get_po_pods(self, test_client, setup_po):
        """Test the get_analysis_pods method."""
        r = test_client.get(f"/po/{TEST_ANALYSIS}/pods", auth=fakeauth)
        assert r.status_code == status.HTTP_200_OK

        resp = r.json()
        assert "pods" in resp
        pods = resp["pods"]
        assert isinstance(pods, list)
        assert len(pods) == 1

    def test_create_stop_delete_pod(self, test_client):
        """Test the create_analysis, stop_analysis, and delete_analysis methods."""
        analysis_test = "podorcanalysistest"  # Must be all lower case for podorc unittests
        test_deploy = {
            "analysis_id": analysis_test,
            "project_id": "someproject",
        }

        # Create pod
        create_r = test_client.post("/po", auth=fakeauth, json=test_deploy)
        assert create_r.status_code == status.HTTP_200_OK

        pod_creation_status = create_r.json()
        assert pod_creation_status == {"status": "running"}

        time.sleep(2)

        # Stop pod
        stop_r = test_client.put(f"/po/{analysis_test}/stop", auth=fakeauth)
        assert stop_r.status_code == status.HTTP_200_OK

        pod_stop_resp = stop_r.json()
        assert "status" in pod_stop_resp
        pod_stop_statuses = pod_stop_resp["status"]
        for pod_name, pod_status in pod_stop_statuses.items():
            assert pod_name.startswith(analysis_test)
            assert pod_status == "stopped"

        time.sleep(2)

        # Delete pod
        delete_r = test_client.delete(f"/po/{analysis_test}/delete", auth=fakeauth)
        assert delete_r.status_code == status.HTTP_200_OK

        pod_delete_resp = delete_r.json()
        assert "status" in pod_delete_resp
        pod_delete_statuses = pod_delete_resp["status"]
        for pod_name, pod_status in pod_delete_statuses.items():
            assert pod_name.startswith(analysis_test)
            assert pod_status == "stopped"
