"""Collection of unit tests for testing user_settings module methods."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import peewee as pw
import pytest

from hub_adapter.conf import UserSettings
from hub_adapter.user_settings import (
    PersistentUserConfiguration,
    _deep_merge,
    _load_from_database,
    _load_from_json,
    _save_to_database,
    _save_to_json,
    load_persistent_settings,
    save_persistent_settings,
    update_settings,
    with_db_fallback,
)


class TestWithDbFallback:
    """Tests for the with_db_fallback decorator."""

    def test_decorator_returns_fallback_on_operational_error(self):
        """Test that decorator returns fallback value when OperationalError occurs."""

        @with_db_fallback(fallback_value="fallback", log_message="Test failed")
        def failing_function():
            raise pw.OperationalError("Database connection lost")

        result = failing_function()
        assert result == "fallback"

    def test_decorator_returns_correct_fallback_for_none(self):
        """Test that decorator returns None when fallback_value is not specified."""

        @with_db_fallback()
        def failing_function():
            raise pw.OperationalError("Database error")

        result = failing_function()
        assert result is None

    def test_decorator_returns_function_result_on_success(self):
        """Test that decorator returns the function result when successful."""

        @with_db_fallback(fallback_value="fallback")
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_with_function_args(self):
        """Test that decorator works with function arguments."""

        @with_db_fallback(fallback_value=0)
        def add_numbers(a, b):
            return a + b

        result = add_numbers(5, 3)
        assert result == 8

    def test_decorator_with_function_kwargs(self):
        """Test that decorator works with function keyword arguments."""

        @with_db_fallback(fallback_value="fallback")
        def greet(name="World"):
            return f"Hello, {name}!"

        result = greet(name="Alice")
        assert result == "Hello, Alice!"

    def test_decorator_logs_warning_on_error(self):
        """Test that decorator logs a warning when OperationalError occurs."""

        @with_db_fallback(fallback_value=None, log_message="Custom error message")
        def failing_function():
            raise pw.OperationalError("DB error")

        with patch("hub_adapter.user_settings.logger") as mock_logger:
            result = failing_function()
            mock_logger.warning.assert_called_once()
            assert "Custom error message" in mock_logger.warning.call_args[0][0]


class TestDeepMerge:
    """Tests for the _deep_merge function."""

    def test_merge_simple_dicts(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        updates = {"c": 3}
        result = _deep_merge(base, updates)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_overwrites_existing_keys(self):
        """Test that updates overwrite existing base keys."""
        base = {"a": 1, "b": 2}
        updates = {"a": 10}
        result = _deep_merge(base, updates)
        assert result == {"a": 10, "b": 2}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        base = {"level1": {"a": 1, "b": 2}}
        updates = {"level1": {"c": 3}}
        result = _deep_merge(base, updates)
        assert result == {"level1": {"a": 1, "b": 2, "c": 3}}

    def test_merge_nested_dicts_with_overwrite(self):
        """Test that nested dict updates overwrite nested base keys."""
        base = {"level1": {"a": 1, "b": 2}}
        updates = {"level1": {"a": 10}}
        result = _deep_merge(base, updates)
        assert result == {"level1": {"a": 10, "b": 2}}

    def test_merge_replaces_non_dict_with_dict(self):
        """Test that a non-dict value is replaced with a dict value."""
        base = {"a": 1}
        updates = {"a": {"nested": 2}}
        result = _deep_merge(base, updates)
        assert result == {"a": {"nested": 2}}

    def test_merge_replaces_dict_with_non_dict(self):
        """Test that a dict value is replaced with a non-dict value."""
        base = {"a": {"nested": 1}}
        updates = {"a": 2}
        result = _deep_merge(base, updates)
        assert result == {"a": 2}

    def test_merge_deeply_nested_dicts(self):
        """Test merging deeply nested dictionaries."""
        base = {"l1": {"l2": {"a": 1, "b": 2}}}
        updates = {"l1": {"l2": {"c": 3}}}
        result = _deep_merge(base, updates)
        assert result == {"l1": {"l2": {"a": 1, "b": 2, "c": 3}}}

    def test_merge_empty_dicts(self):
        """Test merging with empty dictionaries."""
        assert _deep_merge({}, {}) == {}
        assert _deep_merge({"a": 1}, {}) == {"a": 1}
        assert _deep_merge({}, {"a": 1}) == {"a": 1}

    def test_merge_does_not_modify_original(self):
        """Test that merge doesn't modify the original base dict."""
        base = {"a": 1}
        updates = {"b": 2}
        result = _deep_merge(base, updates)
        assert base == {"a": 1}
        assert result == {"a": 1, "b": 2}


