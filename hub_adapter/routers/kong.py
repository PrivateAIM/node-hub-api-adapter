"""EPs for the kong service."""

import logging
import time
import uuid
from typing import Annotated
from uuid import UUID

import httpx2
import kong_admin_client
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security
from kong_admin_client import (
    ApiException,
    CreateAclForConsumerRequest,
    CreateConsumerRequest,
    CreateKeyAuthForConsumerRequest,
    CreatePluginForConsumerRequest,
    CreateRouteRequest,
    CreateServiceRequest,
    ListService200Response,
    Service,
)
from starlette import status

from hub_adapter.auth import jwtbearer, require_steward_role, verify_idp_token
from hub_adapter.conf import Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings
from hub_adapter.errors import (
    BucketError,
    FhirEndpointError,
    KongAmbiguousProjectDatastoreError,
    KongAnalysisConsumerNotFoundError,
    KongConsumerApiKeyError,
    KongDataStoreLinkedError,
    KongDatastoreLinkedToOtherProjectError,
    KongDatastoreMissingTypeError,
    KongDatastoreOrProjectNotFoundError,
    KongGatewayError,
    KongProjectDatastoreLinkConflictError,
    KongProjectDatastoreUnlinkedError,
    KongProjectEmptyError,
    KongProjectNotMappedError,
    KongProxyNotConfiguredError,
    KongServiceError,
    KongUpstreamError,
    KongValidationError,
    catch_kong_errors,
)
from hub_adapter.schemas.kong import (
    DataStoreType,
    HttpMethodCode,
    LinkDataStoreProject,
    LinkProjectAnalysis,
    ListConsumers,
    ListRoutes,
    ListServices,
    ProtocolCode,
    S3Config,
    ServiceRequest,
    UnlinkResponse,
)
from hub_adapter.utils import (
    HEALTH_TAG,
    analysis_tag,
    analysis_username,
    datastore_tag,
    health_username,
    is_uuid,
    parse_tags,
    project_tag,
    type_tag,
    validate_datastore_name,
)

kong_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=[ServiceTag.KONG],
    responses={404: {"description": "Not found"}},
    prefix="/kong",
)

logger = logging.getLogger(__name__)

DEFAULT_METHODS: list[HttpMethodCode] = [HttpMethodCode.GET]
DEFAULT_PROTOCOLS: list[ProtocolCode] = [ProtocolCode.HTTP]


def _require_uuid_ids(**ids: str | uuid.UUID) -> None:
    """Validate that the given ids are UUID-shaped before using them in Kong tags filters or ACL groups.

    Kong treats ',' in a tags filter as an AND separator between whole tag values. An id containing a comma would
    corrupt the filter built from it.
    """
    for name, value in ids.items():
        if not is_uuid(value):
            raise KongValidationError(f"{name} must be a valid UUID, got {value!r}")


def _find_project_datastore_route(api_client, project_id: str | uuid.UUID, datastore_id: str | uuid.UUID):
    """List the link routes between a project and a data store via tags."""
    route_api = kong_admin_client.RoutesApi(api_client)
    return route_api.list_route(tags=f"{project_tag(project_id)},{datastore_tag(datastore_id)}")


def _find_datastore_routes(api_client, datastore_id: str | uuid.UUID):
    """List the link routes for a data store, across every project it's linked to."""
    route_api = kong_admin_client.RoutesApi(api_client)
    return route_api.list_route(tags=datastore_tag(datastore_id))


