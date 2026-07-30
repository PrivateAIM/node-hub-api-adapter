"""Unit tests for the shared background task manager instances."""

import importlib.util
import sys

MANAGERS = ("autostart_manager", "kong_cleanup_manager", "service_health_monitor")


def _load_server_as_script(name: str = "__main_simulated__"):
    """Load server.py under a second module name, as `python hub_adapter/server.py` does.

    Running the file directly binds it to "__main__" rather than "hub_adapter.server", so any
    module level state defined in server.py gets built a second time when something imports it
    by its package name.
    """
    spec = importlib.util.spec_from_file_location(name, "hub_adapter/server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module

    finally:
        del sys.modules[name]


def test_managers_are_shared_when_server_is_run_as_a_script():
    """The routers must reach the same manager instances the lifespan starts.

    The lifespan starts whichever managers the running server module holds, while the routers
    reach them by package name. If server.py owned them, running it as a script would leave the
    routers reading a second set that was never started, e.g. reporting that service health
    monitoring is disabled while the loop is happily recording checks.
    """
    from hub_adapter import managers

    as_script = _load_server_as_script()

    for manager in MANAGERS:
        assert getattr(as_script, manager) is getattr(managers, manager), (
            f"{manager} was duplicated when server.py was loaded under a second module name"
        )


def test_routers_do_not_import_managers_from_the_server_module():
    """Importing the managers from hub_adapter.server reintroduces the duplication above."""
    from pathlib import Path

    offenders = [
        path.as_posix()
        for path in Path("hub_adapter/routers").glob("*.py")
        if "from hub_adapter.server import" in path.read_text()
    ]

    assert not offenders, f"Routers must import managers from hub_adapter.managers: {offenders}"