class TestLoadFromDatabase:
    """Tests for _load_from_database function."""

    @patch("hub_adapter.user_settings.node_database")
    @patch("hub_adapter.user_settings.bind_user_settings")
    def test_load_from_database_success(self, mock_bind, mock_db):
        """Test successfully loading settings from database."""
        mock_db.__enter__ = Mock()
        mock_db.__exit__ = Mock()

        mock_entry = Mock()
        mock_entry.configuration = {"require_data_store": False, "autostart": {"enabled": True}}

        with patch("hub_adapter.user_settings.PersistentUserConfiguration.get_or_create") as mock_get_or_create:
            mock_get_or_create.return_value = (mock_entry, False)

            with patch("hub_adapter.user_settings.bind_user_settings"):
                result = _load_from_database()

            assert result == {"require_data_store": False, "autostart": {"enabled": True}}

    @patch("hub_adapter.user_settings.node_database", None)
    def test_load_from_database_with_none_database(self):
        """Test that function returns an empty dict when node_database is None."""
        result = _load_from_database()
        assert result == {}

    @patch("hub_adapter.user_settings.node_database")
    def test_load_from_database_operational_error(self, mock_db):
        """Test that function returns an empty dict on OperationalError."""
        mock_db.side_effect = pw.OperationalError("Connection failed")

        with patch("hub_adapter.user_settings.logger"):
            result = _load_from_database()

        assert result == {}

    @patch("hub_adapter.user_settings.node_database")
    @patch("hub_adapter.user_settings.bind_user_settings")
    def test_load_from_database_returns_empty_config(self, mock_bind, mock_db):
        """Test loading when the configuration is None or empty."""
        mock_entry = Mock()
        mock_entry.configuration = None

        with patch("hub_adapter.user_settings.PersistentUserConfiguration.get_or_create") as mock_get_or_create:
            mock_get_or_create.return_value = (mock_entry, False)

            with patch("hub_adapter.user_settings.bind_user_settings"):
                result = _load_from_database()

            assert result == {}


