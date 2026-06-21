---
name: bosgenesis-k8s-operator
description: Use this skill when inspecting, troubleshooting, or safely modifying Kubernetes resources through the BOS Genesis Kubernetes MCP server. The server is namespace-scoped by allowlist and supports runtime namespace selection with the bosgenesis_k8s tools.
---

# BOS Genesis Kubernetes Operator

Use the `bosgenesis_k8s` remote MCP server for BOS Genesis Kubernetes inspection and controlled mutation tasks.

## Rules

- Start by calling `k8s_get_namespace` to see the active namespace and allowlist.
- Operate only inside namespaces returned by `k8s_get_namespace.allowed_namespaces`.
- Pass the intended `namespace` argument on each MCP call when it is available.
- Use `k8s_set_namespace` only when the user asks to switch the default namespace or when a test explicitly requires it.
- Prefer `bosgenesis_k8s` MCP tools over raw `kubectl`.
- Never inspect or modify resources outside the configured namespace allowlist.
- Never use cluster-admin access.
- Never read, list, describe, patch, update, or generically apply Kubernetes Secrets.
- The only Secret exception is the dedicated ephemeral Secret workflow: create/delete MCP-owned `bosgenesis-mcp-*` Secrets without reading or returning values.
- Never use pod exec, attach, or port-forward through this skill.
- Treat write operations as sensitive.
- For write operations, use `dry_run=true` first whenever supported.
- Explain the expected impact before applying any real change.
- Request confirmation before applying, creating, updating, patching, deleting, deletecollection, binding, or scaling resources.
- Keep troubleshooting evidence grounded in MCP tool output.

## Read-Only Workflows

### Namespace Overview

Use `k8s_get_namespace`, then `k8s_namespace_summary`, `k8s_list_pods`, `k8s_list_services`, `k8s_list_configmaps`, `k8s_list_pvcs`, `k8s_list_deployments`, `k8s_list_statefulsets`, `k8s_list_ingresses`, and `k8s_list_events`.

Summarize unhealthy, restarting, pending, or not-ready workloads.

### Diagnose A Failing Pod

Use `k8s_list_pods`, `k8s_describe_pod`, `k8s_get_pod_logs`, and `k8s_list_events`.

Check phase, readiness, restart count, image, node, recent events, and relevant log lines. Do not inspect secrets.

### Inspect A Resource

Use `k8s_get_resource` for a specific supported resource after confirming its namespace is allowed.

Do not use this tool for Secrets or cluster-scoped resources.

### Inspect Persistent Storage

Use `k8s_list_pvcs`, `k8s_describe_pvc`, and `k8s_list_events`.

Check phase, storage class, access modes, requested size, bound volume name, capacity, and recent events.

### Inspect ConfigMaps

Use `k8s_list_configmaps` and `k8s_get_configmap`.

List ConfigMaps first to inspect names, labels, annotations, and key names. Use `include_data=true` only when values are explicitly needed, because ConfigMaps can accidentally contain sensitive non-Secret data.

## Write Workflows

### Apply, Create, Update, Or Patch

1. Validate that `metadata.namespace` is one of the allowed namespaces.
2. Refuse cluster-scoped resources, secrets, RBAC resources, service accounts, privileged pods, host networking, and hostPath volumes.
3. Use the matching write tool with `dry_run=true`.
4. Explain the planned change, expected impact, and rollback idea.
5. Ask for confirmation.
6. Use `dry_run=false` only after approval.

### Scale Or Bind

1. Confirm the target namespace, object name, and requested change.
2. Use `k8s_scale_deployment` or `k8s_bind_pod` with `dry_run=true`.
3. Explain availability, scheduling, and capacity impact.
4. Ask for confirmation.
5. Use `dry_run=false` only after approval.

### Delete

1. Confirm the target namespace, resource type, name, and selector if deleting a collection.
2. Use `k8s_delete_resource`, `k8s_delete_pvc`, `k8s_delete_collection`, or `k8s_delete_pvc_collection` with `dry_run=true`.
3. Explain what will be deleted and expected impact.
4. Ask for confirmation.
5. Use `dry_run=false` only after approval.

### Ephemeral Secret Operations

Use only `k8s_create_ephemeral_secret` and `k8s_delete_ephemeral_secret`.

- Never use generic manifest apply/create/update/patch/delete for Secrets.
- Never read, list, describe, patch, or update Secrets.
- Secret names must start with `bosgenesis-mcp-`.
- Create with `dry_run=true` first.
- Explain the Secret name, namespace, key names, TTL, expected consumer, and rollback/delete command.
- Ask for confirmation before real creation or deletion.
- Do not echo Secret values in chat, logs, docs, or audit summaries.
- Use the returned `correlation_id` to delete the Secret during the same MCP server session.

## Tool Map

Use these MCP tools:

- `k8s_get_namespace`
- `k8s_set_namespace`
- `k8s_namespace_summary`
- `k8s_get_resource`
- `k8s_list_pods`
- `k8s_describe_pod`
- `k8s_get_pod_logs`
- `k8s_list_services`
- `k8s_list_configmaps`
- `k8s_get_configmap`
- `k8s_list_pvcs`
- `k8s_describe_pvc`
- `k8s_list_deployments`
- `k8s_list_statefulsets`
- `k8s_list_ingresses`
- `k8s_list_events`
- `k8s_apply_manifest`
- `k8s_create_resource`
- `k8s_update_resource`
- `k8s_create_pvc`
- `k8s_update_pvc`
- `k8s_create_ephemeral_secret`
- `k8s_delete_ephemeral_secret`
- `k8s_delete_resource`
- `k8s_delete_pvc`
- `k8s_delete_collection`
- `k8s_delete_pvc_collection`
- `k8s_patch_resource`
- `k8s_patch_pvc`
- `k8s_bind_pod`
- `k8s_scale_deployment`
