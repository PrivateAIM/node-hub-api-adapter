"""Models for the Kong microservice."""
from enum import Enum

from kong_admin_client import CreateServiceRequest, Consumer, KeyAuth, \
    ACL, CreateServiceRequestClientCertificate, Route, ListRoute200Response, RouteService, \
    Service, ListService200Response
from pydantic import BaseModel, constr


class DataStoreType(Enum):
    """Data store types."""
    S3: str = "s3"
    FHIR: str = "fhir"


class ServiceRequest(CreateServiceRequest):
    """Improved version of the CreateServiceRequest with better defaults."""

    protocol: str | None = "http"
    port: int | None = 80
    path: str | None = "/somewhere"
    client_certificate: CreateServiceRequestClientCertificate | None = None
    tls_verify: bool | None = None
    ca_certificates: list[str] | None = None
    enabled: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "myNewDatastore",
                    "retries": 5,
                    "protocol": "http",
                    "host": "whonnock",
                    "port": 443,
                    "path": "/upload",
                    "connect_timeout": 6000,
                    "write_timeout": 6000,
                    "read_timeout": 6000,
                    "tags": [
                        "example"
                    ],
                    "client_certificate": None,
                    "tls_verify": None,
                    "tls_verify_depth": None,
                    "ca_certificates": None,
                    "enabled": True
                }
            ]
        }
    }


class LinkDataStoreProject(BaseModel):
    route: Route
    keyauth: KeyAuth
    acl: ACL


class LinkProjectAnalysis(BaseModel):
    consumer: Consumer
    keyauth: KeyAuth
    acl: ACL


class DetailedService(Route):
    """Custom route response model with associated services."""
    routes: list[Route] | None = None


class DetailedRoute(Route):
    """Custom route response model with associated services."""
    service: Service | RouteService | None = None


class ListRoutes(ListRoute200Response):
    """Custom route list response model."""
    data: list[DetailedRoute] | None = None


class ListServices(ListService200Response):
    """Custom route list response model."""
    data: list[DetailedService] | None = None


class Disconnect(BaseModel):
    """Response from disconnecting a project from a datastore."""
    removed_routes: list[str] | None
    status: int | None = None


HttpMethodCode = constr(pattern=r"(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|CONNECT|TRACE|CUSTOM)")
ProtocolCode = constr(pattern=r"(http|grpc|grpcs|tls|tcp)")
