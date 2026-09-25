#!/usr/bin/env bash
# Read and check the database status line on the public home page.
#
# The deploy job reads the boot count before a release and checks after it that the page shows
# the expected schema revision and a strictly higher count, so "the data survived the redeploy"
# is asserted on every release rather than observed once by hand (SC-002). It reads only the
# public HTML, so it needs no credential and prints none.
# Contract: specs/003-database-questions/contracts/pipeline.md#scriptsdatabase_statussh
#
# Usage:  ./scripts/database_status.sh boot-count <base-url>
#         ./scripts/database_status.sh verify <base-url> <revision> [<previous-boots>]
set -euo pipefail

usage() {
  echo "usage: $0 boot-count <base-url>" >&2
  echo "       $0 verify <base-url> <revision> [<previous-boots>]" >&2
  exit 2
}

# A free instance may be spinning up from cold, so a single request is allowed to take a while.
REQUEST_TIMEOUT=60
# How long `verify` keeps retrying for a 200 after the release has been confirmed.
VERIFY_DEADLINE_SECONDS=60
RETRY_INTERVAL=5

UNAVAILABLE_NOTICE="Question data is temporarily unavailable"

page=$(mktemp)
trap 'rm -f "$page"' EXIT

# GET <url> into $page; print the HTTP status. curl itself prints 000 when there was no response
# at all, and exits non-zero, which must not end the script.
fetch() {
  : >"$page"
  curl -sS -o "$page" -w '%{http_code}' --max-time "$REQUEST_TIMEOUT" "$1" 2>/dev/null || true
}

# Print the value of a data-* attribute of the status line, or nothing.
attribute() {
  sed -n "s/.*class=\"db-status\"[^>]*$1=\"\([^\"]*\)\".*/\1/p" "$page" | head -n 1
}

excerpt() {
  sed -n '/class="db-status"/p' "$page" | head -c 500
  if ! grep -q 'class="db-status"' "$page"; then
    head -c 500 "$page"
  fi
}

boot_count() {
  local url="$1/"
  # Best effort: an old release without a status line, or one that does not answer, gives an
  # empty value and the caller skips the comparison. Never fails.
  if [ "$(fetch "$url")" = "200" ]; then
    attribute data-boots
  fi
}

verify() {
  local url="$1/" expected_revision="$2" previous_boots="${3:-}"
  local started_at status elapsed
  started_at=$(date +%s)

  while true; do
    status=$(fetch "$url")
    [ "$status" = "200" ] && break
    elapsed=$(($(date +%s) - started_at))
    if [ "$elapsed" -ge "$VERIFY_DEADLINE_SECONDS" ]; then
      echo "error: GET $url returned $status (expected 200) for ${VERIFY_DEADLINE_SECONDS}s." >&2
      echo "Page excerpt: $(head -c 500 "$page" 2>/dev/null || true)" >&2
      exit 1
    fi
    echo "[${elapsed}s] GET $url returned $status; retrying…"
    sleep "$RETRY_INTERVAL"
  done

  if grep -q "$UNAVAILABLE_NOTICE" "$page"; then
    echo "error: GET $url shows the notice '$UNAVAILABLE_NOTICE' (expected the question data)." >&2
    echo "Page excerpt: $(excerpt)" >&2
    exit 1
  fi

  local revision boots
  revision=$(attribute data-revision)
  boots=$(attribute data-boots)

  if [ "$revision" != "$expected_revision" ]; then
    echo "error: GET $url shows schema revision '${revision:-<none>}'" \
      "(expected '$expected_revision')." >&2
    echo "Page excerpt: $(excerpt)" >&2
    exit 1
  fi
  echo "Schema revision: $revision (expected $expected_revision)."

  if [ -z "$previous_boots" ]; then
    echo "Boot count: $boots (no previous boot count to compare with)."
  elif ! [[ "$boots" =~ ^[0-9]+$ ]] || [ "$boots" -le "$previous_boots" ]; then
    echo "error: GET $url shows boot count '${boots:-<none>}'" \
      "(expected more than the previous $previous_boots)." >&2
    echo "Page excerpt: $(excerpt)" >&2
    exit 1
  else
    echo "Boot count: $previous_boots → $boots."
  fi

  echo "Data verified."
}

[ "$#" -ge 1 ] || usage
command="$1"
shift

case "$command" in
  boot-count)
    [ "$#" -eq 1 ] || usage
    boot_count "${1%/}"
    ;;
  verify)
    [ "$#" -eq 2 ] || [ "$#" -eq 3 ] || usage
    verify "${1%/}" "$2" "${3:-}"
    ;;
  *)
    usage
    ;;
esac
