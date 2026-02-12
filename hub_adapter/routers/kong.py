"""EPs for the kong service."""

import logging
import time
import uuid
from typing import Annotated

import httpx
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
from hub_adapter.dependencies import get_settings
from hub_adapter.errors import (
    BucketError,
    FhirEndpointError,
    KongConsumerApiKeyError,
    KongGatewayError,
    KongServiceError,
    catch_kong_errors, )
from hub_adapter.models.kong import (
    DataStoreType,
    DeleteProject,
    HttpMethodCode,
    LinkDataStoreProject,
    LinkProjectAnalysis,
    ListConsumers,
    ListRoutes,
    ListServices,
    MinioConfig,
    ProtocolCode,
    ServiceRequest,
)

kong_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(jwtbearer),
    ],
    tags=["Kong"],
    responses={404: {"description": "Not found"}},
    prefix="/kong",
)

logger = logging.getLogger(__name__)
FLAME = "flame"


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
        project_id: uuid.UUID | str | None = None,
        detailed: bool = False,
) -> ListService200Response | dict:
    """Get either all or a single data store (service)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    with kong_admin_client.ApiClient(configuration) as api_client:
        service_api_instance = kong_admin_client.ServicesApi(api_client)
        services = service_api_instance.list_service(tags=project_id)

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
        detailed: Annotated[bool, Query(description="Whether to include detailed information on projects")] = False,
):
    """List all available data stores (referred to as services by kong)."""
    return get_data_stores(settings, project_id=None, detailed=detailed)


@kong_router.get(
    "/datastore/{project_id}",
    response_model=ListServices,
    status_code=status.HTTP_200_OK,
    name="kong.datastore.get",
)
@catch_kong_errors
async def list_specific_data_store(
        settings: Annotated[Settings, Depends(get_settings)],
        project_id: Annotated[uuid.UUID | str, Path(description="UUID of the associated project.")],
        detailed: Annotated[bool, Query(description="Whether to include detailed information on projects")] = False,
):
    """Retrieve a specific data store using the project UUID"""
    return get_data_stores(settings, project_id=project_id, detailed=detailed)


@kong_router.delete(
    "/datastore/{data_store_name}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    name="kong.datastore.delete",
)
@catch_kong_errors
async def delete_data_store(
        settings: Annotated[Settings, Depends(get_settings)],
        data_store_name: Annotated[str, Path(description="Unique name of the data store.")],
):
    """Delete the listed data store (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)

    # Delete related projects and analyses first, data_store_name is same as associated project in kong (route)
    # {ProjectUUID}-{datastore type}
    try:
        await delete_route(settings=settings, project_route_id=data_store_name)

    except HTTPException:
        logger.info(f"No routes for service {data_store_name} found")

    # Delete data store
    with kong_admin_client.ApiClient(configuration) as api_client:
        svc_api = kong_admin_client.ServicesApi(api_client)

        svc = svc_api.get_service(service_id_or_name=data_store_name)
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
async def create_service(
        settings: Annotated[Settings, Depends(get_settings)],
        datastore: Annotated[
            ServiceRequest,
            Body(
                description="Required information for creating a new data store.",
                title="Data store metadata.",
            ),
        ],
        ds_type: Annotated[DataStoreType, Body(description="Data store type. Either 's3' or 'fhir'")],
        minio_config: Annotated[MinioConfig | None, Body(description="Minio configuration")] = None,
) -> Service | None:
    """Create a datastore (referred to as services by kong) by providing necessary metadata."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)

    datastore_name = f"{datastore.name}-{ds_type.value}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        api_instance = kong_admin_client.ServicesApi(api_client)
        create_service_request = CreateServiceRequest(
            host=datastore.host,
            path=datastore.path,
            port=datastore.port,
            protocol=datastore.protocol,
            name=datastore_name,
            enabled=datastore.enabled,
            tls_verify=datastore.tls_verify,
            tags=[datastore.name, datastore_name],
        )
        service_create_response = api_instance.create_service(create_service_request)

        plugin_api = kong_admin_client.PluginsApi(api_client)
        if minio_config:
            create_minio_gateway_request = CreatePluginForConsumerRequest(  # Also works for services
                name="minio-gateway",
                instance_name=f"{datastore_name}-minio-gateway",
                config={  # Can't use .model_dump() because of SecretStr
                    "minio_access_key": minio_config.minio_access_key.get_secret_value(),
                    "minio_secret_key": minio_config.minio_secret_key.get_secret_value(),
                    "minio_region": minio_config.minio_region,
                    "bucket_name": minio_config.bucket_name,
                    "timeout": minio_config.timeout,
                    "strip_path_pattern": minio_config.strip_path_pattern,
                },
                enabled=True,
                protocols=[datastore.protocol],
            )
            try:
                plugin_api.create_plugin_for_service(service_create_response.id, create_minio_gateway_request)

            except HTTPException as error:  # Delete service if minio fails
                msg = f"Unable to create minio gateway for {datastore_name}"
                logger.error(msg)
                await delete_data_store(settings, service_create_response.id)
                raise error

        return service_create_response


def get_projects(
        settings: Annotated[Settings, Depends(get_settings)],
        project_id: uuid.UUID | str | None = None,
        detailed: bool = False,
) -> ListRoutes | dict:
    """Get either all or a single data store (service)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    project = str(project_id) if project_id else None

    with kong_admin_client.ApiClient(configuration) as api_client:
        api_instance = kong_admin_client.RoutesApi(api_client)
        api_response = api_instance.list_route(tags=project)

        if len(api_response.data) == 0:
            logger.debug("Kong: No routes (projects) found.")

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
    "/project",
    response_model=LinkDataStoreProject,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_steward_role)],
    name="kong.project.create",
)
@catch_kong_errors
async def create_route_to_datastore(
        settings: Annotated[Settings, Depends(get_settings)],
        data_store_id: Annotated[uuid.UUID | str, Body(description="UUID of the data store or 'service'")],
        project_id: Annotated[uuid.UUID | str, Body(description="UUID of the project")],
        methods: Annotated[list[HttpMethodCode], Body(description="List of acceptable HTTP methods")] = ["GET"],
        protocols: Annotated[
            list[ProtocolCode],
            Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
        ] = ["http"],
        ds_type: Annotated[DataStoreType, Body(description="Data store type. Either 's3' or 'fhir'")] = "fhir",
):
    """Connect a project to a data store (referred to as a route by kong)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    ds_type = ds_type.value if isinstance(ds_type, DataStoreType) else ds_type
    methods = [method.value if isinstance(method, HttpMethodCode) else method for method in methods]
    protocols = [protocol.value if isinstance(protocol, ProtocolCode) else protocol for protocol in protocols]

    # Construct path from project_id and type
    project = str(project_id)
    name = f"{project_id}-{ds_type}"
    path = f"/{name}/{ds_type}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        route_api = kong_admin_client.RoutesApi(api_client)
        plugin_api = kong_admin_client.PluginsApi(api_client)

        # Create requests
        create_route_request = CreateRouteRequest(
            name=name,
            protocols=protocols,
            methods=methods,
            paths=[path],
            https_redirect_status_code=426,
            preserve_host=False,
            request_buffering=True,
            response_buffering=True,
            tags=[str(project_id), ds_type],
        )

        # Keyauth for authentication
        create_keyauth_request = CreatePluginForConsumerRequest(
            name="key-auth",
            instance_name=f"{project}-{ds_type}-keyauth",
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
            instance_name=f"{project}-{ds_type}-acl",
            config={"allow": [project], "hide_groups_header": True},
            enabled=True,
            protocols=protocols,
        )

        route_response = route_api.create_route_for_service(str(data_store_id), create_route_request)
        keyauth_response = plugin_api.create_plugin_for_route(route_response.id, create_keyauth_request)
        acl_response = plugin_api.create_plugin_for_route(route_response.id, create_acl_request)

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
        datastore: Annotated[Service, Depends(create_service)],
        project_id: Annotated[str | uuid.UUID, Body(description="UUID of the project")],
        protocols: Annotated[
            list[ProtocolCode],
            Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
        ] = ["http"],
        ds_type: Annotated[
            DataStoreType, Body(description="Data store type. Either 's3' or 'fhir'")] = DataStoreType.FHIR,
):
    """Creates a new datastore (service) and a new project (route), then links them together with a health consumer."""
    proj_response = await create_route_to_datastore(
        settings=settings,
        project_id=project_id,
        data_store_id=datastore.id,
        protocols=protocols,
        ds_type=ds_type,
    )
    # Test connection
    try:
        await probe_connection(settings=settings, project_id=str(project_id), ds_type=ds_type)

    except HTTPException as error:  # if connection fails, delete service and route, then raise error
        logger.error("Failed to validate connection to datastore, deleting service and route")
        await delete_data_store(settings=settings, data_store_name=f"{project_id}-{ds_type.value}")
        raise error

    return proj_response


@kong_router.delete(
    "/project/{project_route_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_steward_role)],
    # response_model=DeleteProject,
    name="kong.project.delete",
)
@catch_kong_errors
async def delete_route(
        settings: Annotated[Settings, Depends(get_settings)],
        project_route_id: Annotated[
            str,
            Path(
                description="Unique identifier of the route to be deleted, "
                            "must include datastore type hyphenated at the end"
            ),
        ],
) -> DeleteProject:
    """Disconnect a project (route) from all data stores (services) and delete associated analyses (consumers)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    project_uuid = project_route_id.rsplit("-", 1)[0]

    with kong_admin_client.ApiClient(configuration) as api_client:
        route_api = kong_admin_client.RoutesApi(api_client)
        consumer_api = kong_admin_client.ConsumersApi(api_client)

        route = route_api.get_route(route_id_or_name=project_route_id)

        # Get related analyses (consumers) and delete them first
        consumer_response = consumer_api.list_consumer(tags=project_uuid)
        for consumer in consumer_response.data:
            consumer_api.delete_consumer(consumer_username_or_id=consumer.id)

        # Delete route
        route_api.delete_route(route.id)

        logger.info(f"Project {route.id} disconnected from data store {route.service.id}")

        return DeleteProject(removed=route, status=status.HTTP_200_OK)


