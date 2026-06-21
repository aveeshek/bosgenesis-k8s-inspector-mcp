#!/usr/bin/env bash
# Undeploy bosgenesis-k8s-inspector-mcp resources.
#
# Defaults preserve namespaces and external data. Set DELETE_AGENT_TESTING_NAMESPACE=true
# only for disposable test clusters.

set -euo pipefail

K8S_NAMESPACE="${K8S_NAMESPACE:-bosgenesis}"
K8S_DEPLOYMENT="${K8S_DEPLOYMENT:-bosgenesis-k8s-inspector-mcp}"
DELETE_AGENT_TESTING_NAMESPACE="${DELETE_AGENT_TESTING_NAMESPACE:-false}"

info() { printf '\n[INFO] %s\n' "$*"; }
success() { printf '[OK] %s\n' "$*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info "Deleting kustomize resources from ${ROOT_DIR}/k8s"
kubectl delete -k "${ROOT_DIR}/k8s" --ignore-not-found=true

info "Waiting for deployment ${K8S_DEPLOYMENT} to disappear from namespace ${K8S_NAMESPACE}"
kubectl wait \
  --for=delete "deployment/${K8S_DEPLOYMENT}" \
  -n "${K8S_NAMESPACE}" \
  --timeout=120s 2>/dev/null || true

if [[ "${DELETE_AGENT_TESTING_NAMESPACE,,}" == "true" ]]; then
  info "Deleting disposable namespace agent-testing"
  kubectl delete namespace agent-testing --ignore-not-found=true
fi

success "Undeploy complete"
