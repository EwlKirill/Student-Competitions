#!/usr/bin/env bash
# Protect `main` so a failing check prevents a merge rather than merely reporting one (FR-016).
#
# Branch protection is configured outside the repository, so this script is the closest thing to
# infrastructure as code the platform allows: reviewable, re-runnable and self-documenting about
# which contexts are required. Settings table:
# specs/002-public-deploy-cicd/contracts/pipeline.md#branch-protection-the-gate-itself
#
# Idempotent — a PUT replaces the whole rule, so running it twice leaves the same state.
#
# Usage:  ./scripts/setup_branch_protection.sh [owner/repo]
#         (the repository is inferred from the current checkout when omitted)
set -euo pipefail

BRANCH="main"

# The status-check contexts, named `<workflow job name>` as GitHub reports them for a called
# reusable workflow: the calling job is `checks`, and its jobs are `quality` and `image`.
REQUIRED_CHECKS=("checks / quality" "checks / image")

# The project has a single active contributor. A rule nobody can satisfy gets switched off rather
# than followed, so approvals stay at 0 — one number to change when the team grows.
REQUIRED_APPROVALS=0

if ! command -v gh >/dev/null 2>&1; then
  cat >&2 <<'EOF'
error: the GitHub CLI (`gh`) is not installed.

  Install it from https://cli.github.com and run `gh auth login`, or apply the same settings by
  hand: specs/002-public-deploy-cicd/quickstart.md, bootstrap step B3.
EOF
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  cat >&2 <<'EOF'
error: the GitHub CLI is not authenticated.

  Run `gh auth login` and try again. The account needs admin rights on the repository.
EOF
  exit 1
fi

REPO="${1:-}"
if [ -z "$REPO" ]; then
  if ! REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null); then
    echo "error: could not infer the repository. Pass it explicitly: $0 owner/repo" >&2
    exit 1
  fi
fi

echo "Applying branch protection to ${REPO}@${BRANCH}…"

# Built as JSON rather than interpolated into a string so a context containing a space survives.
payload=$(
  REQUIRED_APPROVALS="$REQUIRED_APPROVALS" python3 - "${REQUIRED_CHECKS[@]}" <<'PY'
import json
import os
import sys

print(
    json.dumps(
        {
            # Both jobs must pass, and `strict` requires the branch to be up to date with main
            # first — this is what catches two independently green pull requests that conflict
            # only once combined.
            "required_status_checks": {"strict": True, "contexts": sys.argv[1:]},
            # Applies the rule to administrators too. `None` here would leave enforcement at
            # "non_admins", which on a single-admin repository means the gate prevents nobody
            # and FR-016 ("a failing check MUST prevent a merge") is hollow.
            #
            # Quickstart V8 deliberately forces a broken image build onto `main`. Untick
            # "Do not allow bypassing the above settings" for that one experiment, then re-run
            # this script to put the gate back up.
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "required_approving_review_count": int(os.environ["REQUIRED_APPROVALS"]),
                "dismiss_stale_reviews": False,
                "require_code_owner_reviews": False,
            },
            "restrictions": None,
            # Release history is not rewritten, and the branch cannot be deleted.
            "allow_force_pushes": False,
            "allow_deletions": False,
        }
    )
)
PY
)

if ! printf '%s' "$payload" |
  gh api --method PUT "repos/${REPO}/branches/${BRANCH}/protection" --input - >/dev/null; then
  cat >&2 <<EOF

error: could not apply branch protection to ${REPO}@${BRANCH}.

  Common causes:
    - The status-check contexts do not exist yet. They only appear after the workflows have run
      once — open a throwaway pull request first, then re-run this script.
    - The repository is private on a free GitHub plan. Branch protection is free for public
      repositories only; there is no implementation-side workaround (research D13).
    - The authenticated account does not have admin rights on the repository.
EOF
  exit 1
fi

echo "Done. ${BRANCH} now requires: ${REQUIRED_CHECKS[*]} (strict), a pull request, and"
echo "${REQUIRED_APPROVALS} approvals; force pushes and deletions are blocked."
