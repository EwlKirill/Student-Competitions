#!/usr/bin/env bash
# Ask Render to deploy one exact commit, by calling the service's deploy hook.
#
# The hook URL is a credential: it deploys the service for anyone holding it. It is read from the
# RENDER_DEPLOY_HOOK_URL environment variable and never taken as an argument, so it cannot appear
# in a process listing, a shell history or a workflow log (FR-027). Nothing here ever prints it.
#
# Rationale: research D2. Contract: specs/002-public-deploy-cicd/contracts/pipeline.md
#
# Usage:  RENDER_DEPLOY_HOOK_URL=… ./scripts/render_deploy.sh <commit-sha>
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: RENDER_DEPLOY_HOOK_URL=… $0 <commit-sha>" >&2
  exit 2
fi

COMMIT_SHA="$1"

if [ -z "${RENDER_DEPLOY_HOOK_URL:-}" ]; then
  cat >&2 <<'EOF'
error: RENDER_DEPLOY_HOOK_URL is not set.

  It is the `production` environment secret holding the service's deploy hook URL
  (Render → the service → Settings → Deploy hook). See the quickstart, bootstrap step B2.
EOF
  exit 1
fi

# `ref` pins the release to one commit rather than "whatever the branch points at now", which is
# what makes "the newest commit wins" checkable. The hook URL already carries a `key=` query
# parameter, so this is appended with `&`, not `?`.
echo "Triggering a Render deploy of ${COMMIT_SHA}…"

response_body=$(mktemp)
curl_stderr=$(mktemp)
trap 'rm -f "$response_body" "$curl_stderr"' EXIT

curl_exit=0
status=$(
  curl -sS -X POST \
    -o "$response_body" \
    -w '%{http_code}' \
    --max-time 30 \
    "${RENDER_DEPLOY_HOOK_URL}&ref=${COMMIT_SHA}" \
    2>"$curl_stderr"
) || curl_exit=$?

if [ "$curl_exit" -ne 0 ]; then
  # Render was not reached at all (DNS, TLS, timeout). Curl's own message is useful, but it is
  # redacted first in case it echoed the URL back — it carries the hook key.
  echo "error: the deploy hook could not be reached (curl exit ${curl_exit})." >&2
  sed "s|${RENDER_DEPLOY_HOOK_URL}|<deploy-hook-url>|g" "$curl_stderr" >&2
  exit 1
fi

body=$(cat "$response_body")

case "$status" in
  200)
    echo "Deploy started (HTTP 200)."
    ;;
  202)
    # Another deploy is already running; Render will pick this one up after it.
    echo "Deploy queued behind a running deploy (HTTP 202)."
    ;;
  *)
    # The body is safe to print; the URL is not, and is deliberately absent from this message.
    echo "error: the deploy hook returned HTTP ${status}. Response body: ${body}" >&2
    echo "  401 means the hook key is wrong or missing; 404 means the service or the commit" >&2
    echo "  SHA was not found; 400 means the parameters were rejected." >&2
    exit 1
    ;;
esac

echo "Response body: ${body}"

# The deploy id is the operator's link into Render's deploy history, so surface it on its own
# line. `jq` is not guaranteed to be present wherever this runs, so failing to parse is not fatal.
if command -v jq >/dev/null 2>&1; then
  deploy_id=$(printf '%s' "$body" | jq -r '.deploy.id // .id // empty' 2>/dev/null || true)
  if [ -n "$deploy_id" ]; then
    echo "Render deploy id: ${deploy_id}"
  fi
fi
