from __future__ import annotations

import os
from pathlib import Path

from kubernetes import client, config as k8s_config
from kubernetes.client import ApiClient

from .config import config

_LOADED = False
_API_CLIENT: ApiClient | None = None

SERVICEACCOUNT_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
SERVICEACCOUNT_CA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
SERVICEACCOUNT_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def _load_direct_incluster_client() -> ApiClient:
    host = os.getenv("KUBERNETES_SERVICE_HOST")
    port = os.getenv("KUBERNETES_SERVICE_PORT", "443")
    if not host:
        raise RuntimeError("KUBERNETES_SERVICE_HOST is not set; cannot use in_cluster auth.")
    if not SERVICEACCOUNT_TOKEN_PATH.exists():
        raise RuntimeError(f"ServiceAccount token not found at {SERVICEACCOUNT_TOKEN_PATH}.")

    token = SERVICEACCOUNT_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"ServiceAccount token at {SERVICEACCOUNT_TOKEN_PATH} is empty.")

    client_config = client.Configuration()
    client_config.host = f"https://{host}:{port}"
    client_config.api_key = {"authorization": token, "BearerToken": token}
    client_config.api_key_prefix = {"authorization": "Bearer", "BearerToken": "Bearer"}
    if SERVICEACCOUNT_CA_PATH.exists():
        client_config.ssl_ca_cert = str(SERVICEACCOUNT_CA_PATH)
        client_config.verify_ssl = True

    api_client = ApiClient(client_config)
    # Be explicit for Kubernetes deployments: every request must carry the pod
    # ServiceAccount token. This avoids anonymous API calls if generated-client
    # auth settings are not applied by a specific API path.
    api_client.default_headers["Authorization"] = f"Bearer {token}"
    return api_client


def load_kubernetes_config() -> ApiClient:
    global _API_CLIENT, _LOADED
    if _LOADED and _API_CLIENT is not None:
        return _API_CLIENT

    if config.k8s_auth_mode == "kubeconfig":
        client_config = client.Configuration()
        k8s_config.load_kube_config(
            config_file=config.kubeconfig_path,
            context=config.kubeconfig_context,
            client_configuration=client_config,
        )
        _API_CLIENT = ApiClient(client_config)
    else:
        _API_CLIENT = _load_direct_incluster_client()
    client.Configuration.set_default(_API_CLIENT.configuration)
    _LOADED = True
    return _API_CLIENT


def core_v1() -> client.CoreV1Api:
    return client.CoreV1Api(load_kubernetes_config())


def apps_v1() -> client.AppsV1Api:
    return client.AppsV1Api(load_kubernetes_config())


def batch_v1() -> client.BatchV1Api:
    return client.BatchV1Api(load_kubernetes_config())


def networking_v1() -> client.NetworkingV1Api:
    return client.NetworkingV1Api(load_kubernetes_config())


def api_client() -> ApiClient:
    return load_kubernetes_config()


def auth_diagnostics() -> dict[str, object]:
    """Return non-secret Kubernetes auth diagnostics for health checks."""
    return {
        "auth_mode": config.k8s_auth_mode,
        "in_cluster_host_present": bool(os.getenv("KUBERNETES_SERVICE_HOST")),
        "serviceaccount_token_present": SERVICEACCOUNT_TOKEN_PATH.exists(),
        "serviceaccount_token_readable": os.access(SERVICEACCOUNT_TOKEN_PATH, os.R_OK),
        "serviceaccount_ca_present": SERVICEACCOUNT_CA_PATH.exists(),
        "serviceaccount_namespace_present": SERVICEACCOUNT_NAMESPACE_PATH.exists(),
        "direct_incluster_client": config.k8s_auth_mode != "kubeconfig",
        "kubernetes_service_port": os.getenv("KUBERNETES_SERVICE_PORT"),
        "kubernetes_client_bearer_auth_configured": _client_bearer_auth_configured(),
        "kubernetes_client_authorization_header_configured": _client_authorization_header_configured(),
    }


def _client_bearer_auth_configured() -> bool:
    if _API_CLIENT is None:
        return False
    auth_settings = _API_CLIENT.configuration.auth_settings()
    bearer = auth_settings.get("BearerToken") or {}
    return bearer.get("key") == "authorization" and str(bearer.get("value", "")).startswith("Bearer ")


def _client_authorization_header_configured() -> bool:
    if _API_CLIENT is None:
        return False
    return str(_API_CLIENT.default_headers.get("Authorization", "")).startswith("Bearer ")
