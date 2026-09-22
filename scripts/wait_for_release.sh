#!/usr/bin/env bash
# Prove a deploy actually landed: poll the public /healthz until it reports the deployed commit.
#
# Without this, a green pipeline would mean only "Render accepted the request" — a hook call that
# returns 200 before a build that fails four minutes later would be a green workflow over a stale
# site. Polling the application rather than Render's API checks what a visitor actually gets, and
# keeps the pipeline free of a workspace-scoped API key (research D15).
#
# Usage:  ./scripts/wait_for_release.sh <base-url> <commit-sha>
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <base-url> <commit-sha>" >&2
  exit 2
fi

# Tolerate a trailing slash in PUBLIC_BASE_URL rather than producing `//healthz`.
BASE_URL="${1%/}"
EXPECTED_SHA="$2"

# Sits inside SC-007's 15 minutes and outside the realistic worst case: a cold multi-minute image
# build plus a free instance's ~1-minute start.
DEADLINE_SECONDS=$((12 * 60))

# A free instance may be spinning up from cold, so a single request is allowed to take a while.
REQUEST_TIMEOUT=60

# Backoff between attempts, in seconds: quick at first, then patient while Render builds.
INITIAL_INTERVAL=5
MAX_INTERVAL=20

HEALTH_URL="${BASE_URL}/healthz"
started_at=$(date +%s)
interval=$INITIAL_INTERVAL
attempt=0
last_report="no response received yet"

echo "Waiting for ${HEALTH_URL} to report commit ${EXPECTED_SHA} (deadline: ${DEADLINE_SECONDS}s)…"

response_body=$(mktemp)
trap 'rm -f "$response_body"' EXIT

while true; do
  attempt=$((attempt + 1))
  elapsed=$(($(date +%s) - started_at))

  if [ "$elapsed" -ge "$DEADLINE_SECONDS" ]; then
    cat >&2 <<EOF

error: ${HEALTH_URL} did not report commit ${EXPECTED_SHA} within ${DEADLINE_SECONDS}s
       (${attempt} attempts).

Last response seen: ${last_report}

Render accepted the deploy but the public address is not serving this commit. Look at the
service's deploy log in Render before merging anything else — the previous version is still
serving, so visitors are not seeing an error.
EOF
    exit 1
  fi

  # On a failed connection curl exits non-zero; `|| status=…` replaces the value rather than
  # appending to it, so the "no response at all" case below can recognise itself.
  status=$(
    curl -sS -o "$response_body" -w '%{http_code}' --max-time "$REQUEST_TIMEOUT" "$HEALTH_URL" \
      2>/dev/null
  ) || status="000"
  body=$(head -c 500 "$response_body" 2>/dev/null || true)

  if [ "$status" = "200" ]; then
    reported_sha=$(printf '%s' "$body" | sed -n 's/.*"commit"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    last_report="HTTP ${status}, commit '${reported_sha:-<unparseable>}', body: ${body}"

    if [ "$reported_sha" = "$EXPECTED_SHA" ]; then
      echo "[${elapsed}s] ${HEALTH_URL} is serving ${EXPECTED_SHA}."
      echo "Release verified."
      exit 0
    fi

    echo "[${elapsed}s] attempt ${attempt}: serving '${reported_sha}', waiting for '${EXPECTED_SHA}'."
  elif [ "$status" = "000" ]; then
    # No HTTP response at all: the instance is restarting, or the request timed out.
    last_report="no HTTP response (connection failed or timed out after ${REQUEST_TIMEOUT}s)"
    echo "[${elapsed}s] attempt ${attempt}: ${last_report}."
  else
    last_report="HTTP ${status}, body: ${body}"
    echo "[${elapsed}s] attempt ${attempt}: ${last_report}."
  fi

  sleep "$interval"
  if [ "$interval" -lt "$MAX_INTERVAL" ]; then
    interval=$((interval * 2))
    if [ "$interval" -gt "$MAX_INTERVAL" ]; then
      interval=$MAX_INTERVAL
    fi
  fi
done