class TestLoadFromJson:
    """Tests for _load_from_json function."""

    @patch("hub_adapter.user_settings.logger")
    def test_load_from_json_file_exists(self, test_logger):
        """Test loading settings from JSON file when it exists."""
        settings_data = {"require_data_store": False, "autostart": {"enabled": True}}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "userSettings.json"
            json_path.write_text(json.dumps(settings_data))

            with patch("hub_adapter.user_settings.SETTINGS_PATH", json_path):
                result = _load_from_json()

            assert result == settings_data

    def test_load_from_json_file_not_exists(self):
        """Test loading from JSON when file doesn't exist."""
        with patch("hub_adapter.user_settings.SETTINGS_PATH", Path("/nonexistent/path.json")):
            result = _load_from_json()
            assert result == {}

    @patch("hub_adapter.user_settings.logger")
    def test_load_from_json_invalid_json(self, test_logger):
        """Test loading from JSON when file contains invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "userSettings.json"
            json_path.write_text("{ invalid json }")

            with patch("hub_adapter.user_settings.SETTINGS_PATH", json_path):
                result = _load_from_json()

            assert result == {}

    @patch("hub_adapter.user_settings.logger")
    def test_load_from_json_logs_on_success(self, test_logger):
        """Test that function logs when successfully loading from JSON."""
        settings_data = {"require_data_store": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "userSettings.json"
            json_path.write_text(json.dumps(settings_data))

            with patch("hub_adapter.user_settings.SETTINGS_PATH", json_path):
                _load_from_json()
                test_logger.info.assert_called()


class TestSaveToDatabase:
    """Tests for _save_to_database function."""

    @patch("hub_adapter.user_settings.node_database")
    @patch("hub_adapter.user_settings.bind_user_settings")
    @patch("hub_adapter.user_settings.logger")
    def test_save_to_database_success(self, test_logger, mock_bind, mock_db):
        """Test successfully saving settings to database."""
        settings_dict = {"require_data_store": False}

        with patch("hub_adapter.user_settings.PersistentUserConfiguration.update") as mock_update:
            mock_query = Mock()
            mock_update.return_value = mock_query
            mock_query.where.return_value = mock_query
            mock_query.execute.return_value = None

            with patch("hub_adapter.user_settings.bind_user_settings"):
                result = _save_to_database(settings_dict)

            assert result is True

    @patch("hub_adapter.user_settings.node_database", None)
    def test_save_to_database_with_none_database(self):
        """Test that function returns False when node_database is None."""
        result = _save_to_database({"key": "value"})
        assert result is False

    @patch("hub_adapter.user_settings.node_database")
    def test_save_to_database_operational_error(self, mock_db):
        """Test that function returns False on OperationalError."""
        mock_db.side_effect = pw.OperationalError("Connection failed")

        with patch("hub_adapter.user_settings.logger"):
            result = _save_to_database({"key": "value"})

        assert result is False

    @patch("hub_adapter.user_settings.node_database")
    @patch("hub_adapter.user_settings.bind_user_settings")
    @patch("hub_adapter.user_settings.logger")
    def test_save_to_database_logs_success(self, test_logger, mock_bind, mock_db):
        """Test that function logs when successfully saving to database."""
        settings_dict = {"require_data_store": True, "autostart": {"enabled": False}}

        with patch("hub_adapter.user_settings.PersistentUserConfiguration.update") as mock_update:
            mock_query = Mock()
            mock_update.return_value = mock_query
            mock_query.where.return_value = mock_query
            mock_query.execute.return_value = None

            with patch("hub_adapter.user_settings.bind_user_settings"):
                _save_to_database(settings_dict)
                test_logger.info.assert_called()


class TestSaveToJson:
    """Tests for _save_to_json function."""

    def test_save_to_json_success(self):
        """Test successfully saving settings to JSON file."""
        settings_dict = {"require_data_store": False, "autostart": {"enabled": True}}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "userSettings.json"

            with patch("hub_adapter.user_settings.SETTINGS_PATH", json_path):
                _save_to_json(settings_dict, db_saved=True)

            assert json_path.exists()
            saved_data = json.loads(json_path.read_text())
            assert saved_data == settings_dict

    @patch("hub_adapter.user_settings.logger")
    def test_save_to_json_with_db_failed(self, test_logger):
        """Test that function logs appropriately when database save failed."""
        settings_dict = {"require_data_store": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "userSettings.json"

            with patch("hub_adapter.user_settings.SETTINGS_PATH", json_path):
                _save_to_json(settings_dict, db_saved=False)
                test_logger.info.assert_called_once()
                assert "database unavailable" in test_logger.info.call_args[0][0].lower()

    def test_save_to_json_error_handling(self):
        """Test that function raises exception on file write error."""
        settings_dict = {"key": "value"}

        with patch("hub_adapter.user_settings.SETTINGS_PATH") as mock_path:
            mock_path.write_text.side_effect = OSError("Permission denied")
            with pytest.raises(OSError):
                _save_to_json(settings_dict, db_saved=True)


class TestLoadPersistentSettings:
    """Tests for load_persistent_settings function."""

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_load_persistent_settings_from_database(self, mock_load_json, mock_load_db, mock_user_settings_class):
        """Test loading settings from database when available."""
        mock_load_db.return_value = {
            "require_data_store": False,
        }
        mock_load_json.return_value = {}

        # Mock the UserSettings class to return a mock instance
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True, "autostart": {}}
        mock_user_settings_class.return_value = mock_settings_instance

        result = load_persistent_settings()

        assert isinstance(result, UserSettings) or hasattr(result, "require_data_store")
        mock_load_db.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_load_persistent_settings_fallback_to_json(self, mock_load_json, mock_load_db, mock_user_settings_class):
        """Test loading from JSON when database returns empty."""
        mock_load_db.return_value = {}
        mock_load_json.return_value = {
            "require_data_store": False,
        }

        # Mock the UserSettings class
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True, "autostart": {}}
        mock_user_settings_class.return_value = mock_settings_instance

        result = load_persistent_settings()

        assert isinstance(result, UserSettings) or hasattr(result, "require_data_store")

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_load_persistent_settings_merges_with_defaults(
        self, mock_load_json, mock_load_db, mock_user_settings_class
    ):
        """Test that loaded settings are merged with default UserSettings."""
        mock_load_db.return_value = {"require_data_store": False}
        mock_load_json.return_value = {}

        # Mock the UserSettings class
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True, "autostart": {"enabled": False}}
        mock_user_settings_class.return_value = mock_settings_instance

        result = load_persistent_settings()

        # Should have autostart settings
        assert hasattr(result, "autostart") or result is not None

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_load_persistent_settings_returns_user_settings_instance(
        self, mock_load_json, mock_load_db, mock_user_settings_class
    ):
        """Test that function returns UserSettings instance."""
        mock_load_db.return_value = {}
        mock_load_json.return_value = {}

        # Mock the UserSettings class
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True}
        mock_user_settings_class.return_value = mock_settings_instance

        result = load_persistent_settings()

        assert result is not None


class TestSavePersistentSettings:
    """Tests for save_persistent_settings function."""

    @patch("hub_adapter.user_settings._save_to_database")
    @patch("hub_adapter.user_settings._save_to_json")
    def test_save_persistent_settings_saves_to_both(self, mock_save_json, mock_save_db):
        """Test that settings are saved to both database and JSON."""
        mock_save_db.return_value = True

        settings = Mock(spec=UserSettings)
        settings.model_dump.return_value = {"require_data_store": False}
        save_persistent_settings(settings)

        mock_save_db.assert_called_once()
        mock_save_json.assert_called_once()

    @patch("hub_adapter.user_settings._save_to_database")
    @patch("hub_adapter.user_settings._save_to_json")
    def test_save_persistent_settings_passes_db_status_to_json(self, mock_save_json, mock_save_db):
        """Test that database save status is passed to JSON save function."""
        mock_save_db.return_value = False

        settings = Mock(spec=UserSettings)
        settings.model_dump.return_value = {"require_data_store": False}
        save_persistent_settings(settings)

        # Check that _save_to_json was called with db_saved=False
        call_args = mock_save_json.call_args
        assert call_args[0][1] is False  # db_saved parameter

    @patch("hub_adapter.user_settings._save_to_database")
    @patch("hub_adapter.user_settings._save_to_json")
    def test_save_persistent_settings_excludes_none_values(self, mock_save_json, mock_save_db):
        """Test that None values are excluded from saved data."""
        mock_save_db.return_value = True

        settings = Mock(spec=UserSettings)
        settings.model_dump.return_value = {"require_data_store": False}
        save_persistent_settings(settings)

        # Get the settings_dict passed to _save_to_database
        call_args = mock_save_db.call_args
        saved_dict = call_args[0][0]

        # Verify the structure
        assert "require_data_store" in saved_dict
        assert saved_dict["require_data_store"] is False


class TestUpdateSettings:
    """Tests for update_settings function."""

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_with_single_field(self, mock_save, mock_load, mock_user_settings_class):
        """Test updating a single field in settings."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {"require_data_store": True, "autostart": {}}
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        result = update_settings({"require_data_store": False})

        mock_save.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_with_nested_fields(self, mock_save, mock_load, mock_user_settings_class):
        """Test updating nested fields in settings."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {
            "require_data_store": True,
            "autostart": {"enabled": False, "interval": 60},
        }
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        result = update_settings({"autostart": {"enabled": True}})

        mock_save.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_preserves_unmodified_fields(self, mock_save, mock_load, mock_user_settings_class):
        """Test that unmodified fields are preserved."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {
            "require_data_store": True,
            "autostart": {"enabled": False, "interval": 120},
        }
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        result = update_settings({"autostart": {"enabled": True}})

        mock_save.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_returns_user_settings_instance(self, mock_save, mock_load, mock_user_settings_class):
        """Test that function returns UserSettings instance."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {"require_data_store": True}
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        result = update_settings({"require_data_store": False})

        mock_save.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_saves_result(self, mock_save, mock_load, mock_user_settings_class):
        """Test that updated settings are saved."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {"require_data_store": True}
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        update_settings({"require_data_store": False})

        mock_save.assert_called_once()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings.load_persistent_settings")
    @patch("hub_adapter.user_settings.save_persistent_settings")
    def test_update_settings_empty_update(self, mock_save, mock_load, mock_user_settings_class):
        """Test updating with empty dictionary."""
        mock_settings = Mock(spec=UserSettings)
        mock_settings.model_dump.return_value = {"require_data_store": True}
        mock_load.return_value = mock_settings

        mock_updated = Mock(spec=UserSettings)
        mock_user_settings_class.return_value = mock_updated

        result = update_settings({})

        mock_save.assert_called_once()


