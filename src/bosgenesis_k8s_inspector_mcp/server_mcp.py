from __future__ import annotations

import json
from secrets import compare_digest
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import config
from .errors import PolicyDeniedError
from .operations import ops
from .telemetry import setup_telemetry

setup_telemetry()

mcp = FastMCP(
    "bosgenesis-k8s-inspector-mcp",
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(allowed_hosts=config.mcp_allowed_hosts),
)


def require_mutation_api_key(api_key: str | None) -> None:
    if not config.require_api_key:
        return
    expected = config.env.api_key
    if not expected or expected == "change-me-later":
        raise PermissionError("Mutating MCP tools require a non-placeholder BOSGENESIS_API_KEY.")
    if not api_key or not compare_digest(api_key, expected):
        raise PermissionError("Invalid or missing api_key for mutating MCP tool.")


@mcp.tool()
def k8s_get_namespace() -> dict[str, Any]:
    """Get the currently allowed namespace for this inspector MCP session."""
    return {
        "configured_namespace": config.configured_namespace,
        "active_namespace": config.namespace,
        "allowed_namespaces": config.allowed_namespaces,
        "session_context_key": f"namespace:{config.namespace}",
    }


@mcp.tool()
def k8s_set_namespace(namespace: str, actor: str = "codex") -> dict[str, Any]:
    """Switch the default namespace for this inspector MCP session."""
    active_namespace = config.set_runtime_namespace(namespace)
    return {
        "configured_namespace": config.configured_namespace,
        "active_namespace": active_namespace,
        "allowed_namespaces": config.allowed_namespaces,
        "session_context_key": f"namespace:{active_namespace}",
        "updated_by": actor,
    }