def _resolve_datastore_services(api_client, datastore_id_or_name: str) -> list[Service]:
    """Resolve a path value to one or more Kong services.

    Tries a direct service id/name lookup first. For backwards compatibility, if that 404s and the value is a UUID,
    it's treated as a project id and resolved via the project's linked data stores instead
    """
    svc_api = kong_admin_client.ServicesApi(api_client)

    try:
        return [svc_api.get_service(service_id_or_name=datastore_id_or_name)]

    except ApiException as e:
        if e.status != status.HTTP_404_NOT_FOUND or not is_uuid(datastore_id_or_name):
            raise

        route_api = kong_admin_client.RoutesApi(api_client)
        routes = route_api.list_route(tags=project_tag(datastore_id_or_name))
        linked_service_ids = {route.service.id for route in routes.data if route.service}

        if not linked_service_ids:
            raise KongDatastoreOrProjectNotFoundError(datastore_id_or_name) from e

        return [svc_api.get_service(service_id_or_name=svc_id) for svc_id in linked_service_ids]


def parse_project_info(services, client) -> dict:
    """Get detailed information on project(s)."""
    service_dicts = [svc.to_dict() for svc in services.data]
    route_api_instance = kong_admin_client.RoutesApi(client)
    routes = route_api_instance.list_route()

    route_dict = {}
    for route in routes.data:
        if route.service:
            svc_id = route.service.id
            if svc_id in route_dict:
                route_dict[svc_id].append(route)
            else:
                route_dict[svc_id] = [route]

    for idx, svc in enumerate(service_dicts):
        svc_id = svc.get("id")
        svc["routes"] = []
        if svc_id in route_dict:
            svc["routes"] += route_dict[svc_id]

        service_dicts[idx] = svc

    return {"data": service_dicts}


def get_data_stores(
    settings: Annotated[Settings, Depends(get_settings)],
    ds_type: DataStoreType | None = None,
    detailed: bool = False,
) -> ListService200Response | dict:
    """Get all data stores (services), optionally filtered by type."""
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    tags = None if ds_type is None else type_tag(ds_type)

    with kong_admin_client.ApiClient(configuration) as api_client:
        service_api_instance = kong_admin_client.ServicesApi(api_client)
        services = service_api_instance.list_service(tags=tags)

        if detailed:
            services = parse_project_info(services, api_client)

        return services


@kong_router.get(
    "/datastore",
    response_model=ListServices,
    status_code=status.HTTP_200_OK,
    name="kong.datastore.get",
)
@catch_kong_errors
async def list_data_stores(
    settings: Annotated[Settings, Depends(get_settings)],
    ds_type: Annotated[DataStoreType | None, Query(description="Filter by data store type")] = None,
    detailed: Annotated[bool, Query(description="Whether to include linked projects (routes)")] = False,
):
    """List all available data stores (referred to as services by kong)."""
    return get_data_stores(settings, ds_type=ds_type, detailed=detailed)


@kong_router.get(
    "/datastore/{datastore_id_or_name}",
    response_model=ListServices,
    status_code=status.HTTP_200_OK,
    name="kong.datastore.get",
)
@catch_kong_errors
async def get_data_store(
    settings: Annotated[Settings, Depends(get_settings)],
    datastore_id_or_name: Annotated[str, Path(description="Kong service ID or display name of the data store.")],
    detailed: Annotated[bool, Query(description="Whether to include linked projects (routes)")] = False,
):
    """Retrieve a specific data store by its Kong service ID or display name.

    For backwards compatibility, a project ID is also accepted. If no service matches directly,
    all data stores currently linked to that project are returned instead.
    """
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        svcs = _resolve_datastore_services(api_client, datastore_id_or_name)
        services = ListService200Response(data=svcs)

        if detailed:
            return parse_project_info(services, api_client)

        return services


