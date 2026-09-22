"""Application constants: user-facing strings, and the release identity `/healthz` reports.

Single source of truth for the name, tagline and description that appear on the page, in the
browser tab and in the test assertions — those are literals, so the application still starts with
no configuration at all (FR-010).

Two values do come from the environment, and this module is the only place that reads it:
`COMMIT_SHA` answers "which commit is live" (FR-025), resolved once at import time. See
specs/002-public-deploy-cicd/data-model.md#1-configuration-read-from-the-environment.
"""

import os

APP_NAME = "Student Competitions"

APP_TAGLINE = "Online knowledge competitions for students."

APP_DESCRIPTION = (
    "Student Competitions is a web application for running online knowledge competitions in "
    "schools and universities. Teachers build a question bank and open a competition, students "
    "answer the questions in writing, and every answer is scored automatically."
)

APP_VERSION = "0.1.0"
"""The release number reported by `/healthz`. Equals `project.version` in `pyproject.toml`,
which `tests/unit/test_config.py` asserts."""

COMMIT_SHA = os.environ.get("APP_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"
"""The commit the running instance was built from.

`APP_COMMIT` (a local or CI `docker build --build-arg`) wins, then `RENDER_GIT_COMMIT` (set
automatically by Render for every deploy), then the literal `"unknown"`. `or` rather than a
default argument is deliberate: the Dockerfile declares `ARG APP_COMMIT=""`, so an unstamped
build sets the variable to an empty string, and empty must fall through rather than win.
"""
