"""Utility functions."""
import requests
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def __import_schema(schema_url: str) -> dict:
    """Import OpenAPI schema and add security to all methods then return dict of paths and tags."""
    schema = requests.get(schema_url).json()
    modified_paths = {}
    for path, request_methods in schema["paths"].items():
        for request_method, metadata in request_methods.items():
            keycloak_security = {"OAuth2AuthorizationCodeBearer": []}
            if "security" not in metadata:
                metadata["security"] = [keycloak_security]

            else:  # May be other security
                metadata["security"].append(keycloak_security)

            if path in modified_paths:
                modified_paths[path][request_method] = metadata

            else:
                modified_paths[path] = {request_method: metadata}

    return {
        "paths": modified_paths,
        "tags": schema["tags"] if "tags" in schema else [],
        "components": schema["components"],
    }


def export_openapi(api_app: FastAPI):
    """Exports the API and its routes as OpenAPI JSON."""
    if api_app.openapi_schema:
        return api_app.openapi_schema
    openapi_schema = get_openapi(
        title="FLAME 2 API",
        version="2.5.0",
        summary="This is a very custom OpenAPI schema",
        description="Here's a longer description of the custom **OpenAPI** schema",
        routes=api_app.routes,
    )
    api_app.openapi_schema = openapi_schema
    return api_app.openapi_schema


def merge_openapi_schemas(og_schema: dict, imported_schemas: list[dict]) -> dict:
    """Merge the API's schema with the imported paths and tags of other schemas."""
    for schema in imported_schemas:
        # Paths
        og_schema["paths"].update(schema["paths"])

        # Tags
        if "tags" not in og_schema:
            og_schema["tags"] = {}
        og_schema["tags"].update(schema["tags"])

        # Components
        comps_to_import = schema["components"]
        for comp in ("schemas", "securitySchemes"):
            if comp not in og_schema["components"]:
                og_schema["components"][comp] = comps_to_import[comp]

            else:
                og_schema["components"][comp].update(comps_to_import[comp])

    return og_schema
