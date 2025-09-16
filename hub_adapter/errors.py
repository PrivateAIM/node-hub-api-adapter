"""Router specific error decorators."""

import functools
import logging

import httpx
from fastapi import HTTPException
from flame_hub import HubAPIError
from kong_admin_client import ApiException
from starlette import status
from urllib3.exceptions import MaxRetryError

logger = logging.getLogger(__name__)


class KongError(HTTPException):
    pass


class BucketError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Bucket does not exist or is set to private",
                "service": "MinIO",
                "status_code": status.HTTP_403_FORBIDDEN,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class KongGatewayError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Unable to contact upstream service, likely an incorrect port",
                "service": "Kong",
                "status_code": status.HTTP_502_BAD_GATEWAY,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class FhirServerError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "FHIR server name resolution failed",
                "service": "FHIR",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class FhirEndpointError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "FHIR endpoint not found, check path",
                "service": "FHIR",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class KongConsumerApiKeyError(KongError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Unable to obtain API key for health consumer",
                "service": "Kong",
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def catch_hub_errors(f):
    """Custom error handling decorator for flame_hub_client."""

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Hub"
        try:
            return await f(*args, **kwargs)

        except httpx.ProxyError:
            err = "Proxy Error - Unable to contact the Hub"
            logger.error(err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": err,
                    "service": "proxy",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        except HubAPIError as err:
            resp_error = err.error_response

            if type(resp_error) is httpx.ConnectTimeout:
                err = "Connection Timeout - Hub is currently unreachable"
                logger.error(err)
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail={
                        "message": err,
                        "service": svc,
                        "status_code": status.HTTP_408_REQUEST_TIMEOUT,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err

            elif type(resp_error) is httpx.ConnectError:
                err = "Connection Error - Hub is currently unreachable"
                logger.error(err)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "message": err,
                        "service": svc,
                        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err

            else:
                logger.error("Failed to retrieve JWT from Hub")
                logger.error(err)
                raise HTTPException(
                    status_code=err.error_response.status_code,
                    detail={  # Invalid authentication credentials
                        "message": err.error_response.message,
                        "service": svc,
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
            logger.error(f"Kong error: {e}")
            raise HTTPException(
                status_code=e.status,
                detail={
                    "message": e.reason,
                    "service": svc,
                    "status_code": e.status,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except MaxRetryError as e:
            logger.error(f"Kong error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Kong service unavailable",
                    "service": svc,
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except KongError as e:
            logger.error(f"Kong error: {e}")
            raise e

        except HTTPException as http_error:
            logger.error(f"Kong error: {http_error}")
            raise http_error

        except Exception as e:
            logger.error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": f"Service error - {e}",
                    "service": svc,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    return inner
