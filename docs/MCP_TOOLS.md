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
| `k8s_delete_resource` | Delete supported resource by name | Requires API key; namespace only; supports dry-run |
| `k8s_delete_collection` | Delete a filtered collection of supported resources | Requires API key; namespace only; requires label or field selector; supports dry-run |
| `k8s_patch_resource` | Patch supported resource | Requires API key; namespace only; blocks dangerous patch payloads; supports dry-run |
| `k8s_bind_pod` | Bind a pending pod to a named node | Requires API key; namespace only; does not read node resources; supports dry-run |
| `k8s_scale_deployment` | Scale deployment replica count | Requires API key; namespace only; supports dry-run |

## Blocked by policy

The default policy blocks:

- `secrets`
- `serviceaccounts`
- RBAC objects such as `roles` and `rolebindings`
- cluster-scoped resources such as `nodes`, `namespaces`, `persistentvolumes`, and `customresourcedefinitions`
- `pods/exec`, `pods/attach`, and `pods/portforward`
- privileged containers
- `hostNetwork`, `hostPID`, `hostIPC`
- `hostPath` volumes
- service account override in user workloads