@kong_router.delete(
    "/datastore/{datastore_id_or_name}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    name="kong.datastore.delete",
)
@catch_kong_errors
async def delete_data_store(
    settings: Annotated[Settings, Depends(get_settings)],
    datastore_id_or_name: Annotated[str, Path(description="Kong service ID or display name of the data store.")],
    cascade: Annotated[bool, Query(description="Also delete existing project links (routes)")] = False,
):
    """Delete a data store (service). Refused with 409 while projects link it, unless cascade=true.

    Cascading removes the link routes only, consumers (analyses) belong to projects and are untouched.

    For backwards compatibility, a project ID is also accepted in place of the data store id/name, but only if
    it resolves to exactly one linked data store, otherwise refused with 409 if the project is linked to more than 1
    """
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        svc_api = kong_admin_client.ServicesApi(api_client)
        route_api = kong_admin_client.RoutesApi(api_client)

        svcs = _resolve_datastore_services(api_client, datastore_id_or_name)
        if len(svcs) > 1:
            raise KongAmbiguousProjectDatastoreError(datastore_id_or_name, [str(svc.id) for svc in svcs])

        svc = svcs[0]
        routes = route_api.list_route(tags=datastore_tag(svc.id))

        if routes.data and not cascade:
            linked_projects = sorted({parse_tags(route.tags).get("project", "unknown") for route in routes.data})
            raise KongDataStoreLinkedError(str(svc.name or svc.id), linked_projects)

        for route in routes.data:
            route_api.delete_route(route.id)
            logger.info(f"Deleted link (route) {route.id} for data store {svc.id}")

        svc_api.delete_service(service_id_or_name=svc.id)
        logger.info(f"Data store {svc.id} deleted")

        return status.HTTP_200_OK


@kong_router.post(
    "/datastore",
    response_model=Service,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_steward_role)],
    name="kong.datastore.create",
)
@catch_kong_errors
async def create_data_store(
    settings: Annotated[Settings, Depends(get_settings)],
    datastore: Annotated[
        ServiceRequest,
        Body(
            description="Required information for creating a new data store.",
            title="Data store metadata.",
        ),
    ],
    ds_type: Annotated[DataStoreType, Body(description="Data store type. Either 's3' or 'fhir'")],
    s3_config: Annotated[S3Config | None, Body(description="S3 configuration")] = None,
) -> Service | None:
    """Create a data store (service), independent of any project.

    The admin chosen display name must not be a bare UUID, the Kong service ID returned in the response is the main
    identifier.
    """
    try:
        validate_datastore_name(datastore.name)

    except ValueError as err:
        raise KongValidationError(str(err)) from err

    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        api_instance = kong_admin_client.ServicesApi(api_client)
        create_service_request = CreateServiceRequest(
            host=datastore.host,
            path=datastore.path,
            port=datastore.port,
            protocol=datastore.protocol,
            name=datastore.name,
            enabled=datastore.enabled,
            tls_verify=datastore.tls_verify,
            tags=[type_tag(ds_type)],
        )
        service_create_response = api_instance.create_service(create_service_request)

        plugin_api = kong_admin_client.PluginsApi(api_client)
        if s3_config:
            create_s3_gateway_request = CreatePluginForConsumerRequest(  # Also works for services
                name="minio-gateway",  # Still called minio gateway plugin
                instance_name=f"{service_create_response.id}-s3-gateway",
                # TODO change minio_* to s3_* once plugin is updated
                config={  # Can't use .model_dump() because of SecretStr
                    "minio_access_key": s3_config.s3_access_key.get_secret_value(),
                    "minio_secret_key": s3_config.s3_secret_key.get_secret_value(),
                    "minio_region": s3_config.s3_region,
                    "bucket_name": s3_config.bucket_name,
                    "timeout": s3_config.timeout,
                    "strip_path_pattern": s3_config.strip_path_pattern,
                },
                enabled=True,
                protocols=[datastore.protocol],
            )
            try:
                plugin_api.create_plugin_for_service(service_create_response.id, create_s3_gateway_request)

            except (HTTPException, ApiException) as error:  # Delete service if s3 fails
                logger.error(f"Unable to create s3 gateway for {datastore.name}")
                svc_api = kong_admin_client.ServicesApi(api_client)
                svc_api.delete_service(service_id_or_name=service_create_response.id)
                raise error

        return service_create_response


