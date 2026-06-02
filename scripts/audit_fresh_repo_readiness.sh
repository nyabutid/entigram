#!/usr/bin/env zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
REPOS=(
  "$ROOT/entigram"
  "$ROOT/entigram-registry"
  "$ROOT/entigram-standard-packages"
  "$ROOT/homebrew-entigram"
)

LEGACY='[Mm][Aa][Kk][Ii][Nn][Ii]'
LEGACY_WORD="m""akini"
PATTERN="${LEGACY}|@${LEGACY}|api\\.${LEGACY}|${LEGACY}\\.ai|${LEGACY}-standard|${LEGACY}-ai|${LEGACY}_ARCHITECTURE"

audit_status=0

echo "Fresh repository readiness audit"
echo

for repo in "${REPOS[@]}"; do
  echo "== ${repo}"
  if [[ ! -d "$repo" ]]; then
    echo "missing repository directory"
    audit_status=1
    continue
  fi

  if rg -n "$PATTERN" "$repo" \
    --glob '!/.git/**' \
    --glob '!*.db' \
    --glob '!*.tar.gz' \
    --glob '!*.pyc' \
    --glob '!__pycache__/**'; then
    echo "found stale legacy-brand references"
    audit_status=1
  else
    echo "no stale legacy-brand references found"
  fi

  if find "$repo" -path '*/.git' -prune -o -iname "*${LEGACY_WORD}*" -print | rg .; then
    echo "found stale legacy-brand path names"
    audit_status=1
  else
    echo "no stale legacy-brand path names found"
  fi

  echo
done

if command -v node >/dev/null 2>&1; then
  node --input-type=module --check < "$ROOT/entigram-registry/worker/src/index.js" || audit_status=1
else
  echo "node not found; skipped Worker syntax check"
fi

if command -v terraform >/dev/null 2>&1; then
  terraform -chdir="$ROOT/entigram-registry/terraform" fmt -check || audit_status=1
else
  echo "terraform not found; skipped Terraform fmt check"
fi

exit "$audit_status"
