"""Collection of unit tests for testing the dependency methods."""

from pathlib import Path
from unittest.mock import patch

from hub_adapter.conf import Settings
from hub_adapter.dependencies import get_ssl_context


class TestDeps:
    """Collection of unit tests for testing the dependency methods."""

    @patch("hub_adapter.dependencies.get_settings")
    def test_get_ssl_context(self, mock_settings):
        """Test the get_ssl_context method."""
        # Clear the cache to avoid conflicts
        get_ssl_context.cache_clear()
        mock_settings.return_value = Settings()

        cert_file_path = Path(__file__).resolve().parent.joinpath("assets/test.ssl.pem")
        non_existent_cert = Path("./foo.pem")

        assert cert_file_path.exists()
        assert not non_existent_cert.exists()

        # Missing file
        no_context = get_ssl_context(mock_settings)
        assert len(no_context._ctx.get_ca_certs()) == 0

        # Valid file
        get_ssl_context.cache_clear()
        mock_settings.EXTRA_CA_CERTS = str(cert_file_path)
        context = get_ssl_context(mock_settings)
        assert context is not None
        assert len(context._ctx.get_ca_certs()) == 2  # 2 certificates in test file
