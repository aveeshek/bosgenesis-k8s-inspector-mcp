# MCP Tool Contract

The MCP server exposes namespace-scoped tools only. The namespace is controlled by configuration and defaults to `bosgenesis`.

The Kubernetes deployment serves the same tools through Streamable HTTP at:

```text
http://k8s-inspector.bosgenesis.local/mcp
```

## Read tools

| Tool | Purpose |
|---|---|
| `k8s_namespace_summary` | Counts and health summary for the allowed namespace |
| `k8s_list_pods` | List pods |
| `k8s_describe_pod` | Describe one pod |
| `k8s_get_pod_logs` | Get recent pod logs |
| `k8s_list_services` | List services |
| `k8s_list_configmaps` | List ConfigMaps with metadata and key names only |
| `k8s_get_configmap` | Read one ConfigMap; values are returned only when `include_data=true` |
| `k8s_get_resource` | Read one allowed namespaced resource as full JSON for reconstruction evidence; Secrets and cluster-scoped kinds are denied |
| `k8s_list_pvcs` | List PersistentVolumeClaims |
| `k8s_describe_pvc` | Describe one PersistentVolumeClaim |
| `k8s_list_deployments` | List deployments |
| `k8s_list_statefulsets` | List statefulsets |
| `k8s_list_ingresses` | List ingresses |
| `k8s_list_events` | List events |

## Write tools

| Tool | Purpose | Safety |
|---|---|---|
| `k8s_apply_manifest` | Server-side apply one manifest JSON object | Requires API key; enforces namespace, blocks dangerous resources and pod security risks |
| `k8s_create_resource` | Create one supported manifest JSON object | Requires API key; namespace only; supports dry-run |
| `k8s_update_resource` | Replace/update one supported manifest JSON object | Requires API key; namespace only; supports dry-run |
| `k8s_create_pvc` | Create one PersistentVolumeClaim manifest | Requires API key; namespace only; supports dry-run |
| `k8s_update_pvc` | Replace/update one PersistentVolumeClaim manifest | Requires API key; namespace only; supports dry-run |
| `k8s_create_ephemeral_secret` | Create an MCP-owned temporary Secret without returning values | Requires API key; namespace only; name must start with `bosgenesis-mcp-`; supports dry-run |
| `k8s_delete_ephemeral_secret` | Delete an MCP-owned temporary Secret from the current server session | Requires API key; namespace only; matching `correlation_id` required; supports dry-run |
| `k8s_delete_resource` | Delete supported resource by name | Requires API key; namespace only; supports dry-run |
| `k8s_delete_pvc` | Delete one PersistentVolumeClaim by name | Requires API key; namespace only; supports dry-run |
| `k8s_delete_collection` | Delete a filtered collection of supported resources | Requires API key; namespace only; requires label or field selector; supports dry-run |
| `k8s_delete_pvc_collection` | Delete filtered PersistentVolumeClaims | Requires API key; namespace only; requires label or field selector; supports dry-run |
| `k8s_patch_resource` | Patch supported resource | Requires API key; namespace only; blocks dangerous patch payloads; supports dry-run |
| `k8s_patch_pvc` | Patch one PersistentVolumeClaim | Requires API key; namespace only; supports dry-run |
| `k8s_bind_pod` | Bind a pending pod to a named node | Requires API key; namespace only; does not read node resources; supports dry-run |
| `k8s_scale_deployment` | Scale deployment replica count | Requires API key; namespace only; supports dry-run |

## `k8s_get_resource`

Purpose:

```text
Read one allowed namespaced Kubernetes resource as full JSON for reconstruction evidence.
```

Input:

```json
{
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "example",
  "actor": "codex",
  "correlation_id": "optional-correlation-id"
}
```

Allowed kinds:

- `ConfigMap`
- `Service`
- `Deployment`
- `StatefulSet`
- `DaemonSet`
- `Job`
- `CronJob`
- `PersistentVolumeClaim`
- `Ingress`

Success response:

```json
{
  "status": "ok",
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "example",
  "resource": {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {},
    "spec": {},
    "status": {}
  }
}
```

Not-found response:

```json
{
  "status": "not_found",
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "missing",
  "error": "resource_not_found"
}
```

MCP policy-denied response:

```json
{
  "status": "denied",
  "namespace": "bosgenesis",
  "kind": "Secret",
  "name": "blocked",
  "error": "policy_denied",
  "message": "Kind 'Secret' is blocked by policy."
}
```

REST `/resource` uses the same operation layer and returns HTTP `403` for policy denials. The inspector does not strip runtime metadata from allowed resources; downstream consumers own manifest normalization.

## Blocked by policy

The default policy blocks:

- `secrets`
- `serviceaccounts`
- RBAC objects such as `roles` and `rolebindings`
- cluster-scoped resources such as `nodes`, `namespaces`, `persistentvolumes`, and `customresourcedefinitions`
- storage and admission classes such as `storageclasses`, `ingressclasses`, `priorityclasses`, `mutatingwebhookconfigurations`, and `validatingwebhookconfigurations`
- `pods/exec`, `pods/attach`, and `pods/portforward`
- privileged containers
- `hostNetwork`, `hostPID`, `hostIPC`
- `hostPath` volumes
- service account override in user workloads

## Narrow Secret Exception

Secrets remain blocked for all generic read and mutation tools. The server exposes no Secret list/get/describe/update/patch tools.

The only allowed Secret workflow is:

- `k8s_create_ephemeral_secret`
- `k8s_delete_ephemeral_secret`

This workflow can create a temporary Secret named `bosgenesis-mcp-*`, label and annotate it as MCP-owned, return only the Secret name/key names/TTL/correlation ID, and later delete it during the same server session by matching `correlation_id`. Secret values are never returned in tool responses or audit summaries. Kubernetes does not auto-delete Secrets from the TTL annotation, so delete explicitly unless a separate cleanup controller is added.
