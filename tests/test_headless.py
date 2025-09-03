"""Collection of unit tests for testing headless operation."""

from pathlib import Path

import pytest
import respx
from dotenv import load_dotenv

from hub_adapter.headless import register_analysis
from hub_adapter.routers.kong import create_and_connect_analysis_to_project
from tests.constants import TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID
from tests.mock_responses import mock_kong_analysis_creation_response

foo = create_and_connect_analysis_to_project


class TestHeadless:
    """Headless methods."""

    @staticmethod
    @respx.mock
    @pytest.mark.asyncio
    async def test_register_analysis():
        """Test registering an analysis with kong."""
        import os
        test_env_file = Path("./.env.test")
        load_dotenv(test_env_file, override=True)
        os.getenv("KONG_ADMIN_SERVICE_URL")
        respx.get("http://kong.test/routes").mock(return_value=mock_kong_analysis_creation_response)
        respx.post("http://kong.test/consumers").mock(return_value=mock_kong_analysis_creation_response)
        resp = await register_analysis(TEST_MOCK_ANALYSIS_ID, TEST_MOCK_PROJECT_ID)
        foo = 2