def get_projects(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: uuid.UUID | str | None = None,
    detailed: bool = False,
) -> ListRoutes | dict:
    """Get the link routes for all projects or a single one, via tags."""
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    tags = None if project_id is None else project_tag(project_id)

    with kong_admin_client.ApiClient(configuration) as api_client:
        api_instance = kong_admin_client.RoutesApi(api_client)
        api_response = api_instance.list_route(tags=tags)

        if len(api_response.data) == 0:
            logger.debug("Kong: No routes (project links) found.")

        if detailed:
            service_api_instance = kong_admin_client.ServicesApi(api_client)
            services = service_api_instance.list_service()
            service_dict = {str(svc.id): svc for svc in services.data}

            annotated_routes = []
            for route in api_response.data:
                service_id = route.service.id
                route_data = route.to_dict()
                if service_id in service_dict:
                    route_data["service"] = service_dict[service_id]

                annotated_routes.append(route_data)

            api_response = {"data": annotated_routes}

        return api_response


@kong_router.get(
    "/project",
    response_model=ListRoutes,
    status_code=status.HTTP_200_OK,
    name="kong.project.get",
)
@catch_kong_errors
async def list_projects(
    settings: Annotated[Settings, Depends(get_settings)],
    detailed: Annotated[
        bool,
        Query(description="Whether to include detailed information on the connected kong service"),
    ] = False,
):
    """List all projects (referred to as routes by kong) available, can be filtered by project_id.

    Set "detailed" to True to include detailed information on the linked kong service.
    """
    return get_projects(settings, project_id=None, detailed=detailed)


@kong_router.get(
    "/project/{project_id}",
    response_model=ListRoutes,
    status_code=status.HTTP_200_OK,
    name="kong.project.get",
)
@catch_kong_errors
async def list_specific_project(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[uuid.UUID | str, Path(description="UUID of the associated project.")],
    detailed: Annotated[
        bool,
        Query(description="Whether to include detailed information on the connected kong service"),
    ] = False,
):
    """List a specific projects (referred to as routes by kong) using the project UUID.

    Set "detailed" to True to include detailed information on the linked kong service.
    """
    return get_projects(settings, project_id=project_id, detailed=detailed)


