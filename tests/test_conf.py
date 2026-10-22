"""Unit tests for hub_adapter.conf Settings models."""

import uuid

import pytest
from pydantic import ValidationError

from hub_adapter.conf import AutostartSettings, Settings, UserSettings

PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
OTHER_PROJECT_ID = "16cdb4d5-a4ee-47c4-822f-c0bfd4271ce2"


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


class TestAutostartSettings:
    """Tests for project-specific autostart policy in AutostartSettings."""

    def test_defaults(self):
        """Autostart and per-project autostart are disabled by default."""
        settings = AutostartSettings()
        assert settings.enabled is False
        assert settings.default_project_autostart_policy is False
        assert settings.projects == {}

    def test_project_ids_normalized_to_canonical_uuid_string(self):
        """Uppercase and UUID-object keys are stored as lowercase hyphenated strings."""
        settings = AutostartSettings(projects={PROJECT_ID.upper(): True, uuid.UUID(OTHER_PROJECT_ID): False})
        assert settings.projects == {PROJECT_ID: True, OTHER_PROJECT_ID: False}

    def test_projects_none_becomes_empty_dict(self):
        """A null projects value is coerced to an empty mapping."""
        assert AutostartSettings(projects=None).projects == {}

    def test_invalid_project_id_rejected(self):
        """Non-UUID project keys fail validation."""
        with pytest.raises(ValidationError):
            AutostartSettings(projects={"not-a-uuid": True})

    def test_unknown_field_rejected(self):
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            AutostartSettings(project_policy=True)

    @pytest.mark.parametrize("default_policy", [True, False])
    def test_project_allowed_falls_back_to_default(self, default_policy):
        """Projects without an explicit entry use the default policy."""
        settings = AutostartSettings(default_project_autostart_policy=default_policy, projects={PROJECT_ID: True})
        assert settings.project_allowed(OTHER_PROJECT_ID) is default_policy

    @pytest.mark.parametrize("default_policy", [True, False])
    def test_project_allowed_explicit_entry_overrides_default(self, default_policy):
        """An explicit per-project entry takes precedence over the default policy."""
        settings = AutostartSettings(
            default_project_autostart_policy=default_policy,
            projects={PROJECT_ID: not default_policy},
        )
        assert settings.project_allowed(PROJECT_ID) is (not default_policy)

    def test_projects_survive_json_round_trip(self):
        """Project policies serialize to JSON and load back unchanged."""
        settings = UserSettings(autostart=AutostartSettings(projects={PROJECT_ID: True}))
        restored = UserSettings.model_validate_json(settings.model_dump_json())
        assert restored.autostart.projects == {PROJECT_ID: True}
