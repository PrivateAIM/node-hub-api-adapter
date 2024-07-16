"""EPs for the kong service."""
import logging
import uuid
from typing import Annotated

import kong_admin_client
from fastapi import APIRouter, HTTPException, Body, Path, Query, Security
from kong_admin_client import CreateServiceRequest, Service, CreateRouteRequest, CreatePluginForConsumerRequest, \
    CreateConsumerRequest, CreateAclForConsumerRequest, CreateKeyAuthForConsumerRequest
from kong_admin_client.rest import ApiException
from starlette import status

from hub_adapter.auth import verify_idp_token, idp_oauth2_scheme_pass, httpbearer
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.models.kong import ServiceRequest, HttpMethodCode, ProtocolCode, LinkDataStoreProject, \
    Disconnect, LinkProjectAnalysis, ListRoutes, ListServices

kong_router = APIRouter(
    dependencies=[Security(verify_idp_token), Security(idp_oauth2_scheme_pass), Security(httpbearer)],
    tags=["Kong"],
    responses={404: {"description": "Not found"}},
    prefix="/kong"
)

logger = logging.getLogger(__name__)
kong_admin_url = hub_adapter_settings.KONG_ADMIN_SERVICE_URL


@kong_router.get("/datastore", response_model=ListServices, status_code=status.HTTP_200_OK)
async def list_data_stores(
        detailed: Annotated[bool, Query(description="Whether to include detailed information on projects")] = False,
):
    """List all available data stores (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            service_api_instance = kong_admin_client.ServicesApi(api_client)
            services = service_api_instance.list_service()

            if detailed:
                service_dicts = [svc.to_dict() for svc in services.data]
                route_api_instance = kong_admin_client.RoutesApi(api_client)
                routes = route_api_instance.list_route()
                route_dict = {rte.service.id: rte for rte in routes.data if rte.service}

                for idx, svc in enumerate(service_dicts):
                    svc_id = svc.get("id")
                    svc["routes"] = []
                    if svc_id in route_dict:
                        svc["routes"].append(route_dict[svc_id])

                    service_dicts[idx] = svc

                services = {"data": service_dicts}

            return services

    except ApiException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service error",
            headers={"WWW-Authenticate": "Bearer"},
        )


@kong_router.delete("/datastore/{data_store_name}", status_code=status.HTTP_200_OK)
async def delete_data_store(
        data_store_name: Annotated[str, Path(description="Unique name of the data store.")]
):
    """Delete the listed data store (referred to as services by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.ServicesApi(api_client)
            api_instance.delete_service(service_id_or_name=data_store_name)

            logger.info(f"Data store {data_store_name} deleted")

            return status.HTTP_200_OK

    except ApiException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@kong_router.post("/datastore", response_model=Service, status_code=status.HTTP_201_CREATED)
async def create_data_store(
        data: Annotated[ServiceRequest, Body(
            description="Required information for creating a new data store.",
            title="Data store metadata."
        )]
):
    """Create a datastore (referred to as services by kong) by providing necessary metadata."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.ServicesApi(api_client)
            create_service_request = CreateServiceRequest(
                host=data.host,
                path=data.path,
                port=data.port,
                protocol=data.protocol,
                name=data.name,
                enabled=data.enabled,
                tls_verify=data.tls_verify,
                tags=data.tags,
            )
            api_response = api_instance.create_service(create_service_request)
            return api_response

    except ApiException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@kong_router.get("/project", response_model=ListRoutes, status_code=status.HTTP_200_OK)
async def list_projects(
        project_id: Annotated[uuid.UUID | None, Query(description="UUID of project.")] = None,
        detailed: Annotated[bool, Query(description="Whether to include detailed information on data stores")] = False,
):
    """List all projects (referred to as routes by kong) available, can be filtered by project_id.

    Set "detailed" to True to include detailed information on the linked data stores.
    """
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    project = str(project_id) if project_id else None

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.RoutesApi(api_client)
            api_response = api_instance.list_route(tags=project)

            for route in api_response.data:
                logger.info(f"Project {project_id} connected to data store id: {route.service.id}")

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
                    if service_id in service_dict.keys():
                        route_data["service"] = service_dict[service_id]

                    annotated_routes.append(route_data)

                api_response = {"data": annotated_routes}

            return api_response

    except ApiException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@kong_router.post("/project", response_model=LinkDataStoreProject)
async def create_and_connect_project_to_datastore(
        data_store_id: Annotated[uuid.UUID, Body(description="UUID of the data store or 'gateway'")],
        project_id: Annotated[uuid.UUID, Body(description="UUID of the project")],
        methods: Annotated[
            list[HttpMethodCode],
            Body(description="List of acceptable HTTP methods")
        ] = ["GET", "POST", "PUT", "DELETE"],
        protocols: Annotated[
            list[ProtocolCode],
            Body(description="List of acceptable transfer protocols. A combo of 'http', 'grpc', 'grpcs', 'tls', 'tcp'")
        ] = ["http"],
        ds_type: Annotated[str, Body(description="Data store type. Either 's3' or 'fhir'")] = "fhir",
):
    """Connect a project to a data store (referred to as a route by kong)."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    response = {}

    # Construct path from project_id and type
    path = f"/{project_id}/{ds_type}"
    name = f"{project_id}-{ds_type}"
    project = str(project_id)

    # Add route
    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.RoutesApi(api_client)
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
            api_response = api_instance.create_route_for_service(
                str(data_store_id), create_route_request
            )
            route_id = api_response.id
            response["route"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Add key-auth plugin
    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.PluginsApi(api_client)
            create_route_request = CreatePluginForConsumerRequest(
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
            api_response = api_instance.create_plugin_for_route(
                route_id, create_route_request
            )
            response["keyauth"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Add acl plugin
    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.PluginsApi(api_client)
            create_route_request = CreatePluginForConsumerRequest(
                name="acl",
                instance_name=f"{project}-{ds_type}-acl",
                config={"allow": [project], "hide_groups_header": True},
                enabled=True,
                protocols=protocols,
            )
            api_response = api_instance.create_plugin_for_route(
                route_id, create_route_request
            )
            response["acl"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return response


@kong_router.put("/project/disconnect/{project_id}", status_code=status.HTTP_200_OK, response_model=Disconnect)
async def disconnect_project(
        project_id: Annotated[uuid.UUID, Path(description="UUID of project to be disconnected")]
):
    """Disconnect a project from all connected data stores (i.e. delete the "route")."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    project = str(project_id) if project_id else None

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.RoutesApi(api_client)
            api_response = api_instance.list_route(tags=project)
            removed_routes = []
            for route in api_response.data:
                # Delete route
                try:
                    api_instance = kong_admin_client.RoutesApi(api_client)
                    api_instance.delete_route(route.id)
                    logger.info(
                        f"Project {project_id} disconnected from data store {route.service.id}"
                    )
                    removed_routes.append(route.id)

                except ApiException as e:
                    raise HTTPException(
                        status_code=e.status,
                        detail=str(e),
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Service error: {e}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            return {"removed_routes": removed_routes, "status": status.HTTP_200_OK}

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@kong_router.post("/analysis", response_model=LinkProjectAnalysis, status_code=status.HTTP_202_ACCEPTED)
async def create_and_connect_analysis_to_project(
        project_id: Annotated[str, Body(description="UUID or name of the project")],
        analysis_id: Annotated[str, Body(description="UUID or name of the analysis")],
):
    """Create a new analysis and link it to a project."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)
    response = {}

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.ConsumersApi(api_client)
            api_response = api_instance.create_consumer(
                CreateConsumerRequest(
                    username=analysis_id,
                    custom_id=analysis_id,
                    tags=[str(project_id)],
                )
            )
            logger.info(f"Consumer added, id: {api_response.id}")

            consumer_id = api_response.id
            response["consumer"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Configure acl plugin for consumer
    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.ACLsApi(api_client)
            api_response = api_instance.create_acl_for_consumer(
                consumer_id,
                CreateAclForConsumerRequest(
                    group=project_id,
                    tags=[str(project_id)],
                ),
            )
            logger.info(
                f"ACL plugin configured for consumer, group: {api_response.group}"
            )
            response["acl"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Configure key-auth plugin for consumer
    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.KeyAuthsApi(api_client)
            api_response = api_instance.create_key_auth_for_consumer(
                consumer_id,
                CreateKeyAuthForConsumerRequest(
                    tags=[str(project_id)],
                ),
            )
            logger.info(
                f"Key authentication plugin configured for consumer, api_key: {api_response.key}"
            )
            response["keyauth"] = api_response

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return response


@kong_router.delete("/analysis/{analysis_id}", status_code=status.HTTP_200_OK)
async def delete_analysis(
        analysis_id: Annotated[str, Path(description="UUID or unique name of the analysis.")]
):
    """Delete the listed analysis."""
    configuration = kong_admin_client.Configuration(host=kong_admin_url)

    try:
        with kong_admin_client.ApiClient(configuration) as api_client:
            api_instance = kong_admin_client.ConsumersApi(api_client)
            api_instance.delete_consumer(consumer_username_or_id=analysis_id)

            logger.info(f"Analysis {analysis_id} deleted")

            return status.HTTP_200_OK

    except ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