@kong_router.post(
    "/project/{project_id}/datastore/{datastore_id}",
    response_model=LinkDataStoreProject,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_steward_role)],
    name="kong.project.link",
)
@catch_kong_errors
async def link_project_to_datastore(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[uuid.UUID | str, Path(description="UUID of the project")],
    datastore_id: Annotated[uuid.UUID | str, Path(description="Kong service ID of the data store")],
    methods: Annotated[list[HttpMethodCode] | None, Body(description="List of acceptable HTTP methods")] = None,
    protocols: Annotated[
        list[ProtocolCode] | None,
        Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
    ] = None,
):
    """Link a project to a data store by creating a route on the store's service.

    A data store can only be linked to one project at a time.
    The route's matching path is "/{service_name}/{type}" with no project identifier in it.
    """
    _require_uuid_ids(project_id=project_id, datastore_id=datastore_id)

    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    methods = [HttpMethodCode(m).value for m in (methods or DEFAULT_METHODS)]
    protocols = [ProtocolCode(p).value for p in (protocols or DEFAULT_PROTOCOLS)]

    with kong_admin_client.ApiClient(configuration) as api_client:
        svc_api = kong_admin_client.ServicesApi(api_client)
        route_api = kong_admin_client.RoutesApi(api_client)
        plugin_api = kong_admin_client.PluginsApi(api_client)

        svc = svc_api.get_service(service_id_or_name=str(datastore_id))
        ds_type = parse_tags(svc.tags).get("type")

        if ds_type is None:
            raise KongDatastoreMissingTypeError(str(datastore_id))

        existing_routes = _find_datastore_routes(api_client, svc.id)
        if existing_routes.data:
            existing_project_ids = sorted(
                {parse_tags(route.tags).get("project", "unknown") for route in existing_routes.data}
            )
            if str(project_id) in existing_project_ids:
                raise KongProjectDatastoreLinkConflictError(str(project_id), str(svc.id))

            raise KongDatastoreLinkedToOtherProjectError(str(svc.id), existing_project_ids[0])

        create_route_request = CreateRouteRequest(
            name=f"{svc.name}-route",
            protocols=protocols,
            methods=methods,
            paths=[f"/{svc.name}/{ds_type}"],
            path_handling="v1",
            https_redirect_status_code=426,
            preserve_host=False,
            request_buffering=True,
            response_buffering=True,
            tags=[project_tag(project_id), datastore_tag(svc.id), type_tag(ds_type)],
        )
        route_response = route_api.create_route_for_service(str(svc.id), create_route_request)

        # Keyauth for authentication
        create_keyauth_request = CreatePluginForConsumerRequest(
            name="key-auth",
            instance_name=f"{route_response.id}-keyauth",
            config={
                "hide_credentials": True,
                "key_in_body": False,
                "key_in_header": True,
                "key_in_query": False,
                "key_names": ["apikey"],
                "run_on_preflight": True,
            },
            enabled=True,
            protocols=protocols,
        )

        create_acl_request = CreatePluginForConsumerRequest(
            name="acl",
            instance_name=f"{route_response.id}-acl",
            config={"allow": [str(project_id)], "hide_groups_header": True},
            enabled=True,
            protocols=protocols,
        )

        try:
            keyauth_response = plugin_api.create_plugin_for_route(route_response.id, create_keyauth_request)
            acl_response = plugin_api.create_plugin_for_route(route_response.id, create_acl_request)

        except (ApiException, HTTPException) as error:
            logger.error(f"Plugin setup failed to link {project_id} to {svc.id}, deleting route")
            route_api.delete_route(route_response.id)
            raise error

    try:
        await probe_connection(settings=settings, project_id=project_id, datastore_id=svc.id)

    except HTTPException as error:  # roll back the just-created link so no broken route lingers
        logger.error(f"Probe failed for new link {project_id} -> {svc.id}, deleting route")
        with kong_admin_client.ApiClient(configuration) as api_client:
            kong_admin_client.RoutesApi(api_client).delete_route(route_response.id)
        raise error

    return {"route": route_response, "keyauth": keyauth_response, "acl": acl_response}


@kong_router.post(
    "/initialize",
    response_model=LinkDataStoreProject,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_steward_role)],
    name="kong.initialize",
)
@catch_kong_errors
async def create_datastore_and_project_with_link(
    settings: Annotated[Settings, Depends(get_settings)],
    datastore: Annotated[Service, Depends(create_data_store)],
    project_id: Annotated[str | uuid.UUID, Body(description="UUID of the project")],
    protocols: Annotated[
        list[ProtocolCode],
        Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
    ] = ["http"],
    methods: Annotated[list[HttpMethodCode] | None, Body(description="List of acceptable HTTP methods")] = None,
):
    """Creates a new datastore (service) and a new project (route), then links them together with a health consumer."""
    try:
        return await link_project_to_datastore(
            settings=settings,
            project_id=project_id,
            datastore_id=datastore.id,
            methods=methods,
            protocols=protocols,
        )
    except HTTPException as error:  # link or probe failed: remove the freshly created service
        logger.error("Failed to link project to new datastore, deleting service")
        await delete_data_store(settings=settings, datastore_id_or_name=datastore.id, cascade=True)
        raise error


