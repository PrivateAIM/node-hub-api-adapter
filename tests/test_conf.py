"""Unit tests for hub_adapter.conf Settings models."""

from hub_adapter.conf import Settings


class TestSettingsValidator:
    """Tests for the Settings model_validator."""

    def test_node_svc_oidc_url_defaults_to_idp_url_when_not_set(self):
        """When node_svc_oidc_url is not provided, it is set to idp_url by the validator."""
        settings = Settings(_env_file=None, idp_url="https://idp.example.com")
        assert settings.node_svc_oidc_url == "https://idp.example.com"

    def test_node_svc_oidc_url_preserved_when_explicitly_set(self):
        """When node_svc_oidc_url is explicitly provided, it is not overwritten."""
        settings = Settings(
            _env_file=None,
            idp_url="https://idp.example.com",
            node_svc_oidc_url="https://svc-oidc.example.com",
        )
        assert settings.node_svc_oidc_url == "https://svc-oidc.example.com"
