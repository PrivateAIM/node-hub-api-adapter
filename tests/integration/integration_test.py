import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.client import HTTPException
from typing import Optional

import httpx

from hub_adapter.auth import _get_internal_token
from hub_adapter.conf import Settings
from hub_adapter.dependencies import (
    get_core_client,
    get_flame_hub_auth_flow,
    get_settings,
    get_ssl_context,
)
from hub_adapter.oidc import get_svc_oidc_config


@dataclass
class IntegrationTestSettings:
    """Settings for integration tests."""

    api_base_url: str = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
    project_id: str = os.getenv("PROJECT_ID")
    analysis_id: str = os.getenv("ANALYSIS_ID")
    analysis_startup_timeout: int = int(os.getenv("ANALYSIS_STARTUP_TIMEOUT", "30"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "60"))


logger = logging.getLogger(__name__)


class IntegrationTestRunner:
    """Manages integration test execution with proper resource cleanup."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.integration_settings = IntegrationTestSettings()
        self.ssl_ctx = get_ssl_context(settings)
        self.hub_robot = get_flame_hub_auth_flow(self.ssl_ctx, settings)
        self.core_client = get_core_client(self.hub_robot, self.ssl_ctx, settings)
        self.token: dict | None = None
        self.http_client: httpx.AsyncClient | None = None
        self._resources_created = {
            "datastore": False,
            "analysis": False,
        }

    async def __aenter__(self):
        """Initialize async resources."""
        self.http_client = httpx.AsyncClient(timeout=self.integration_settings.request_timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources on exit."""
        if self.http_client:
            await self.http_client.aclose()

    async def get_auth_token(self) -> dict:
        """Get a JWT using client credentials from the bundled Keycloak instance."""
        if self.token:
            return self.token

        oidc_config = get_svc_oidc_config()
        self.token = await _get_internal_token(oidc_config, self.settings)
        logger.info("Successfully obtained authentication token")
        return self.token

    async def test_hub_connectivity(self):
        """Test: Verify communication with Hub."""
        logger.info("Testing Hub connectivity...")
        analyses = self.core_client.get_analyses()
        assert analyses is not None, "Failed to fetch analyses from Hub"
        logger.info("✓ Hub communication verified")

    async def test_create_datastore(self):
        """Test: Create a new data store via Kong."""
        logger.info("Testing datastore creation...")
        payload = {
            "project_id": self.integration_settings.project_id,
            "protocols": ["http"],
            "datastore": {
                "connect_timeout": 6000,
                "enabled": True,
                "host": "node-datastore-blaze",
                "name": self.integration_settings.project_id,
                "path": "/fhir",
                "port": 80,
                "protocol": "http",
                "read_timeout": 6000,
                "retries": 5,
                "tags": [],
                "write_timeout": 6000,
            },
            "ds_type": "fhir",
        }

        url = f"{self.integration_settings.api_base_url}/kong/initialize"
        resp = await self.http_client.post(url, json=payload, headers=self.token)
        resp.raise_for_status()
        self._resources_created["datastore"] = True
        logger.info("✓ Datastore created successfully")

    async def test_start_analysis(self):
        """Test: Start an analysis via PodOrc."""
        logger.info("Testing analysis startup...")
        payload = {
            "analysis_id": self.integration_settings.analysis_id,
            "project_id": self.integration_settings.project_id,
        }

        url = f"{self.integration_settings.api_base_url}/analysis/initialize"
        resp = await self.http_client.post(url, data=payload, headers=self.token)
        resp.raise_for_status()
        self._resources_created["analysis"] = True
        logger.info("✓ Analysis started successfully")

        # Wait for analysis to be ready
        logger.info(f"Waiting {self.integration_settings.analysis_startup_timeout}s for analysis to start...")
        await asyncio.sleep(self.integration_settings.analysis_startup_timeout)

    async def test_fetch_logs(self):
        """Test: Fetch logs for the running analysis."""
        logger.info("Testing log retrieval...")
        url = f"{self.integration_settings.api_base_url}/po/history/{self.integration_settings.analysis_id}"
        resp = await self.http_client.get(url, headers=self.token)
        resp.raise_for_status()
        assert resp.content, "No logs returned"
        logger.info("✓ Logs retrieved successfully")

    async def test_stop_analysis(self):
        """Test: Stop the running analysis."""
        logger.info("Testing analysis stop...")
        url = f"{self.integration_settings.api_base_url}/po/stop/{self.integration_settings.analysis_id}"
        resp = await self.http_client.put(url, headers=self.token)
        resp.raise_for_status()
        logger.info("✓ Analysis stopped successfully")

    async def cleanup_analysis(self):
        """Clean up: Terminate the analysis and delete consumer."""
        if not self._resources_created["analysis"]:
            return

        try:
            logger.info("Cleaning up analysis resources...")
            url = f"{self.integration_settings.api_base_url}/analysis/terminate/{self.integration_settings.analysis_id}"
            resp = await self.http_client.delete(url, headers=self.token)
            resp.raise_for_status()
            self._resources_created["analysis"] = False
            logger.info("✓ Analysis resources cleaned up")
        except Exception as e:
            logger.error(f"Failed to clean up analysis: {e}")

    async def cleanup_datastore(self):
        """Clean up: Delete the test datastore."""
        if not self._resources_created["datastore"]:
            return

        try:
            logger.info("Cleaning up datastore...")
            datastore_name = f"{self.integration_settings.project_id}-fhir"
            url = f"{self.integration_settings.api_base_url}/kong/datastore/{datastore_name}"
            resp = await self.http_client.delete(url, headers=self.token)
            resp.raise_for_status()
            self._resources_created["datastore"] = False
            logger.info("✓ Datastore cleaned up")

        except HTTPException as e:
            logger.error(f"Failed to clean up datastore: {e}")

    async def run_all_tests(self):
        """Execute all integration tests with proper cleanup."""
        try:
            # Authentication
            await self.get_auth_token()
            logger.info("✓ Keycloak authentication verified")

            # Run tests in sequence
            await self.test_hub_connectivity()
            await self.test_create_datastore()
            await self.test_start_analysis()
            await self.test_fetch_logs()
            await self.test_stop_analysis()

            logger.info("\n" + "=" * 50)
            logger.info("All integration tests passed successfully! ✓")
            logger.info("=" * 50)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during test: {e.response.status_code} - {e.response.text}")
            raise

        except HTTPException as e:
            logger.error(f"Test failed with error: {e}")
            raise

        finally:
            # Always clean up resources
            await self.cleanup_analysis()
            await self.cleanup_datastore()


async def main():
    """Main entry point for integration tests."""
    settings: Settings = get_settings()

    async with IntegrationTestRunner(settings) as runner:
        await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