@kong_router.delete(
    "/project/{project_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    response_model=UnlinkResponse,
    name="kong.project.delete",
)
@catch_kong_errors
async def delete_project(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[uuid.UUID | str, Path(description="UUID of the project")],
) -> UnlinkResponse:
    """Disconnect a project from all data stores and delete all its consumers (analyses + health)."""
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    tags = project_tag(project_id)

    with kong_admin_client.ApiClient(configuration) as api_client:
        route_api = kong_admin_client.RoutesApi(api_client)
        consumer_api = kong_admin_client.ConsumersApi(api_client)

        routes = route_api.list_route(tags=tags)
        consumers = consumer_api.list_consumer(tags=tags)

        if not routes.data and not consumers.data:
            raise KongProjectEmptyError(str(project_id))

        for route in routes.data:
            route_api.delete_route(route.id)

        for consumer in consumers.data:
            consumer_api.delete_consumer(consumer_username_or_id=consumer.id)

        logger.info(
            f"Project {project_id} deleted: {len(routes.data)} link(s), {len(consumers.data)} consumer(s) removed"
        )

        return UnlinkResponse(removed_routes=routes.data, removed_consumers=consumers.data, status=status.HTTP_200_OK)


@kong_router.delete(
    "/project/{project_id}/datastore/{datastore_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    response_model=UnlinkResponse,
    name="kong.project.unlink",
)
@catch_kong_errors
async def unlink_project_from_datastore(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[uuid.UUID | str, Path(description="UUID of the project")],
    datastore_id: Annotated[uuid.UUID | str, Path(description="Kong service ID of the data store")],
) -> UnlinkResponse:
    """Unlink a single data store from a project. Consumers (analyses) are kept."""
    _require_uuid_ids(project_id=project_id, datastore_id=datastore_id)

    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        route_api = kong_admin_client.RoutesApi(api_client)
        routes = _find_project_datastore_route(api_client, project_id, datastore_id)

        if not routes.data:
            raise KongProjectDatastoreUnlinkedError(str(project_id), str(datastore_id))

        for route in routes.data:
            route_api.delete_route(route.id)
            logger.info(f"Project {project_id} unlinked from data store {datastore_id} (route {route.id})")

        return UnlinkResponse(removed_routes=routes.data, status=status.HTTP_200_OK)


def _find_analysis_consumer(api_client, analysis_id: str | uuid.UUID):
    """Resolve the Kong consumer for an analysis via its tag, or None."""
    consumer_api = kong_admin_client.ConsumersApi(api_client)
    consumers = consumer_api.list_consumer(tags=analysis_tag(analysis_id))
    return consumers.data[0] if consumers.data else None


def get_analyses(
    settings: Annotated[Settings, Depends(get_settings)],
    analysis_id: uuid.UUID | str | None = None,
    project_id: uuid.UUID | str | None = None,
) -> ListConsumers | dict:
    """Get consumers via tags. Health consumers are excluded — they are not analyses."""
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    tags = []
    if analysis_id:
        tags.append(analysis_tag(analysis_id))
    if project_id:
        tags.append(project_tag(project_id))

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        api_response = consumer_api.list_consumer(tags=",".join(tags) if tags else None)
        analyses = [c for c in api_response.data if HEALTH_TAG not in (c.tags or [])]
        return {"data": analyses}


@kong_router.get(
    "/analysis",
    response_model=ListConsumers,
    status_code=status.HTTP_200_OK,
    name="kong.analysis.get",
)
@catch_kong_errors
async def list_analyses(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[
        str | None,
        Query(description="Filter consumers by project UUID"),
    ] = None,
):
    """List all analyses (referred to as consumers by kong) available. Can be filtered by project UUID."""
    return get_analyses(settings, project_id=project_id)


@kong_router.get(
    "/analysis/{analysis_id}",
    response_model=ListConsumers,
    status_code=status.HTTP_200_OK,
    name="kong.analysis.get",
)
@catch_kong_errors
async def list_specific_analysis(
    settings: Annotated[Settings, Depends(get_settings)],
    analysis_id: Annotated[uuid.UUID | str | None, Path(description="UUID of the analysis.")],
    project_id: Annotated[
        str | None,
        Query(description="Filter consumers by project UUID"),
    ] = None,
):
    """List all analyses (referred to as consumers by kong) available."""
    return get_analyses(settings, analysis_id=analysis_id, project_id=project_id)


