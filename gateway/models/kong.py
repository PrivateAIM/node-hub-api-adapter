"""Models for the Kong microservice."""
from enum import Enum

from kong_admin_client import CreateServiceRequest, CreateServiceRequestClientCertificate, Plugin, Consumer, KeyAuth, \
    ACL
from kong_admin_client.models.service import Service
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


class LinkDataStoreProject(BaseModel):
    route: Service
    keyauth: Plugin
    acl: Plugin


class LinkProjectAnalysis(BaseModel):
    consumer: Consumer
    keyauth: KeyAuth
    acl: ACL


class Disconnect(BaseModel):
    """Response from disconnecting a project from a datastore."""
    removed_routes: list[str] | None
    status: str | None


HttpMethodCode = constr(pattern=r"(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|CONNECT|TRACE|CUSTOM)")
ProtocolCode = constr(pattern=r"(http|grpc|grpcs|tls|tcp)")