def get_analyses(
        settings: Annotated[Settings, Depends(get_settings)],
        analysis_id: uuid.UUID | str | None = None,
        tag: str | None = None,
) -> ListConsumers | dict:
    """Get either all or a single analysis (consumer)."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    username = f"{analysis_id}-{FLAME}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        if analysis_id:
            api_response = consumer_api.get_consumer(consumer_username_or_id=username)
            api_response = {"data": [api_response]}

        else:
            api_response = consumer_api.list_consumer(tags=tag)

        return api_response


@kong_router.get(
    "/analysis",
    response_model=ListConsumers,
    status_code=status.HTTP_200_OK,
    name="kong.analysis.get",
)
@catch_kong_errors
async def list_analyses(
        settings: Annotated[Settings, Depends(get_settings)],
        tag: Annotated[str | None, Query(description="Filter consumers by project using the project UUID")] = None,
):
    """List all analyses (referred to as consumers by kong) available. Can be filtered by project UUID using tag."""
    return get_analyses(settings, analysis_id=None, tag=tag)


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
        tag: Annotated[str | None, Query(description="Filter consumers by project using the project UUID")] = None,
):
    """List all analyses (referred to as consumers by kong) available."""
    return get_analyses(settings, analysis_id=analysis_id, tag=tag)


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
    proj_resp = get_projects(settings=settings, project_id=project_id, detailed=False)

    # Tags are used to annotate routes (projects) with datastore type and original project ID
    route_tags = set()
    for proj in proj_resp.data:
        route_tags.update(proj.tags)

    # UUID must be cast to str to check in set since tags are strings
    if project_id not in route_tags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Associated project not mapped to a data store",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    response = {}
    username = f"{analysis_id}-{FLAME}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        api_response = consumer_api.create_consumer(
            CreateConsumerRequest(
                username=username,
                custom_id=username,
                tags=[str(project_id), str(analysis_id)],
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
                tags=[str(project_id)],
            ),
        )
        logger.info(f"ACL plugin configured for consumer, group: {api_response.group}")
        response["acl"] = api_response

        # Configure key-auth plugin for consumer
        keyauth_api = kong_admin_client.KeyAuthsApi(api_client)
        api_response = keyauth_api.create_key_auth_for_consumer(
            consumer_id,
            CreateKeyAuthForConsumerRequest(
                tags=[str(project_id)],
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
        analysis_id: Annotated[str, Path(description="UUID or unique name of the analysis.")],
):
    """Delete the listed analysis."""
    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    username = f"{analysis_id}-{FLAME}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)

        consumer_api.delete_consumer(consumer_username_or_id=username)

        logger.info(f"Analysis {analysis_id} deleted")
        return status.HTTP_200_OK


@kong_router.get(
    "/project/{project_id}/{ds_type}/health",
    status_code=status.HTTP_200_OK,
    name="kong.probe",
)
@catch_kong_errors
async def probe_connection(
        settings: Annotated[Settings, Depends(get_settings)],
        project_id: Annotated[str | uuid.UUID, Path(description="UUID or unique name of the project.")],
        ds_type: Annotated[DataStoreType, Path(description='Either "fhir" or "s3"')],
):
    """Test whether Kong can read the requested data source.

    Because we use the key-auth plugin, a consumer is required for pinging the data service.
    """
    if not settings.KONG_PROXY_SERVICE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Kong proxy service URL not configured",
                "service": "Kong",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

    configuration = kong_admin_client.Configuration(host=settings.KONG_ADMIN_SERVICE_URL)
    route_id = f"{project_id}-{ds_type.value}"
    apikey = None

    # Get API key for project (route) health consumer and route info
    with kong_admin_client.ApiClient(configuration) as api_client:
        # Check if health consumer exists for route/project
        health_consumer_id = f"{route_id}-health-{FLAME}"
        consumer_api = kong_admin_client.ConsumersApi(api_client)

        try:
            consumer_api.get_consumer(health_consumer_id)

        except ApiException:
            logger.warning(f"No health consumer found for {project_id}, creating one now")
            await create_and_connect_analysis_to_project(
                settings=settings,
                project_id=str(project_id),
                analysis_id=f"{route_id}-health",
            )

        # Parse project/route info
        route_api = kong_admin_client.RoutesApi(api_client)
        route_resp = route_api.get_route(route_id)
        route_path = route_resp.paths[0]

        # Get API key to query service
        keyauth_api = kong_admin_client.KeyAuthsApi(api_client)
        api_response = keyauth_api.list_key_auths_for_consumer(health_consumer_id)
        if api_response:
            apikey = api_response.data[0].key

    if apikey:
        url = f"{settings.KONG_PROXY_SERVICE_URL}{route_path}"
        is_fhir = ds_type == DataStoreType.FHIR

        if is_fhir:
            url = f"{url}/metadata"

        return probe_data_service(url=url, apikey=apikey, is_fhir=is_fhir)

    else:
        raise KongConsumerApiKeyError


def probe_data_service(url: str, apikey: str, is_fhir: bool, attempt: int = 1, max_attempts: int = 4) -> int:
    """Use httpx to probe the data service."""
    svc_resp = httpx.get(
        url,
        headers={"apikey": apikey},
    )
    svc = "FHIR" if is_fhir else "S3"
    if svc_resp.status_code != 200:
        # Sometimes it takes a bit for kong to finish creating a route/service
        if svc_resp.status_code == status.HTTP_404_NOT_FOUND and attempt <= max_attempts:
            time.sleep(attempt)  # Wait a little longer each attempt
            return probe_data_service(url=url, apikey=apikey, is_fhir=is_fhir, attempt=attempt + 1)

        logger.error(f"Unable to connect to data service after {attempt - 1} attempt(s)")
        if svc_resp.status_code == status.HTTP_403_FORBIDDEN and not is_fhir:
            raise BucketError

        elif svc_resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            raise KongServiceError(server_type=svc)

        elif svc_resp.status_code == status.HTTP_404_NOT_FOUND and is_fhir:
            raise FhirEndpointError

        elif svc_resp.status_code == status.HTTP_502_BAD_GATEWAY:
            raise KongGatewayError(server_type=svc)

        else:
            raise HTTPException(
                status_code=svc_resp.status_code,
                detail={
                    "message": svc_resp.text,
                    "service": "Kong",
                    "status_code": svc_resp.status_code,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

    logger.info(f"Successfully able to reach data service after {attempt} attempt(s)")
    return status.HTTP_200_OK
