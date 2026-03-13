"""Collection of methods related to gathering OIDC configurations."""

import logging
import time
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import HTTPException
from starlette import status

from hub_adapter.dependencies import get_settings
from hub_adapter.schemas.conf import OIDCConfiguration

logger = logging.getLogger(__name__)

# Fields in OIDCConfiguration that are network endpoints (issuer excluded — it is used for comparison only)
_OIDC_ENDPOINT_FIELDS = ("token_endpoint", "jwks_uri", "authorization_endpoint", "userinfo_endpoint")


def _rewrite_url_origin(url: str, origin_url: str):
    """Replace the scheme and host of *url* with those from *origin_url*."""
    parsed = urlparse(url)
    origin = urlparse(origin_url)
    swapped = parsed._replace(scheme=origin.scheme, netloc=origin.netloc)
    return urlunparse(swapped)


@lru_cache(maxsize=4)
def fetch_openid_config(
    oidc_url: str,
    max_retries: int = 6,
    wait_interval: int = 10,
    rewrite_endpoints: bool = False,
) -> OIDCConfiguration:
    """Fetch the openid configuration from the OIDC URL. Tries until it reaches max_retries.

    When *rewrite_endpoints* is True the scheme and host of all endpoint URLs returned by
    the IDP are replaced with those from *oidc_url*.  This is required when the IDP advertises
    its ingress hostname in the openid-configuration but only the k8s service URL is reachable
    (e.g. because a network policy blocks the ingress domain).
    """
    provided_url = oidc_url
    if not oidc_url.endswith(".well-known/openid-configuration"):
        oidc_url = oidc_url.rstrip("/") + "/.well-known/openid-configuration"

    attempt_num = 0
    while attempt_num <= max_retries:
        try:
            response = httpx.get(oidc_url)

            response.raise_for_status()
            oidc_config = response.json()

            if rewrite_endpoints:
                for field in _OIDC_ENDPOINT_FIELDS:
                    if field in oidc_config:
                        oidc_config[field] = _rewrite_url_origin(oidc_config[field], provided_url)

            return OIDCConfiguration(**oidc_config)

        except (httpx.ConnectError, httpx.ReadTimeout):  # OIDC Service is not up yet
            attempt_num += 1
            wait_time = wait_interval * (2 ** (attempt_num - 1))  # 10s, 20s, 40s, 80s, 160s, 320s
            logger.warning(f"Unable to contact the IDP at {oidc_url}, retrying in {wait_time} seconds")
            time.sleep(wait_time)

        except httpx.HTTPStatusError as e:
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
    raise httpx.ConnectError(f"Unable to contact the IDP at {oidc_url} after {max_retries} retries")


def get_user_oidc_config() -> OIDCConfiguration:
    """Lazy-load the user OIDC configuration when first needed."""
    settings = get_settings()
    return fetch_openid_config(settings.idp_url)


def get_svc_oidc_config() -> OIDCConfiguration:
    """Lazy-load the service OIDC configuration when first needed."""
    settings = get_settings()
    # Services always use internal IDP
    if settings.node_svc_oidc_url != settings.idp_url:
        # Rewrite endpoint origins so they use the k8s service URL rather than any ingress domain
        # that the IDP may advertise in its openid-configuration.
        return fetch_openid_config(settings.node_svc_oidc_url, rewrite_endpoints=True)
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
