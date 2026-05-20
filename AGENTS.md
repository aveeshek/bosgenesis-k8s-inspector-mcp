# AGENTS.md — BOS Genesis Kubernetes MCP Server

## Project purpose

This repository implements `bosgenesis-k8s-inspector-mcp`, a namespace-scoped Kubernetes MCP server for the BOS Genesis platform.

The MCP server allows Codex and other agents to inspect and operate Kubernetes resources only inside the `bosgenesis` namespace.

## Hard safety rules

- Never access Kubernetes resources outside the configured namespace.
- The only allowed namespace is `bosgenesis` unless explicitly changed in config and policy.
- Never request or use cluster-admin permissions.
- Never create ClusterRole, ClusterRoleBinding, Namespace, Node, PersistentVolume, or CRD resources.
- Never read, list, create, update, patch, or delete Kubernetes Secrets.
- Never use pods/exec, pods/attach, or port-forward.
- Never bypass the policy engine.
- All mutating operations must go through the MCP server policy validator.
- Prefer dry-run before apply/delete/patch.
- Any write action must be clearly explained before execution.

## Allowed operational scope

Allowed read operations:

- pods
- pod logs
- services
- deployments
- replicasets
- statefulsets
- daemonsets
- jobs
- cronjobs
- configmaps
- events
- ingresses
- PVCs

Allowed write operations only when policy allows:

- create/update/delete allowed namespaced app resources
- patch allowed namespaced app resources
- scale deployments/statefulsets

## Audit requirement

Every MCP tool call must generate an audit record with:

- timestamp
- actor
- operation
- namespace
- resource kind
- resource name
- dry_run flag
- request id / correlation id
- decision allowed or denied
- result success or failure

## Testing expectation

Before changing code:

- run unit tests
- run policy tests
- test namespace blocking
- test blocked resource kinds
- test dry-run apply

## Codex behavior

When asked about Kubernetes state, use the MCP tools, not raw kubectl, unless explicitly instructed by the user.

When asked to change Kubernetes resources, first explain:

1. resource kind
2. resource name
3. namespace
4. action
5. expected impact
6. rollback idea

Then use the MCP tool with dry-run first where possible.