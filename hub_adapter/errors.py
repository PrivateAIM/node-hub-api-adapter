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


class ProxyError(HTTPException):
    pass


class HubTimeoutError(HTTPException):
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


def catch_hub_errors(f):
    """Custom error handling decorator for flame_hub_client."""

    @functools.wraps(f)
    async def inner(*args, **kwargs):
        svc = "Hub"
        try:
            return await f(*args, **kwargs)

        except httpx.ProxyError as e:
            err = "Proxy Error - Unable to contact the Hub"
            logger.error(err)
            raise ProxyError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": err,
                    "service": "proxy",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        except HubAPIError as err:
            resp_error = err.error_response

            if type(resp_error) is httpx.ConnectTimeout:
                err = "Connection Timeout - Hub is currently unreachable"
                logger.error(err)
                raise HubTimeoutError(
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
                raise HubConnectError(
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
            if e.status == status.HTTP_409_CONFLICT:
                err = "Kong consumer conflict"
                logger.error(err)
                raise KongConflictError(
                    status_code=e.status,
                    detail={
                        "message": err,
                        "service": svc,
                        "status_code": e.status,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

            elif e.status == status.HTTP_404_NOT_FOUND:
                logger.error("Kong service not found")
                raise KongConnectError(
                    status_code=e.status,
                    detail={
                        "message": e.reason,
                        "service": svc,
                        "status_code": e.status,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

            else:
                logger.error(f"Kong error: {e}")
                raise KongError(
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
            raise KongTimeoutError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Kong service unavailable",
                    "service": svc,
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

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