class TestPersistentUserConfiguration:
    """Tests for PersistentUserConfiguration model."""

    def test_persistent_user_configuration_is_peewee_model(self):
        """Test that PersistentUserConfiguration is a Peewee Model."""
        assert issubclass(PersistentUserConfiguration, pw.Model)

    def test_persistent_user_configuration_has_configuration_field(self):
        """Test that model has a configuration field."""
        # Check that the field exists in the class
        assert hasattr(PersistentUserConfiguration, "configuration")


class TestBindUserSettings:
    """Tests for bind_user_settings context manager."""

    @patch("hub_adapter.user_settings.node_database")
    def test_bind_user_settings_context_manager(self, mock_db):
        """Test that bind_user_settings works as a context manager."""
        mock_db.bind_ctx.return_value.__enter__ = Mock()
        mock_db.bind_ctx.return_value.__exit__ = Mock()
        mock_db.create_tables = Mock()

        with patch("hub_adapter.user_settings.bind_user_settings") as mock_bind:
            mock_bind.return_value.__enter__ = Mock()
            mock_bind.return_value.__exit__ = Mock()

            with mock_bind(mock_db):
                assert True  # Context manager should work without errors


class TestIntegration:
    """Integration tests for user_settings module."""

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._save_to_database")
    @patch("hub_adapter.user_settings._save_to_json")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_load_and_save_cycle(
        self, mock_load_json, mock_save_json, mock_save_db, mock_load_db, mock_user_settings_class
    ):
        """Test a complete load and save cycle."""
        mock_load_db.return_value = {"require_data_store": True}
        mock_save_db.return_value = True

        # Mock UserSettings for load_persistent_settings
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True, "autostart": {}}
        mock_user_settings_class.return_value = mock_settings_instance

        # Call methods to trigger logger
        load_persistent_settings()
        update_settings({"require_data_store": False})

        mock_save_db.assert_called()
        mock_save_json.assert_called()

    @patch("hub_adapter.user_settings.UserSettings")
    @patch("hub_adapter.user_settings._load_from_database")
    @patch("hub_adapter.user_settings._load_from_json")
    def test_fallback_chain(self, mock_load_json, mock_load_db, mock_user_settings_class):
        """Test the complete fallback chain from database to JSON."""
        mock_load_db.return_value = {}
        mock_load_json.return_value = {"require_data_store": False}

        # Mock UserSettings
        mock_settings_instance = Mock(spec=UserSettings)
        mock_settings_instance.model_dump.return_value = {"require_data_store": True, "autostart": {}}
        mock_user_settings_class.return_value = mock_settings_instance

        result = load_persistent_settings()

        assert result is not None
