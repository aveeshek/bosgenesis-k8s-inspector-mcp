#!/usr/bin/env bash
# Build, ship, install, and roll out bosgenesis-k8s-inspector-mcp.
# Usage: ./playbook/deploy.sh <tag>
# Example: ./playbook/deploy.sh 0.0.2
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-bosgenesis-k8s-inspector-mcp-server}"
REMOTE_USER="${REMOTE_USER:-taieuser}"
REMOTE_HOST="${REMOTE_HOST:-10.99.52.165}"
REMOTE_TMP="${REMOTE_TMP:-/tmp}"
K8S_NAMESPACE="${K8S_NAMESPACE:-bosgenesis}"
K8S_DEPLOYMENT="${K8S_DEPLOYMENT:-bosgenesis-k8s-inspector-mcp}"
K8S_CONTAINER="${K8S_CONTAINER:-app}"
TEST_URL="${TEST_URL:-http://bosgenesis-k8s-inspector-mcp/mcp}"
API_KEY="${API_KEY:-bosgenesis-k8s-mcp-secret}"
REQUIRED_NAMESPACES="${REQUIRED_NAMESPACES:-bosgenesis agent-testing}"

info()    { echo -e "\n\033[1;34m> $*\033[0m"; }
success() { echo -e "\033[1;32mOK: $*\033[0m"; }
warn()    { echo -e "\033[1;33mWARN: $*\033[0m"; }
die()     { echo -e "\033[1;31mERROR: $*\033[0m" >&2; exit 1; }

TAG="${1:-}"
[[ -z "${TAG}" ]] && die "Usage: $0 <tag>  (e.g. $0 0.0.2)"

FULL_IMAGE="${IMAGE_NAME}:${TAG}"
TAR_FILE="${IMAGE_NAME}-${TAG}.tar"
LOCAL_TAR="${ROOT_DIR}/${TAR_FILE}"
REMOTE_TAR="${REMOTE_TMP}/${TAR_FILE}"

ensure_namespace() {
  local namespace="$1"
  if kubectl get namespace "${namespace}" >/dev/null 2>&1; then
    success "Namespace exists: ${namespace}"
  else
    info "Creating namespace ${namespace}..."
    kubectl create namespace "${namespace}"
    success "Namespace created: ${namespace}"
  fi
}

info "Deploying ${FULL_IMAGE}"

info "Building Docker image..."
docker build -t "${FULL_IMAGE}" "${ROOT_DIR}"
success "Image built: ${FULL_IMAGE}"

info "Saving image to tarball..."
docker save "${FULL_IMAGE}" -o "${LOCAL_TAR}"
success "Saved: ${LOCAL_TAR}"

info "Copying tarball to ${REMOTE_HOST}..."
scp "${LOCAL_TAR}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_TMP}/"
success "Transferred to ${REMOTE_HOST}:${REMOTE_TMP}/"

info "Importing image into containerd on ${REMOTE_HOST}..."
ssh "${REMOTE_USER}@${REMOTE_HOST}" bash <<EOF
set -euo pipefail
sudo ctr -n k8s.io images import "${REMOTE_TAR}"
echo "--- Images matching '${IMAGE_NAME}' ---"
sudo ctr -n k8s.io images list | grep "${IMAGE_NAME}" || true
EOF
success "Image imported into k8s.io namespace"

info "Ensuring required namespaces exist..."
for namespace in ${REQUIRED_NAMESPACES}; do
  ensure_namespace "${namespace}"
done

info "Applying Kubernetes manifests from ${ROOT_DIR}/k8s..."
kubectl apply -k "${ROOT_DIR}/k8s"
success "Kubernetes manifests applied"

info "Container names in deployment..."
kubectl get deployment "${K8S_DEPLOYMENT}" \
  -n "${K8S_NAMESPACE}" \
  -o jsonpath='{.spec.template.spec.containers[*].name}'
echo

info "Setting image to ${FULL_IMAGE}..."
kubectl set image \
  "deployment/${K8S_DEPLOYMENT}" \
  "${K8S_CONTAINER}=${FULL_IMAGE}" \
  -n "${K8S_NAMESPACE}"

info "Restarting deployment so a re-used tag picks up the newly imported image..."
kubectl rollout restart "deployment/${K8S_DEPLOYMENT}" -n "${K8S_NAMESPACE}"

info "Waiting for rollout..."
kubectl rollout status "deployment/${K8S_DEPLOYMENT}" -n "${K8S_NAMESPACE}" --timeout=180s
success "Rollout complete"

info "Pods:"
kubectl get pod -n "${K8S_NAMESPACE}" -o wide | grep k8s-inspector || true

info "Active image:"
kubectl get deployment "${K8S_DEPLOYMENT}" \
  -n "${K8S_NAMESPACE}" \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
echo

info "Running smoke test against ${TEST_URL}..."
if curl -i \
  -H "Accept: text/event-stream" \
  -H "x-api-key: ${API_KEY}" \
  "${TEST_URL}"; then
  success "Smoke test completed"
else
  warn "Smoke test failed. If running outside the cluster network, retry with TEST_URL set to the ingress URL."
fi

success "Deploy of ${FULL_IMAGE} finished"

read -rp $'\nDelete local tarball '"${LOCAL_TAR}"$'? [y/N] ' CLEAN
if [[ "${CLEAN,,}" == "y" ]]; then
  rm -f "${LOCAL_TAR}"
  success "Local tarball removed"
fi
