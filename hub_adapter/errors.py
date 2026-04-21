"""Router specific error decorators."""

import functools
import logging

import httpx
import pydantic
from fastapi import HTTPException
from flame_hub import HubAPIError
from kong_admin_client import ApiException
from starlette import status
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
                SERVICE: "MinIO",
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
        log_event(
            "storage.bucket.forbidden",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            service="MinIO",
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
            headers={"WWW-Authenticate": "Bearer"},
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
            headers={"WWW-Authenticate": "Bearer"},
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
            headers={"WWW-Authenticate": "Bearer"},
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
            headers={"WWW-Authenticate": "Bearer"},
        )
        log_event(
            "kong.consumer.api_key.not_found",
            event_description=message,
            level=logging.ERROR,
            status_code=status.HTTP_404_NOT_FOUND,
            service="Kong",
        )


def catch_hub_errors(f):
    """Custom error handling decorator for flame_hub_client."""

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Hub"
        try:
            return await f(*args, **kwargs)

        except httpx.ProxyError as e:
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
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except httpx.ReadTimeout as e:
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
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except httpx.ConnectError as e:
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
                headers={"WWW-Authenticate": "Bearer"},
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
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except HubAPIError as err:
            resp_error = err.error_response

            if type(resp_error) is httpx.ConnectTimeout:
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
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err

            elif type(resp_error) is httpx.ConnectError:
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
                    headers={"WWW-Authenticate": "Bearer"},
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
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err

    return inner


def catch_kong_errors(f):
    """Custom error handling decorator for Kong endpoints."""

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Kong"
        try:
            return await f(*args, **kwargs)

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
                    headers={"WWW-Authenticate": "Bearer"},
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
                    headers={"WWW-Authenticate": "Bearer"},
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
                    headers={"WWW-Authenticate": "Bearer"},
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
                headers={"WWW-Authenticate": "Bearer"},
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
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    return inner
