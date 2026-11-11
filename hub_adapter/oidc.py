"""Collection of methods related to gathering OIDC configurations."""

import logging
import time
from functools import lru_cache

import httpx2
from fastapi import HTTPException
from starlette import status

from hub_adapter.dependencies import get_idp_client, get_settings
from hub_adapter.schemas.conf import OIDCConfiguration

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def fetch_openid_config(
    oidc_url: str,
    max_retries: int = 6,
    wait_interval: int = 10,
) -> OIDCConfiguration:
    """Fetch the openid configuration from the provided URL. Tries until it reaches max_retries."""
    provided_url = oidc_url
    if not oidc_url.endswith(".well-known/openid-configuration"):
        oidc_url = oidc_url.rstrip("/") + "/.well-known/openid-configuration"

    attempt_num = 0
    while attempt_num <= max_retries:
        try:
            response = get_idp_client().get(oidc_url)
            response.raise_for_status()
            return OIDCConfiguration(**response.json())

        except (httpx2.ConnectError, httpx2.ReadTimeout):  # OIDC Service is not up yet
            attempt_num += 1
            wait_time = wait_interval * (2 ** (attempt_num - 1))  # 10s, 20s, 40s, 80s, 160s, 320s
            logger.warning(f"Unable to contact the IDP at {oidc_url}, retrying in {wait_time} seconds")
            time.sleep(wait_time)

        except httpx2.HTTPStatusError as e:
            err_msg = (
                f"HTTP error occurred while trying to contact the IDP: {provided_url}, is this the correct issuer URL? "
                f"If behind a proxy, check if '.cluster.local' is in your noProxy values."
            )
            logger.error(err_msg + f" - {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": err_msg,
                    "service": "Auth",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
            ) from e

    logger.error(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")
    raise httpx2.ConnectError(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")


def get_oidc_config() -> OIDCConfiguration:
    """Lazy-load the IDP's OIDC configuration when first needed."""
    return fetch_openid_config(get_settings().idp_url)
