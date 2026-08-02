"""Shared instances of the background task managers.

Need to be initialized here rather than in server.py so that there is exactly one of each, no matter how the
app is launched. server.py can be executed as a script, which binds it to "__main__" instead of "hub_adapter.server".
Anything importing it by its package name afterwards would load the file a second time and build a second set of
managers.
"""

from hub_adapter.autostart import AutostartManager
from hub_adapter.kong_cleanup import KongCleanupManager
from hub_adapter.service_health import ServiceHealthMonitor

autostart_manager = AutostartManager()
kong_cleanup_manager = KongCleanupManager()
service_health_monitor = ServiceHealthMonitor()
