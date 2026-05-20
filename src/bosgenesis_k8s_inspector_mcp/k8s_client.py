from __future__ import annotations

from kubernetes import client, config as k8s_config
from kubernetes.client import ApiClient

from .config import config

_LOADED = False


def load_kubernetes_config() -> None:
    global _LOADED
    if _LOADED:
        return
    if config.k8s_auth_mode == "kubeconfig":
        k8s_config.load_kube_config(
            config_file=config.kubeconfig_path,
            context=config.kubeconfig_context,
        )
    else:
        k8s_config.load_incluster_config()
    _LOADED = True


def core_v1() -> client.CoreV1Api:
    load_kubernetes_config()
    return client.CoreV1Api()


def apps_v1() -> client.AppsV1Api:
    load_kubernetes_config()
    return client.AppsV1Api()


def batch_v1() -> client.BatchV1Api:
    load_kubernetes_config()
    return client.BatchV1Api()


def networking_v1() -> client.NetworkingV1Api:
    load_kubernetes_config()
    return client.NetworkingV1Api()


def api_client() -> ApiClient:
    load_kubernetes_config()
    return ApiClient()
