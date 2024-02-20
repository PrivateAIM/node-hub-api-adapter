import logging

import kubernetes.client
from fastapi import APIRouter

from gateway.conf import gateway_settings

k8s_router = APIRouter()
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


@k8s_router.get("/pods")
async def get_k8s_pods():
    """Get a list of k8s pods."""
    k8s_api = initialize_k8s_api_conn()
    # TODO improve output and limit requested information
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md
    return k8s_api.list_pod_for_all_namespaces().to_dict()
