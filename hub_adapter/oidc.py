"""Collection of methods related to gathering OIDC configurations."""

import logging
import time
from functools import lru_cache

import httpx
from fastapi import HTTPException
from starlette import status

from hub_adapter.dependencies import get_settings
from hub_adapter.models.conf import OIDCConfiguration

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def fetch_openid_config(
    oidc_url: str,
    max_retries: int = 6,
) -> OIDCConfiguration:
    """Fetch the openid configuration from the OIDC URL. Tries until it reaches max_retries."""
    provided_url = oidc_url
    if not oidc_url.endswith(".well-known/openid-configuration"):
        oidc_url = oidc_url.rstrip("/") + "/.well-known/openid-configuration"

    attempt_num = 0
    while attempt_num <= max_retries:
        try:
            response = httpx.get(oidc_url)

            response.raise_for_status()
            oidc_config = response.json()
            return OIDCConfiguration(**oidc_config)

        except (httpx.ConnectError, httpx.ReadTimeout):  # OIDC Service not up yet
            attempt_num += 1
            wait_time = 10 * (2 ** (attempt_num - 1))  # 10s, 20s, 40s, 80s, 160s, 320s
            logger.warning(f"Unable to contact the IDP at {oidc_url}, retrying in {wait_time} seconds")
            time.sleep(wait_time)

        except httpx.HTTPStatusError as e:
            err_msg = (
                f"HTTP error occurred while trying to contact the IDP: {provided_url}, is this the correct issuer URL?"
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
    raise httpx.ConnectError(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")


def get_user_oidc_config() -> OIDCConfiguration:
    """Lazy-load the user OIDC configuration when first needed."""
    settings = get_settings()
    return fetch_openid_config(settings.IDP_URL)


def get_svc_oidc_config() -> OIDCConfiguration:
    """Lazy-load the service OIDC configuration when first needed."""
    settings = get_settings()
    # Services always use internal IDP
    if settings.NODE_SVC_OIDC_URL != settings.IDP_URL:
        return fetch_openid_config(settings.NODE_SVC_OIDC_URL)
    else:
        return get_user_oidc_config()


def check_oidc_configs_match() -> tuple[bool, OIDCConfiguration]:
    """Check whether the user and svc OIDC configurations match and return the check (bool) and the svc OIDC
    configuration if different otherwise the user configuration."""
    user_oidc_config = get_user_oidc_config()
    svc_oidc_config = get_svc_oidc_config()

    if user_oidc_config.issuer != svc_oidc_config.issuer:
        return False, svc_oidc_config
    else:
        return True, user_oidc_config