def get_analysis_keyauth(settings: Settings, analysis_id: str | uuid.UUID):
    """Return the existing key-auth credential for an analysis consumer, or None if absent/unreachable.

    Used to reuse an already registered consumer's credential instead of deleting and recreating it.
    """
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            consumer = _find_analysis_consumer(api_client, analysis_id)
            if consumer is None:
                return None

            keyauth_api = kong_admin_client.KeyAuthsApi(api_client)
            api_response = keyauth_api.list_key_auths_for_consumer(consumer.id)

    except ApiException as e:
        logger.warning(f"Unable to fetch existing key-auth for analysis {analysis_id}: {e}")
        if getattr(e, "status", None) == status.HTTP_404_NOT_FOUND:
            return None

        raise

    if api_response and api_response.data:
        return api_response.data[0]

    return None


@kong_router.post(
    "/analysis",
    response_model=LinkProjectAnalysis,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_steward_role)],
    name="kong.analysis.create",
)
@catch_kong_errors
async def create_and_connect_analysis_to_project(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[str | uuid.UUID, Body(description="UUID or name of the project")],
    analysis_id: Annotated[str | uuid.UUID, Body(description="UUID or name of the analysis")],
):
    """Create a new analysis and link it to a project."""
    _require_uuid_ids(project_id=project_id, analysis_id=analysis_id)

    proj_resp = get_projects(settings=settings, project_id=project_id, detailed=False)
    if not proj_resp.data:
        raise KongProjectNotMappedError()

    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    response = {}
    username = analysis_username(analysis_id)

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        api_response = consumer_api.create_consumer(
            CreateConsumerRequest(
                username=username,
                custom_id=username,
                tags=[project_tag(project_id), analysis_tag(analysis_id)],
            )
        )
        logger.info(f"Consumer added, id: {api_response.id}")

        consumer_id = api_response.id
        response["consumer"] = api_response

        # Configure acl plugin for consumer
        acl_api = kong_admin_client.ACLsApi(api_client)
        api_response = acl_api.create_acl_for_consumer(
            consumer_id,
            CreateAclForConsumerRequest(
                group=project_id,
                tags=[project_tag(project_id)],
            ),
        )
        logger.info(f"ACL plugin configured for consumer, group: {api_response.group}")
        response["acl"] = api_response

        # Configure key-auth plugin for consumer
        keyauth_api = kong_admin_client.KeyAuthsApi(api_client)
        api_response = keyauth_api.create_key_auth_for_consumer(
            consumer_id,
            CreateKeyAuthForConsumerRequest(
                tags=[project_tag(project_id)],
            ),
        )
        logger.info(f"Key authentication plugin configured for consumer, api_key: {api_response.key}")
        response["keyauth"] = api_response

    return response


@kong_router.delete(
    "/analysis/{analysis_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    name="kong.analysis.delete",
)
@catch_kong_errors
async def delete_analysis(
    settings: Annotated[Settings, Depends(get_settings)],
    analysis_id: Annotated[str | UUID, Path(description="UUID of the analysis.")],
):
    """Delete the listed analysis (consumer), resolved via its tag."""
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer = _find_analysis_consumer(api_client, analysis_id)
        if consumer is None:
            raise KongAnalysisConsumerNotFoundError(str(analysis_id))

        consumer_api = kong_admin_client.ConsumersApi(api_client)
        consumer_api.delete_consumer(consumer_username_or_id=consumer.id)

        logger.info(f"Analysis {analysis_id} deleted")
        return status.HTTP_200_OK


