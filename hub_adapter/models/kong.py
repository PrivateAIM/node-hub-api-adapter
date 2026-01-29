"""Models for the Kong microservice."""

from enum import Enum

from kong_admin_client import (
    ACL,
    Consumer,
    CreateServiceRequest,
    CreateServiceRequestClientCertificate,
    KeyAuth,
    ListConsumer200Response,
    ListRoute200Response,
    ListService200Response,
    Route,
    RouteService,
    Service,
)
from pydantic import BaseModel, SecretStr


class DataStoreType(str, Enum):
    """Data store types."""

    S3 = "s3"
    FHIR = "fhir"


class HttpMethodCode(str, Enum):
    """HTTP method codes."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    CONNECT = "CONNECT"
    TRACE = "TRACE"
    CUSTOM = "CUSTOM"


class ProtocolCode(str, Enum):
    """Protocol codes."""

    HTTP = "http"
    GRPC = "grpc"
    GRPCS = "grpcs"
    TLS = "tls"
    TCP = "tcp"


class ServiceRequest(CreateServiceRequest):
    """Improved version of the CreateServiceRequest with better defaults."""

    protocol: str | None = "http"
    port: int | None = 80
    path: str
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
                    "tags": ["example"],
                    "client_certificate": None,
                    "tls_verify": None,
                    "tls_verify_depth": None,
                    "ca_certificates": None,
                    "enabled": True,
                }
            ]
        }
    }


class MinioConfig(BaseModel):
    """Credentials for accessing a private S3 bucket hosted on MinIO."""

    minio_access_key: SecretStr
    minio_secret_key: SecretStr
    minio_region: str = "us-east-1"
    bucket_name: str | None = None
    timeout: int = 100000
    strip_path_pattern: str | None = None


class LinkDataStoreProject(BaseModel):
    route: Route
    keyauth: KeyAuth
    acl: ACL


class LinkProjectAnalysis(BaseModel):
    consumer: Consumer
    keyauth: KeyAuth
    acl: ACL


class DetailedService(Service):
    """Custom route response model with associated services."""

    routes: list[Route] | None = []


class DetailedRoute(Route):
    """Custom route response model with associated services."""

    service: Service | RouteService | None = None


class ListConsumers(ListConsumer200Response):
    """Custom route list response model."""

    data: list[Consumer] | None = None


class ListRoutes(ListRoute200Response):
    """Custom route list response model."""

    data: list[DetailedRoute] | None = None


class ListServices(ListService200Response):
    """Custom route list response model."""

    data: list[DetailedService] | None = None


class DeleteProject(BaseModel):
    """Response from disconnecting a project from a datastore."""

    removed: Route | None
    status: int | None = None
