import logging
from typing import Annotated

import kubernetes.client
from fastapi import APIRouter, Path, Security

from gateway.auth import oauth2_scheme
from gateway.conf import gateway_settings

k8s_router = APIRouter(
    dependencies=[Security(oauth2_scheme)],
    tags=["PodOrc"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)


def initialize_k8s_api_conn():  # Convert to decorator for each EP?
    """Create an API client for the K8s instance."""
    # K8s init
    k8s_conf = kubernetes.client.Configuration()
    k8s_conf.api_key["authorization"] = gateway_settings.K8S_API_KEY
    k8s_conf.host = gateway_settings.PODORC_SERVICE_URL
    kubernetes.client.Configuration.set_default(k8s_conf)

    api_client = kubernetes.client.CoreV1Api()
    return api_client


@k8s_router.get("/namespaces", response_model=list[str])
async def get_namespaces():
    """List available namespaces."""
    k8s_api = initialize_k8s_api_conn()
    resp = k8s_api.list_namespace().to_dict()
    ns = {namespace["metadata"]["name"] for namespace in resp["items"]}
    return ns


@k8s_router.get("/pods/{namespace}")
async def get_k8s_pods_by_namespace(namespace: Annotated[str, Path(title="Namespace to query")], ):
    """Get a list of k8s pods for a given namespace."""
    k8s_api = initialize_k8s_api_conn()
    # TODO improve output and limit requested information
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md
    return k8s_api.list_namespaced_pod(namespace=namespace).to_dict()


@k8s_router.get("/svc/{namespace}")
async def get_k8s_svc_by_namespace(namespace: Annotated[str, Path(title="Namespace to query")], ):
    """Get a list of k8s services for a given namespace."""
    k8s_api = initialize_k8s_api_conn()
    # TODO improve output and limit requested information
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md
    return k8s_api.list_namespaced_service(namespace=namespace).to_dict()
