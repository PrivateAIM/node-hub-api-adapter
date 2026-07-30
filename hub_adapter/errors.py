"""Router specific error decorators."""

import functools
import inspect
import logging

import httpx2
import pydantic
from fastapi import HTTPException
from flame_hub import HubAPIError
from kong_admin_client import ApiException
from starlette import status
from starlette.concurrency import run_in_threadpool
from urllib3.exceptions import MaxRetryError

from hub_adapter.constants import SERVICE
from hub_adapter.middleware import log_event


class ProxyError(HTTPException):
    pass


class HubTimeoutError(HTTPException):
    pass


class HubTypeError(HTTPException):
    pass


class HubConnectError(HTTPException):
    pass


class KongError(HTTPException):
    pass


class KongTimeoutError(HTTPException):
    pass


class KongConnectError(HTTPException):
    pass


class KongConflictError(HTTPException):
    pass


class BucketError(KongError):
    def __init__(self):
        message = "Bucket does not exist or is set to private"
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": message,
                SERVICE: "S3",
                "status_code": status.HTTP_403_FORBIDDEN,
            },
        )
        log_event(
            "storage.bucket.forbidden",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            service="S3",
        )


class KongGatewayError(KongError):
    def __init__(self, server_type: str):
        message = f"Unable to contact the {server_type} service, likely an incorrect port"
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": message,
                SERVICE: server_type,
                "status_code": status.HTTP_502_BAD_GATEWAY,
            },
        )
        log_event(
            "kong.gateway.error",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            service=server_type,
        )


class KongServiceError(KongError):
    def __init__(self, server_type: str):
        message = f"{server_type} server name resolution failed"
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": message,
                SERVICE: server_type,
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
        )
        log_event(
            "kong.service.resolution_failed",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            service=server_type,
        )


class FhirEndpointError(KongError):
    def __init__(self):
        message = "FHIR endpoint not found, check the data path"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": message,
                SERVICE: "FHIR",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )
        log_event(
            "fhir.endpoint.not_found",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="FHIR",
        )


class KongConsumerApiKeyError(KongError):
    def __init__(self):
        message = "Unable to obtain API key for health consumer"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": message,
                SERVICE: "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )
        log_event(
            "kong.consumer.api_key.not_found",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="Kong",
        )


class KongDataStoreLinkedError(KongError):
    def __init__(self, datastore: str, projects: list[str]):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Data store {datastore} is still linked to project(s): {', '.join(projects)}. "
                "Pass cascade=true to delete it along with its links.",
                "service": "Kong",
                "status_code": status.HTTP_409_CONFLICT,
            },
        )


class KongValidationError(KongError):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": message,
                "service": "Kong",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )


class KongDatastoreMissingTypeError(KongError):
    def __init__(self, datastore_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Service {datastore_id} is not a data store (missing type tag)",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongProjectDatastoreLinkConflictError(KongError):
    def __init__(self, project_id: str, datastore_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Project {project_id} is already linked to data store {datastore_id}",
                "service": "Kong",
                "status_code": status.HTTP_409_CONFLICT,
            },
        )


class KongDatastoreLinkedToOtherProjectError(KongError):
    def __init__(self, datastore_id: str, other_project_id: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"Data store {datastore_id} is already linked to project {other_project_id}. "
                    "A data store can only be linked to one project at a time, unlink it first."
                ),
                "service": "Kong",
                "status_code": status.HTTP_409_CONFLICT,
            },
        )


class KongProjectDatastoreUnlinkedError(KongError):
    def __init__(self, project_id: str, datastore_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Project {project_id} is not linked to data store {datastore_id}",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongProjectEmptyError(KongError):
    def __init__(self, project_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Project {project_id} has no linked data stores or consumers",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongDatastoreOrProjectNotFoundError(KongError):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No data store or project found matching {identifier!r}",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongAmbiguousProjectDatastoreError(KongError):
    def __init__(self, project_id: str, datastore_ids: list[str]):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Project {project_id} is linked to multiple data stores "
                f"({', '.join(datastore_ids)}); specify one directly.",
                "service": "Kong",
                "status_code": status.HTTP_409_CONFLICT,
            },
        )


class KongProjectNotMappedError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Associated project not mapped to a data store",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongAnalysisConsumerNotFoundError(KongError):
    def __init__(self, analysis_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No consumer found for analysis {analysis_id}",
                "service": "Kong",
                "status_code": status.HTTP_404_NOT_FOUND,
            },
        )


class KongProxyNotConfiguredError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Kong proxy service URL not configured",
                "service": "Kong",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )


class KongUpstreamError(KongError):
    def __init__(self, status_code: int, message: str):
        super().__init__(
            status_code=status_code,
            detail={
                "message": message,
                "service": "Kong",
                "status_code": status_code,
            },
            headers={"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None,
        )


def require_victoria_logs(f):
    """Raise HTTP 503 if VictoriaLogs is not configured."""

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        from hub_adapter.dependencies import get_settings  # avoid circular import

        if not get_settings().victoria_logs_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Log service is not configured",
            )
        return await f(*args, **kwargs)

    return inner


