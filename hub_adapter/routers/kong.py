"""EPs for the kong service."""

import logging
import uuid
from typing import Annotated

import kong_admin_client
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security
from kong_admin_client import (
    CreateAclForConsumerRequest,
    CreateConsumerRequest,
    CreateKeyAuthForConsumerRequest,
    CreatePluginForConsumerRequest,
    CreateRouteRequest,
    CreateServiceRequest,
    Service,
)
from starlette import status

from hub_adapter.auth import httpbearer, idp_oauth2_scheme_pass, verify_idp_token
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.errors import catch_kong_errors
from hub_adapter.models.kong import (
    DeleteProject,
    HttpMethodCode,
    LinkDataStoreProject,
    LinkProjectAnalysis,
    ListConsumers,
    ListRoutes,
    ListServices,
    ProtocolCode,
    ServiceRequest,
)

kong_router = APIRouter(
    dependencies=[
        Security(verify_idp_token),
        Security(idp_oauth2_scheme_pass),
        Security(httpbearer),
    ],
    tags=["Kong"],
    responses={404: {"description": "Not found"}},
    prefix="/kong",
)

logger = logging.getLogger(__name__)
kong_admin_url = hub_adapter_settings.KONG_ADMIN_SERVICE_URL
realm = hub_adapter_settings.IDP_REALM


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


@kong_router.get("/datastore", response_model=ListServices, status_code=status.HTTP_200_OK)
@catch_kong_errors
async def list_data_stores(
    detailed: Annotated[bool, Query(description="Whether to include detailed information on projects")] = False,
):
    """List all available data stores (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    with kong_admin_client.ApiClient(configuration) as api_client:
        service_api_instance = kong_admin_client.ServicesApi(api_client)
        services = service_api_instance.list_service()

        if detailed:
            services = parse_project_info(services, api_client)

        return services


@kong_router.get(
    "/datastore/{data_store_name}",
    response_model=ListServices,
    status_code=status.HTTP_200_OK,
)
@catch_kong_errors
async def list_specific_data_store(
    data_store_name: Annotated[str | None, Path(description="Unique name of the data store.")],
    detailed: Annotated[bool, Query(description="Whether to include detailed information on projects")] = False,
):
    """List all available data stores (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    with kong_admin_client.ApiClient(configuration) as api_client:
        service_api_instance = kong_admin_client.ServicesApi(api_client)
        services = service_api_instance.list_service(tags=data_store_name)

        if detailed:
            services = parse_project_info(services, api_client)

        return services


@kong_router.delete("/datastore/{data_store_name}", status_code=status.HTTP_200_OK)
@catch_kong_errors
async def delete_data_store(data_store_name: Annotated[str, Path(description="Unique name of the data store.")]):
    """Delete the listed data store (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    # Delete related projects and analyses first, data_store_name is same as associated project in kong (route)
    # {ProjectUUID}-{datastore type}
    await delete_route(project_route_id=data_store_name)

    # Delete data store
    with kong_admin_client.ApiClient(configuration) as api_client:
        svc_api = kong_admin_client.ServicesApi(api_client)

        # Can't delete by svc name so have to get svc ID
        svc = svc_api.get_service(service_id_or_name=data_store_name)
        svc_api.delete_service(service_id_or_name=svc.id)

        logger.info(f"Data store {svc.id} deleted")

        return status.HTTP_200_OK


@catch_kong_errors
async def create_service(
    datastore: Annotated[
        ServiceRequest,
        Body(
            description="Required information for creating a new data store.",
            title="Data store metadata.",
        ),
    ],
    ds_type: Annotated[str, Body(description="Data store type. Either 's3' or 'fhir'")],
) -> Service:
    """Create a datastore (referred to as services by kong) by providing necessary metadata."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    datastore_name = f"{datastore.name}-{ds_type}"

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
        api_response = api_instance.create_service(create_service_request)
        return api_response


@kong_router.post(
    "/datastore",
    response_model=Service,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(create_service)],
)
async def create_data_store():
    """Create a datastore (referred to as services by kong) by providing necessary metadata."""
    return status.HTTP_201_CREATED


@catch_kong_errors
async def list_projects(
    project_id: Annotated[uuid.UUID | str | None, Query(description="UUID of project.")] = None,
    detailed: Annotated[
        bool,
        Query(description="Whether to include detailed information on data stores"),
    ] = False,
):
    """List all projects (referred to as routes by kong) available, can be filtered by project_id.

    Set "detailed" to True to include detailed information on the linked data stores.
    """
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    project = str(project_id) if project_id else None

    with kong_admin_client.ApiClient(configuration) as api_client:
        api_instance = kong_admin_client.RoutesApi(api_client)
        api_response = api_instance.list_route(tags=project)

        if len(api_response.data) == 0:
            logger.info("No routes found.")

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
)
async def get_projects(projects: Annotated[ListRoutes, Depends(list_projects)]):
    """List all projects (referred to as routes by kong) available, can be filtered by project_id.

    Set "detailed" to True to include detailed information on the linked data stores.
    """
    return projects


