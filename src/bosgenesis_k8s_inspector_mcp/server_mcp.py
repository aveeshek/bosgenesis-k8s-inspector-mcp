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
def k8s_namespace_summary(actor: str = "codex") -> dict[str, Any]:
    """Summarize the allowed BOS Genesis Kubernetes namespace."""
    return ops.namespace_summary(actor=actor)


@mcp.tool()
def k8s_list_pods(actor: str = "codex") -> list[dict[str, Any]]:
    """List pods in the allowed namespace only."""
    return ops.list_pods(actor=actor)


@mcp.tool()
def k8s_describe_pod(pod_name: str, actor: str = "codex") -> dict[str, Any]:
    """Describe one pod in the allowed namespace only."""
    return ops.describe_pod(pod_name, actor=actor)


@mcp.tool()
def k8s_get_pod_logs(pod_name: str, tail_lines: int = 200, actor: str = "codex") -> dict[str, Any]:
    """Get recent logs for one pod in the allowed namespace only."""
    return ops.pod_logs(pod_name, tail_lines=tail_lines, actor=actor)


@mcp.tool()
def k8s_list_services(actor: str = "codex") -> list[dict[str, Any]]:
    """List services in the allowed namespace only."""
    return ops.list_services(actor=actor)


@mcp.tool()
def k8s_list_configmaps(actor: str = "codex") -> list[dict[str, Any]]:
    """List ConfigMaps in the allowed namespace without returning data values."""
    return ops.list_configmaps(actor=actor)


@mcp.tool()
def k8s_get_configmap(
    configmap_name: str,
    include_data: bool = False,
    actor: str = "codex",
) -> dict[str, Any]:
    """Read one ConfigMap in the allowed namespace.

    By default this returns metadata and key names only. Set include_data=true
    when the ConfigMap values are explicitly needed.
    """
    return ops.get_configmap(configmap_name, include_data=include_data, actor=actor)


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
def k8s_list_pvcs(actor: str = "codex") -> list[dict[str, Any]]:
    """List PersistentVolumeClaims in the allowed namespace only."""
    return ops.list_pvcs(actor=actor)


@mcp.tool()
def k8s_describe_pvc(pvc_name: str, actor: str = "codex") -> dict[str, Any]:
    """Describe one PersistentVolumeClaim in the allowed namespace only."""
    return ops.describe_pvc(pvc_name, actor=actor)


@mcp.tool()
def k8s_list_deployments(actor: str = "codex") -> list[dict[str, Any]]:
    """List deployments in the allowed namespace only."""
    return ops.list_deployments(actor=actor)


@mcp.tool()
def k8s_list_statefulsets(actor: str = "codex") -> list[dict[str, Any]]:
    """List statefulsets in the allowed namespace only."""
    return ops.list_statefulsets(actor=actor)


@mcp.tool()
def k8s_list_ingresses(actor: str = "codex") -> list[dict[str, Any]]:
    """List ingresses in the allowed namespace only."""
    return ops.list_ingresses(actor=actor)


@mcp.tool()
def k8s_list_events(actor: str = "codex") -> list[dict[str, Any]]:
    """List Kubernetes events in the allowed namespace only."""
    return ops.list_events(actor=actor)


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
) -> dict[str, Any]:
    """Create a write-only, MCP-owned temporary Secret in the allowed namespace.

    Secret values are never returned. The name must start with
    bosgenesis-mcp-. Use the returned correlation_id for in-session deletion.
    """
    require_mutation_api_key(api_key)
    return ops.create_ephemeral_secret(
        name=name,
        string_data=json.loads(string_data_json),
        data=json.loads(data_json),
        secret_type=secret_type,
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
) -> dict[str, Any]:
    """Delete an MCP-owned temporary Secret from the current server session."""
    require_mutation_api_key(api_key)
    return ops.delete_ephemeral_secret(
        name=name,
        correlation_id=correlation_id,
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
) -> dict[str, Any]:
    """Delete a supported resource by name in the allowed namespace only."""
    require_mutation_api_key(api_key)
    return ops.delete_resource(
        resource=resource,
        name=name,
        namespace=config.namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_delete_pvc(
    pvc_name: str,
    dry_run: bool = False,
    actor: str = "codex",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Delete one PersistentVolumeClaim in the allowed namespace only."""
    require_mutation_api_key(api_key)
    return ops.delete_pvc(
        name=pvc_name,
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
) -> dict[str, Any]:
    """Delete a filtered collection of supported resources in the allowed namespace only."""
    require_mutation_api_key(api_key)
    return ops.delete_collection(
        resource=resource,
        namespace=config.namespace,
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
) -> dict[str, Any]:
    """Delete filtered PersistentVolumeClaims in the allowed namespace only."""
    require_mutation_api_key(api_key)
    return ops.delete_pvc_collection(
        label_selector=label_selector,
        field_selector=field_selector,
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
) -> dict[str, Any]:
    """Patch a supported resource in the allowed namespace only."""
    require_mutation_api_key(api_key)
    patch = json.loads(patch_json)
    return ops.patch_resource(
        resource=resource,
        name=name,
        namespace=config.namespace,
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
) -> dict[str, Any]:
    """Patch one PersistentVolumeClaim in the allowed namespace only."""
    require_mutation_api_key(api_key)
    patch = json.loads(patch_json)
    return ops.patch_pvc(
        name=pvc_name,
        patch=patch,
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
) -> dict[str, Any]:
    """Bind a pending pod to a named node without reading node resources."""
    require_mutation_api_key(api_key)
    return ops.bind_pod(
        pod_name=pod_name,
        node_name=node_name,
        namespace=config.namespace,
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
) -> dict[str, Any]:
    """Scale a deployment in the allowed namespace only."""
    require_mutation_api_key(api_key)
    return ops.scale_deployment(
        name=name,
        replicas=replicas,
        namespace=config.namespace,
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
