---
name: bosgenesis-k8s-operator
description: Use this skill when inspecting, troubleshooting, or safely modifying Kubernetes resources through the BOS Genesis namespace-scoped Kubernetes MCP server. Trigger for BOS Genesis Kubernetes operations, pod diagnostics, namespace summaries, pod logs, events, service/deployment inspection, dry-run manifest application, creating, updating, patching, scaling, binding, or deleting resources through the bosgenesis_k8s MCP tools.
---

# BOS Genesis Kubernetes Operator

Use the `bosgenesis_k8s` remote MCP server for Kubernetes inspection and mutation tasks related to BOS Genesis.

## Rules

- Operate only inside the `bosgenesis` namespace.
- Prefer `bosgenesis_k8s` MCP tools over raw `kubectl`.
- Never inspect or modify resources outside `bosgenesis`.
- Never use cluster-admin access.
- Never access Kubernetes secrets.
- Never use pod exec, attach, or port-forward through this skill.
- Treat write operations as sensitive.
- For write operations, use `dry_run=true` first whenever supported.
- Explain the expected impact before applying any real change.
- Request confirmation before applying, creating, updating, patching, deleting, deletecollection, binding, or scaling resources.
- Keep troubleshooting evidence grounded in MCP tool output.

## Read-Only Workflows

### Namespace Overview

Use:

- `k8s_namespace_summary`
- `k8s_list_pods`
- `k8s_list_services`
- `k8s_list_deployments`
- `k8s_list_statefulsets`
- `k8s_list_ingresses`
- `k8s_list_events`

Summarize unhealthy, restarting, pending, or not-ready workloads.

### Diagnose A Failing Pod

Use:

- `k8s_list_pods`
- `k8s_describe_pod`
- `k8s_get_pod_logs`
- `k8s_list_events`

Check phase, readiness, restart count, image, node, recent events, and relevant log lines. Do not inspect secrets.

### Inspect A Workload

Use:

- `k8s_list_deployments`
- `k8s_list_statefulsets`
- `k8s_describe_pod`
- `k8s_get_pod_logs`
- `k8s_list_events`

Compare desired replicas, ready replicas, images, pod status, and events.

## Write Workflows

### Apply Manifest

1. Validate that `metadata.namespace` is `bosgenesis`.
2. Refuse cluster-scoped resources, secrets, RBAC resources, service accounts, privileged pods, host networking, and hostPath volumes.
3. Use `k8s_apply_manifest` with `dry_run=true`.
4. Explain the planned change and possible impact.
5. Ask for confirmation.
6. Use `k8s_apply_manifest` with `dry_run=false` only after approval.

### Create Resource

1. Validate that `metadata.namespace` is `bosgenesis`.
2. Refuse secrets, RBAC resources, service accounts, cluster-scoped resources, privileged pods, host networking, and hostPath volumes.
3. Use `k8s_create_resource` with `dry_run=true`.
4. Explain the resource kind, name, namespace, expected impact, and rollback idea.
5. Ask for confirmation.
6. Use `k8s_create_resource` with `dry_run=false` only after approval.

### Update Resource

1. Validate that `metadata.namespace` is `bosgenesis`.
2. Confirm the resource already exists and is supported.
3. Use `k8s_update_resource` with `dry_run=true`.
4. Explain what fields will change and expected impact.
5. Ask for confirmation.
6. Use `k8s_update_resource` with `dry_run=false` only after approval.

### Patch Resource

1. Confirm the resource is supported and inside `bosgenesis`.
2. Refuse patches that introduce privileged containers, host networking, hostPath, or service account override.
3. Use `k8s_patch_resource` with `dry_run=true`.
4. Explain the patch and expected impact.
5. Ask for confirmation.
6. Use `k8s_patch_resource` with `dry_run=false` only after approval.

### Scale Deployment

1. Confirm the deployment name and target replica count.
2. Use `k8s_scale_deployment` with `dry_run=true`.
3. Explain availability and capacity impact.
4. Ask for confirmation.
5. Use `k8s_scale_deployment` with `dry_run=false` only after approval.

### Bind Pod

1. Confirm the pod name and target node name.
2. Use `k8s_bind_pod` with `dry_run=true`.
3. Explain scheduling impact.
4. Ask for confirmation.
5. Use `k8s_bind_pod` with `dry_run=false` only after approval.

### Delete Resource

1. Confirm the resource type and name.
2. Use `k8s_delete_resource` with `dry_run=true`.
3. Explain what will be deleted and expected impact.
4. Ask for confirmation.
5. Use `k8s_delete_resource` with `dry_run=false` only after approval.

### Delete Collection

1. Confirm the resource type.
2. Require a `label_selector` or `field_selector`.
3. Use `k8s_delete_collection` with `dry_run=true`.
4. Explain which resources may match and expected impact.
5. Ask for confirmation.
6. Use `k8s_delete_collection` with `dry_run=false` only after approval.

## Tool Map

Use these MCP tools:

- `k8s_namespace_summary`
- `k8s_list_pods`
- `k8s_describe_pod`
- `k8s_get_pod_logs`
- `k8s_list_services`
- `k8s_list_deployments`
- `k8s_list_statefulsets`
- `k8s_list_ingresses`
- `k8s_list_events`
- `k8s_apply_manifest`
- `k8s_create_resource`
- `k8s_update_resource`
- `k8s_delete_resource`
- `k8s_delete_collection`
- `k8s_patch_resource`
- `k8s_bind_pod`
- `k8s_scale_deployment`