@catch_kong_errors
async def create_route_to_datastore(
    data_store_id: Annotated[uuid.UUID | str, Body(description="UUID of the data store or 'service'")],
    project_id: Annotated[uuid.UUID | str, Body(description="UUID of the project")],
    methods: Annotated[list[HttpMethodCode], Body(description="List of acceptable HTTP methods")] = ["GET"],
    protocols: Annotated[
        list[ProtocolCode],
        Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
    ] = ["http"],
    ds_type: Annotated[str, Body(description="Data store type. Either 's3' or 'fhir'")] = "fhir",
):
    """Connect a project to a data store (referred to as a route by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    # Construct path from project_id and type
    path = f"/{project_id}/{ds_type}"
    name = f"{project_id}-{ds_type}"
    project = str(project_id)

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
    "/project",
    response_model=LinkDataStoreProject,
)
async def create_project_and_connect_to_datastore(
    proj_link_response: Annotated[LinkDataStoreProject, Depends(create_route_to_datastore)],
):
    """Connect a project (referred to as a route by kong) to an existing data store."""
    return proj_link_response


@kong_router.post(
    "/initialize",
    response_model=LinkDataStoreProject,
)
async def create_datastore_and_project_with_link(
    datastore: Annotated[Service, Depends(create_service)],
    project_id: Annotated[uuid.UUID, Body(description="UUID of the project")],
    methods: Annotated[list[HttpMethodCode], Body(description="List of acceptable HTTP methods")] = ["GET"],
    protocols: Annotated[
        list[ProtocolCode],
        Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'"),
    ] = ["http"],
    ds_type: Annotated[str, Body(description="Data store type. Either 's3' or 'fhir'")] = "fhir",
):
    """Creates a new datastore (service) and a new project (route), then links them together."""
    proj_response = await create_route_to_datastore(
        project_id=project_id,
        data_store_id=datastore.id,
        methods=methods,
        protocols=protocols,
        ds_type=ds_type,
    )
    return proj_response


@catch_kong_errors
async def delete_route(
    project_route_id: Annotated[str, Path(description="Unique identifier of the project to be deleted")],
) -> DeleteProject:
    """Disconnect a project (route) from all data stores (services) and delete associated analyses (consumers)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
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


@kong_router.delete(
    "/project/{project_id}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteProject,
)
async def delete_project(proj_delete_response: Annotated[DeleteProject, Depends(delete_route)]):
    return proj_delete_response


@kong_router.get(
    "/analysis",
    response_model=ListConsumers,
    status_code=status.HTTP_200_OK,
)
@catch_kong_errors
async def get_analyses(
    analysis_id: Annotated[uuid.UUID | str | None, Query(description="UUID of the analysis.")] = None,
    tag: Annotated[str | None, Query(description="Tag to filter by e.g. project ID")] = None,
):
    """List all analyses (referred to as consumers by kong) available, can be filtered by analysis_id."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    username = f"{analysis_id}-{realm}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)
        if analysis_id:
            api_response = consumer_api.get_consumer(consumer_username_or_id=username)
            api_response = {"data": [api_response]}

        else:
            api_response = consumer_api.list_consumer(tags=tag)

        return api_response


@kong_router.post(
    "/analysis",
    response_model=LinkProjectAnalysis,
    status_code=status.HTTP_201_CREATED,
)
@catch_kong_errors
async def create_and_connect_analysis_to_project(
    project_id: Annotated[str, Body(description="UUID or name of the project")],
    analysis_id: Annotated[str, Body(description="UUID or name of the analysis")],
):
    """Create a new analysis and link it to a project."""
    proj_resp = await list_projects(project_id=project_id, detailed=False)

    # Tags are used to annotate routes (projects) with datastore type and original project ID
    route_tags = set()
    for proj in proj_resp.data:
        route_tags.update(proj.tags)

    # UUID must be cast to str to check in set since tags are strings
    if project_id not in route_tags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated project not mapped to a data store",
            headers={"WWW-Authenticate": "Bearer"},
        )

    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    response = {}
    username = f"{analysis_id}-{realm}"

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


@kong_router.delete("/analysis/{analysis_id}", status_code=status.HTTP_200_OK)
@catch_kong_errors
async def delete_analysis(analysis_id: Annotated[str, Path(description="UUID or unique name of the analysis.")]):
    """Delete the listed analysis."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    username = f"{analysis_id}-{realm}"

    with kong_admin_client.ApiClient(configuration) as api_client:
        consumer_api = kong_admin_client.ConsumersApi(api_client)

        consumer_api.delete_consumer(consumer_username_or_id=username)

        logger.info(f"Analysis {analysis_id} deleted")
        return status.HTTP_200_OK