def catch_hub_errors(f):
    """Custom error handling decorator for flame_hub_client.

    The Hub client is synchronous, so move to a separate worker thread.
    The wrapper stays a coroutine either way, so internal callers can keep awaiting the decorated function.
    """
    is_async = inspect.iscoroutinefunction(f)

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Hub"
        try:
            return await (f(*args, **kwargs) if is_async else run_in_threadpool(f, *args, **kwargs))

        except httpx2.ProxyError as e:
            err = "Proxy Error - Unable to contact the Hub"
            log_event(
                "hub.proxy.error",
                event_description=err,
                level=logging.ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
                service="Proxy",
            )
            raise ProxyError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": err,
                    SERVICE: "proxy",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                },
            ) from e

        except httpx2.ReadTimeout as e:
            err = "ReadTimeout Error - Hub is offline or undergoing maintenance"
            log_event(
                "hub.read.timeout",
                event_description=err,
                level=logging.ERROR,
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                service=svc,
            )
            raise HubTimeoutError(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail={
                    "message": err,
                    SERVICE: svc,
                    "status_code": status.HTTP_408_REQUEST_TIMEOUT,
                },
            ) from e

        except httpx2.ConnectError as e:
            err = "ConnectError - CoreClient is unable to get token from Hub"
            log_event(
                "hub.connect.error",
                event_description=err,
                level=logging.ERROR,
                status_code=status.HTTP_404_NOT_FOUND,
                service="CoreClient",
            )
            raise HubConnectError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err,
                    SERVICE: "CoreClient",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            ) from e

        except pydantic.ValidationError as e:
            log_event(
                "hub.validation.error",
                event_description=f"Pydantic type error: {e.errors()}",
                level=logging.ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                service="CoreClient",
            )
            raise HubTypeError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "An error occurred while validating the data",
                    SERVICE: "CoreClient",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            ) from e

        except HubAPIError as err:
            resp_error = err.error_response

            if type(resp_error) is httpx2.ConnectTimeout:
                err_msg = "Connection Timeout - Hub is currently unreachable"
                log_event(
                    "hub.connection.timeout",
                    event_description=err_msg,
                    level=logging.ERROR,
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    service=svc,
                )
                raise HubTimeoutError(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail={
                        "message": err_msg,
                        SERVICE: svc,
                        "status_code": status.HTTP_408_REQUEST_TIMEOUT,
                    },
                ) from err

            elif type(resp_error) is httpx2.ConnectError:
                err_msg = "Connection Error - Hub is currently unreachable"
                log_event(
                    "hub.connection.error",
                    event_description=err_msg,
                    level=logging.ERROR,
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    service=svc,
                )
                raise HubConnectError(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "message": err_msg,
                        SERVICE: svc,
                        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                    },
                ) from err

            else:
                log_event(
                    "hub.auth.error",
                    event_description="Failed to retrieve JWT from Hub",
                    level=logging.ERROR,
                    status_code=err.error_response.status_code,
                    service=svc,
                )
                raise HTTPException(
                    status_code=err.error_response.status_code,
                    detail={
                        "message": err.error_response.message,
                        SERVICE: svc,
                        "status_code": err.error_response.status_code,
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                    if err.error_response.status_code == status.HTTP_401_UNAUTHORIZED
                    else None,
                ) from err

    return inner


def catch_kong_errors(f):
    """Custom error handling decorator for Kong endpoints.

    The Kong admin client is synchronous, so move to a separate worker thread.
    """
    is_async = inspect.iscoroutinefunction(f)

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Kong"
        try:
            return await (f(*args, **kwargs) if is_async else run_in_threadpool(f, *args, **kwargs))

        except ApiException as e:
            if e.status == status.HTTP_409_CONFLICT:
                err = "Kong consumer conflict"
                log_event(
                    "kong.consumer.conflict",
                    event_description=err,
                    level=logging.ERROR,
                    status_code=e.status,
                    service=svc,
                )
                raise KongConflictError(
                    status_code=e.status,
                    detail={
                        "message": err,
                        SERVICE: svc,
                        "status_code": e.status,
                    },
                ) from e

            elif e.status == status.HTTP_404_NOT_FOUND:
                log_event(
                    "kong.service.not_found",
                    event_description="Kong service not found",
                    level=logging.ERROR,
                    status_code=e.status,
                    service=svc,
                )
                raise KongConnectError(
                    status_code=e.status,
                    detail={
                        "message": e.reason,
                        SERVICE: svc,
                        "status_code": e.status,
                    },
                ) from e

            else:
                log_event(
                    "kong.api.error",
                    event_description=f"Kong error: {e}",
                    level=logging.ERROR,
                    status_code=e.status,
                    service=svc,
                )
                raise KongError(
                    status_code=e.status,
                    detail={
                        "message": e.reason,
                        SERVICE: svc,
                        "status_code": e.status,
                    },
                    headers={"WWW-Authenticate": "Bearer"} if e.status == status.HTTP_401_UNAUTHORIZED else None,
                ) from e

        except MaxRetryError as e:
            log_event(
                "kong.service.unavailable",
                event_description="Kong service unavailable",
                level=logging.ERROR,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                service=svc,
            )
            raise KongTimeoutError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Kong service unavailable",
                    SERVICE: svc,
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
            ) from e

        except HTTPException as http_error:
            raise http_error  # Already logged at the raise site

        except Exception as e:
            log_event(
                "kong.service.error",
                event_description=f"Service error - {e}",
                level=logging.ERROR,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                service=svc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": f"Service error - {e}",
                    SERVICE: svc,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            ) from e

    return inner
