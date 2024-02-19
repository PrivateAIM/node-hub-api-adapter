import kubernetes.client

from gateway.conf import gateway_settings


def initialize_k8s_api_conn():  # Convert to decorator for each EP?
    """Create an API client for the K8s instance."""
    # K8s init
    k8s_conf = kubernetes.client.Configuration()
    k8s_conf.api_key["authorization"] = gateway_settings.K8S_API_KEY
    k8s_conf.host = gateway_settings.PODORC_SERVICE_URL
    kubernetes.client.Configuration.set_default(k8s_conf)

    api_client = kubernetes.client.CoreV1Api()
    return api_client