def ensure_health_consumer(settings: Settings, project_id: str | uuid.UUID) -> str:
    """Return an apikey for the project's health consumer, creating consumer/ACL/key-auth on demand.

    One health consumer exists per project, its project ACL group lets it probe every linked store.
    """
    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)
    username = health_username(project_id)

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        keyauth_api = kong_admin_client.KeyAuthsApi(api_client)

        consumers = consumer_api.list_consumer(tags=f"{HEALTH_TAG},{project_tag(project_id)}")
        consumer = consumers.data[0] if consumers.data else None

        if consumer is None:
            logger.info(f"No health consumer found for project {project_id}, creating one now")
            consumer = consumer_api.create_consumer(
                CreateConsumerRequest(
                    username=username,
                    custom_id=username,
                    tags=[HEALTH_TAG, project_tag(project_id)],
                )
            )
            acl_api = kong_admin_client.ACLsApi(api_client)
            acl_api.create_acl_for_consumer(
                consumer.id,
                CreateAclForConsumerRequest(group=str(project_id), tags=[project_tag(project_id)]),
            )

        keyauths = keyauth_api.list_key_auths_for_consumer(consumer.id)
        if keyauths and keyauths.data:
            return keyauths.data[0].key

        keyauth = keyauth_api.create_key_auth_for_consumer(
            consumer.id, CreateKeyAuthForConsumerRequest(tags=[project_tag(project_id)])
        )
        return keyauth.key


@kong_router.get(
    "/project/{project_id}/datastore/{datastore_id}/health",
    status_code=status.HTTP_200_OK,
    name="kong.probe",
)
@catch_kong_errors
async def probe_connection(
    settings: Annotated[Settings, Depends(get_settings)],
    project_id: Annotated[str | uuid.UUID, Path(description="UUID of the project.")],
    datastore_id: Annotated[str | uuid.UUID, Path(description="Kong service ID of the data store.")],
):
    """Test whether Kong can read the given data store through the project's link.

    Because we use the key-auth plugin, a consumer is required for pinging the data service.
    """
    _require_uuid_ids(project_id=project_id, datastore_id=datastore_id)

    if not settings.kong_proxy_service_url:
        raise KongProxyNotConfiguredError()

    configuration = kong_admin_client.Configuration(host=settings.kong_admin_service_url)

    with kong_admin_client.ApiClient(configuration) as api_client:
        routes = _find_project_datastore_route(api_client, project_id, datastore_id)

        if not routes.data:
            raise KongProjectDatastoreUnlinkedError(str(project_id), str(datastore_id))

        route = routes.data[0]
        ds_type = parse_tags(route.tags).get("type")
        route_path = route.paths[0]

    apikey = ensure_health_consumer(settings, project_id)
    if not apikey:
        raise KongConsumerApiKeyError()

    url = f"{settings.kong_proxy_service_url}{route_path}"
    is_fhir = ds_type == DataStoreType.FHIR.value

    if is_fhir:
        url = f"{url}/metadata"

    return probe_data_service(url=url, apikey=apikey, is_fhir=is_fhir)


def probe_data_service(url: str, apikey: str, is_fhir: bool, attempt: int = 1, max_attempts: int = 5) -> int:
    """Use httpx2 to probe the data service."""
    svc_resp = httpx2.get(
        url,
        headers={"apikey": apikey},
    )
    svc = "FHIR" if is_fhir else "S3"
    if svc_resp.status_code != 200:
        # Sometimes it takes a bit for kong to finish creating a route/service
        if svc_resp.status_code == status.HTTP_404_NOT_FOUND and attempt <= max_attempts:
            time.sleep(attempt * 2)  # Wait a little longer each attempt
            return probe_data_service(url=url, apikey=apikey, is_fhir=is_fhir, attempt=attempt + 1)

        if svc_resp.status_code == status.HTTP_403_FORBIDDEN and not is_fhir:
            raise BucketError()

        elif svc_resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            raise KongServiceError(server_type=svc)

        elif svc_resp.status_code == status.HTTP_404_NOT_FOUND and is_fhir:
            raise FhirEndpointError()

        elif svc_resp.status_code == status.HTTP_502_BAD_GATEWAY:
            raise KongGatewayError(server_type=svc)

        else:
            raise KongUpstreamError(status_code=svc_resp.status_code, message=svc_resp.text)

    logger.info(f"Successfully able to reach data service after {attempt} attempt(s)")
    return status.HTTP_200_OK
