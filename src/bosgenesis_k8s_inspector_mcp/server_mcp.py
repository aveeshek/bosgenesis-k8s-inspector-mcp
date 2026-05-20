from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import config
from .operations import ops
from .telemetry import setup_telemetry

setup_telemetry()

mcp = FastMCP("bosgenesis-k8s-inspector-mcp")


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
def k8s_apply_manifest(manifest_json: str, dry_run: bool = False, actor: str = "codex") -> dict[str, Any]:
    """Apply one Kubernetes manifest JSON object in the allowed namespace only.

    The manifest must include metadata.namespace equal to the allowed namespace.
    Policy blocks cluster-scoped resources, RBAC resources, secrets, service accounts,
    privileged pods, host networking, hostPath, and serviceAccountName override.
    """
    manifest = json.loads(manifest_json)
    return ops.apply_manifest(manifest=manifest, dry_run=dry_run, actor=actor).model_dump()


@mcp.tool()
def k8s_delete_resource(resource: str, name: str, dry_run: bool = False, actor: str = "codex") -> dict[str, Any]:
    """Delete a supported resource by name in the allowed namespace only."""
    return ops.delete_resource(
        resource=resource,
        name=name,
        namespace=config.namespace,
        dry_run=dry_run,
        actor=actor,
    ).model_dump()


@mcp.tool()
def k8s_patch_resource(resource: str, name: str, patch_json: str, dry_run: bool = False, actor: str = "codex") -> dict[str, Any]:
    """Patch a supported resource in the allowed namespace only."""
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
def k8s_scale_deployment(name: str, replicas: int, dry_run: bool = False, actor: str = "codex") -> dict[str, Any]:
    """Scale a deployment in the allowed namespace only."""
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


if __name__ == "__main__":
    run()
