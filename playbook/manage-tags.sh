#!/usr/bin/env bash
# ============================================================
# manage-tags.sh — List & delete bosgenesis-k8s-inspector tags
# Usage: ./manage-tags.sh
# ============================================================
set -euo pipefail

# ── Config ───────────────────────────────────────────────────
IMAGE_NAME="bosgenesis-k8s-inspector-mcp-server"
REMOTE_USER="taieuser"
REMOTE_HOST="10.99.52.165"
# ─────────────────────────────────────────────────────────────

# ── Helpers ──────────────────────────────────────────────────
info()    { echo -e "\n\033[1;34m▶ $*\033[0m"; }
success() { echo -e "\033[1;32m✔ $*\033[0m"; }
warn()    { echo -e "\033[1;33m⚠ $*\033[0m"; }
die()     { echo -e "\033[1;31m✖ $*\033[0m" >&2; exit 1; }
hr()      { echo -e "\033[90m────────────────────────────────────────\033[0m"; }

# ── Collect tags from both sources ───────────────────────────
get_local_tags() {
  docker images --format "{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" "${IMAGE_NAME}" 2>/dev/null \
    | grep -v "^<none>" || true
}

get_remote_tags() {
  ssh "${REMOTE_USER}@${REMOTE_HOST}" \
    "sudo ctr -n k8s.io images list 2>/dev/null | grep '${IMAGE_NAME}' | awk '{print \$1}'" \
    | sed "s|docker.io/library/${IMAGE_NAME}:||;s|${IMAGE_NAME}:||" \
    | sort -u || true
}

# ── Print a numbered tag table ────────────────────────────────
print_tag_table() {
  local source="$1"   # "local" or "remote"
  shift
  local tags=("$@")

  if [[ ${#tags[@]} -eq 0 ]]; then
    echo "  (none found)"
    return
  fi

  local i=1
  for entry in "${tags[@]}"; do
    printf "  \033[1;37m[%2d]\033[0m  %s\n" "$i" "$entry"
    (( i++ ))
  done
}

# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
clear
echo -e "\033[1;36m╔══════════════════════════════════════════╗"
echo -e "║  bosgenesis-k8s-inspector  Tag Manager  ║"
echo -e "╚══════════════════════════════════════════╝\033[0m"

# ── 1. Fetch local tags ───────────────────────────────────────
info "Scanning local Docker images..."
mapfile -t LOCAL_RAW < <(get_local_tags)
LOCAL_TAGS=()
LOCAL_META=()
for row in "${LOCAL_RAW[@]}"; do
  tag=$(echo "$row" | cut -f1)
  meta=$(echo "$row" | cut -f2-3 | tr '\t' '  ')
  LOCAL_TAGS+=("$tag")
  LOCAL_META+=("${tag}  \033[90m(${meta})\033[0m")
done

# ── 2. Fetch remote tags ──────────────────────────────────────
info "Scanning remote node  ${REMOTE_HOST}..."
mapfile -t REMOTE_TAGS < <(get_remote_tags)

# ── 3. Display ────────────────────────────────────────────────
hr
echo -e "\n  \033[1mLocal Docker tags\033[0m"
hr
for i in "${!LOCAL_META[@]}"; do
  printf "  \033[1;37m[%2d]\033[0m  %b\n" "$((i+1))" "${LOCAL_META[$i]}"
done
[[ ${#LOCAL_TAGS[@]} -eq 0 ]] && echo "  (none found)"

echo -e "\n  \033[1mRemote containerd tags  (${REMOTE_HOST})\033[0m"
hr
REMOTE_OFFSET=${#LOCAL_TAGS[@]}
for i in "${!REMOTE_TAGS[@]}"; do
  printf "  \033[1;37m[%2d]\033[0m  %s\n" "$((REMOTE_OFFSET+i+1))" "${REMOTE_TAGS[$i]}"
done
[[ ${#REMOTE_TAGS[@]} -eq 0 ]] && echo "  (none found)"

# ── 4. Deletion menu ─────────────────────────────────────────
TOTAL=$(( ${#LOCAL_TAGS[@]} + ${#REMOTE_TAGS[@]} ))
if [[ "$TOTAL" -eq 0 ]]; then
  echo -e "\nNo tags found anywhere. Nothing to delete."
  exit 0
fi

echo
hr
echo -e "  Enter numbers to delete (space-separated), or \033[1ma\033[0m for all, or \033[1mq\033[0m to quit:"
echo -e "  Example: \033[90m1 3 5\033[0m"
hr
printf "\n  Your selection: "
read -r SELECTION

[[ "$SELECTION" == "q" || -z "$SELECTION" ]] && { echo "Aborted."; exit 0; }

# Build list of indices to delete
if [[ "$SELECTION" == "a" ]]; then
  INDICES=()
  for i in $(seq 1 "$TOTAL"); do INDICES+=("$i"); done
else
  IFS=' ' read -ra INDICES <<< "$SELECTION"
fi

# Validate indices
for idx in "${INDICES[@]}"; do
  if ! [[ "$idx" =~ ^[0-9]+$ ]] || [[ "$idx" -lt 1 ]] || [[ "$idx" -gt "$TOTAL" ]]; then
    die "Invalid selection: $idx  (valid range: 1–${TOTAL})"
  fi
done

# ── 5. Confirm ────────────────────────────────────────────────
echo -e "\n  \033[1;31mThe following will be deleted:\033[0m"
for idx in "${INDICES[@]}"; do
  i=$(( idx - 1 ))
  if [[ "$i" -lt "${#LOCAL_TAGS[@]}" ]]; then
    echo "    [LOCAL]  ${IMAGE_NAME}:${LOCAL_TAGS[$i]}"
  else
    r=$(( i - ${#LOCAL_TAGS[@]} ))
    echo "    [REMOTE] ${IMAGE_NAME}:${REMOTE_TAGS[$r]}  (on ${REMOTE_HOST})"
  fi
done

echo
printf "  Confirm deletion? [y/N]: "
read -r CONFIRM
[[ "${CONFIRM,,}" != "y" ]] && { echo "Aborted."; exit 0; }

# ── 6. Delete ─────────────────────────────────────────────────
REMOTE_TO_DELETE=()

for idx in "${INDICES[@]}"; do
  i=$(( idx - 1 ))

  if [[ "$i" -lt "${#LOCAL_TAGS[@]}" ]]; then
    TAG="${LOCAL_TAGS[$i]}"
    info "Deleting local image  ${IMAGE_NAME}:${TAG}..."
    docker rmi "${IMAGE_NAME}:${TAG}" && success "Deleted local: ${IMAGE_NAME}:${TAG}" \
      || warn "Could not delete (image may be in use)"
  else
    r=$(( i - ${#LOCAL_TAGS[@]} ))
    REMOTE_TO_DELETE+=("${REMOTE_TAGS[$r]}")
  fi
done

# Batch remote deletions in a single SSH call
if [[ ${#REMOTE_TO_DELETE[@]} -gt 0 ]]; then
  info "Deleting remote images on ${REMOTE_HOST}..."
  CMDS=""
  for tag in "${REMOTE_TO_DELETE[@]}"; do
    FULL_REF="docker.io/library/${IMAGE_NAME}:${tag}"
    CMDS+="sudo ctr -n k8s.io images rm '${FULL_REF}' && echo 'Deleted: ${tag}' || echo 'Failed: ${tag}'; "
  done
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "bash -c \"${CMDS}\""
fi

echo
success "Done. Run the script again to verify."
