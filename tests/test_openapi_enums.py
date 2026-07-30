"""API-wide guards for the enums exported in openapi.json.

The frontend generates its types from openapi.json, so every set of canned strings the API accepts or
returns has to arrive there as a named string schema it can import. That only holds if the enums stay
StrEnums — a plain Enum leaks member names instead of values, and the legacy (str, Enum) pairing
stringifies as "ClassName.MEMBER" outside of Pydantic.
"""

import importlib
import pkgutil
from enum import Enum, StrEnum

import hub_adapter

# Enums that are part of the API surface, i.e. reachable from a request or response model
API_ENUMS = (
    "CleanUpType",
    "DataStoreType",
    "HealthStatus",
    "HttpMethodCode",
    "PodStatus",
    "ProtocolCode",
    "ServiceCheckStatus",
    "ServiceMonitoringStatus",
    "ServiceTag",
)


def _hub_adapter_enums() -> dict[str, type[Enum]]:
    """Collect every enum defined anywhere in the hub_adapter package, keyed by class name."""
    found: dict[str, type[Enum]] = {}

    for module_info in pkgutil.walk_packages(hub_adapter.__path__, prefix=f"{hub_adapter.__name__}."):
        module = importlib.import_module(module_info.name)

        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, Enum) and attr.__module__.startswith(hub_adapter.__name__):
                found[attr.__name__] = attr

    return found


class TestEnumDefinitions:
    """Every enum this package defines has to use StrEnum, not the legacy (str, Enum) pairing."""

    def test_all_enums_are_str_enums(self):
        offenders = sorted(name for name, enum_cls in _hub_adapter_enums().items() if not issubclass(enum_cls, StrEnum))
        assert not offenders, f"These enums must subclass StrEnum instead of (str, Enum) or Enum: {offenders}"


class TestOpenApiEnums:
    """The API enums have to reach openapi.json as named string schemas."""

    def test_api_enums_are_named_string_schemas(self, test_client):
        schemas = test_client.app.openapi()["components"]["schemas"]
        defined = _hub_adapter_enums()

        for name in API_ENUMS:
            assert name in schemas, f"{name} is missing from components.schemas"
            assert schemas[name]["type"] == "string", f"{name} is not typed as a string schema"
            assert schemas[name]["enum"] == [member.value for member in defined[name]]