@mcp.tool()
def k8s_namespace_summary(actor: str = "codex", namespace: str | None = None) -> dict[str, Any]:
    """Summarize one allowed Kubernetes namespace."""
    return ops.namespace_summary(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_pods(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List pods in one allowed namespace."""
    return ops.list_pods(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_describe_pod(
    pod_name: str,
    actor: str = "codex",
    namespace: str | None = None,
) -> dict[str, Any]:
    """Describe one pod in one allowed namespace."""
    return ops.describe_pod(pod_name, actor=actor, namespace=namespace)


@mcp.tool()
def k8s_get_pod_logs(
    pod_name: str,
    tail_lines: int = 200,
    actor: str = "codex",
    namespace: str | None = None,
) -> dict[str, Any]:
    """Get recent logs for one pod in one allowed namespace."""
    return ops.pod_logs(pod_name, tail_lines=tail_lines, actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_services(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List services in one allowed namespace."""
    return ops.list_services(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_configmaps(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List ConfigMaps in one allowed namespace without returning data values."""
    return ops.list_configmaps(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_get_configmap(
    configmap_name: str,
    include_data: bool = False,
    actor: str = "codex",
    namespace: str | None = None,
) -> dict[str, Any]:
    """Read one ConfigMap in one allowed namespace.

    By default this returns metadata and key names only. Set include_data=true
    when the ConfigMap values are explicitly needed.
    """
    return ops.get_configmap(
        configmap_name,
        include_data=include_data,
        actor=actor,
        namespace=namespace,
    )


@mcp.tool()
def k8s_get_resource(
    namespace: str,
    kind: str,
    name: str,
    actor: str = "codex",
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Read one allowed namespaced Kubernetes resource as full JSON for reconstruction evidence.

    Secrets and cluster-scoped resources are denied.
    """
    try:
        return ops.get_resource(
            namespace=namespace,
            kind=kind,
            name=name,
            actor=actor,
            correlation_id=correlation_id,
        )
    except PolicyDeniedError as exc:
        return {
            "status": "denied",
            "namespace": namespace,
            "kind": kind,
            "name": name,
            "error": "policy_denied",
            "message": str(exc),
        }


@mcp.tool()
def k8s_list_pvcs(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List PersistentVolumeClaims in one allowed namespace."""
    return ops.list_pvcs(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_describe_pvc(
    pvc_name: str,
    actor: str = "codex",
    namespace: str | None = None,
) -> dict[str, Any]:
    """Describe one PersistentVolumeClaim in one allowed namespace."""
    return ops.describe_pvc(pvc_name, actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_deployments(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List deployments in one allowed namespace."""
    return ops.list_deployments(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_statefulsets(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List statefulsets in one allowed namespace."""
    return ops.list_statefulsets(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_ingresses(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List ingresses in one allowed namespace."""
    return ops.list_ingresses(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_list_events(actor: str = "codex", namespace: str | None = None) -> list[dict[str, Any]]:
    """List Kubernetes events in one allowed namespace."""
    return ops.list_events(actor=actor, namespace=namespace)


@mcp.tool()
def k8s_apply_manifest(
    manifest_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Apply one Kubernetes manifest JSON object in the allowed namespace only.

    The manifest must include metadata.namespace equal to the allowed namespace.
    Policy blocks cluster-scoped resources, RBAC resources, secrets, service accounts,
    privileged pods, host networking, hostPath, and serviceAccountName override.
    """
    require_mutation_api_key(api_key)
    manifest = json.loads(manifest_json)
    return ops.apply_manifest(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_create_resource(
    manifest_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create one supported Kubernetes object in the allowed namespace only."""
    require_mutation_api_key(api_key)
    manifest = json.loads(manifest_json)
    return ops.create_manifest(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_update_resource(
    manifest_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Replace/update one supported Kubernetes object in the allowed namespace only."""
    require_mutation_api_key(api_key)
    manifest = json.loads(manifest_json)
    return ops.update_manifest(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_create_pvc(
    manifest_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create one PersistentVolumeClaim in the allowed namespace only."""
    require_mutation_api_key(api_key)
    manifest = json.loads(manifest_json)
    return ops.create_pvc(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_update_pvc(
    manifest_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Replace/update one PersistentVolumeClaim in the allowed namespace only."""
    require_mutation_api_key(api_key)
    manifest = json.loads(manifest_json)
    return ops.update_pvc(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_create_ephemeral_secret(
    name: str,
    string_data_json: str = "{}",
    data_json: str = "{}",
    secret_type: str = "Opaque",
    ttl_seconds: int = 3600,
    dry_run: bool = False,
    actor: str = "codex",
    correlation_id: str | None = None,
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Create a write-only, MCP-owned temporary Secret in one allowed namespace.

    Secret values are never returned. The name must start with
    bosgenesis-mcp-. Use the returned correlation_id for in-session deletion.
    """
    require_mutation_api_key(api_key)
    return ops.create_ephemeral_secret(
        name=name,
        string_data=json.loads(string_data_json),
        data=json.loads(data_json),
        secret_type=secret_type,
        namespace=namespace,
        ttl_seconds=ttl_seconds,
        dry_run=dry_run,
        actor=actor,
        correlation_id=correlation_id,
    ).model_dump()


@mcp.tool()
def k8s_delete_ephemeral_secret(
    name: str,
    correlation_id: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Delete an MCP-owned temporary Secret from the current server session."""
    require_mutation_api_key(api_key)
    return ops.delete_ephemeral_secret(
        name=name,
        correlation_id=correlation_id,
        namespace=namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_delete_resource(
    resource: str,
    name: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Delete a supported resource by name in one allowed namespace."""
    require_mutation_api_key(api_key)
    return ops.delete_resource(
        resource=resource,
        name=name,
        namespace=namespace or config.namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_delete_pvc(
    pvc_name: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Delete one PersistentVolumeClaim in one allowed namespace."""
    require_mutation_api_key(api_key)
    return ops.delete_pvc(
        name=pvc_name,
        namespace=namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_delete_collection(
    resource: str,
    label_selector: str | None = None,
    field_selector: str | None = None,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Delete a filtered collection of supported resources in one allowed namespace."""
    require_mutation_api_key(api_key)
    return ops.delete_collection(
        resource=resource,
        namespace=namespace or config.namespace,
        label_selector=label_selector,
        field_selector=field_selector,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_delete_pvc_collection(
    label_selector: str | None = None,
    field_selector: str | None = None,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Delete filtered PersistentVolumeClaims in one allowed namespace."""
    require_mutation_api_key(api_key)
    return ops.delete_pvc_collection(
        label_selector=label_selector,
        field_selector=field_selector,
        namespace=namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_patch_resource(
    resource: str,
    name: str,
    patch_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Patch a supported resource in one allowed namespace."""
    require_mutation_api_key(api_key)
    patch = json.loads(patch_json)
    return ops.patch_resource(
        resource=resource,
        name=name,
        namespace=namespace or config.namespace,
        patch=patch,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_patch_pvc(
    pvc_name: str,
    patch_json: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Patch one PersistentVolumeClaim in one allowed namespace."""
    require_mutation_api_key(api_key)
    patch = json.loads(patch_json)
    return ops.patch_pvc(
        name=pvc_name,
        patch=patch,
        namespace=namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_bind_pod(
    pod_name: str,
    node_name: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Bind a pending pod to a named node without reading node resources."""
    require_mutation_api_key(api_key)
    return ops.bind_pod(
        pod_name=pod_name,
        node_name=node_name,
        namespace=namespace or config.namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_scale_deployment(
    name: str,
    replicas: int,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Scale a deployment in one allowed namespace."""
    require_mutation_api_key(api_key)
    return ops.scale_deployment(
        name=name,
        replicas=replicas,
        namespace=namespace or config.namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


def run() -> None:
    # Default to stdio for Codex/local client integration.
    # Keep REST API deployment separate using server_fastapi.py.
    mcp.run()


def streamable_http_app():
    """Return the Streamable HTTP MCP ASGI app for mounting under /mcp."""
    return mcp.streamable_http_app()


if __name__ == "__main__":
    run()
