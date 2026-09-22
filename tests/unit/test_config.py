"""Configuration read from the environment.

See specs/002-public-deploy-cicd/data-model.md#1-configuration-read-from-the-environment.

`app.core.config` resolves `COMMIT_SHA` once, at import time, so every case below reloads the
module under a prepared environment rather than importing it once and expecting it to change.
"""

import importlib
import tomllib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

import app.core.config as config

PYPROJECT = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"

SHA = "9f2c1ab3e4d5678901234567890abcdef1234567"
OTHER_SHA = "0123456789abcdef0123456789abcdef01234567"


def reload_config(
    monkeypatch: pytest.MonkeyPatch, app_commit: str | None, render_commit: str | None
) -> ModuleType:
    """Reload `app.core.config` with the two commit variables set, or absent when `None`."""
    for name, value in (("APP_COMMIT", app_commit), ("RENDER_GIT_COMMIT", render_commit)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def _restore_config() -> Iterator[None]:
    """Leave the module as the rest of the suite found it, whatever a test set."""
    yield
    importlib.reload(config)


def test_app_version_matches_pyproject() -> None:
    """The version `/healthz` reports is the project's version, not a second source of truth."""
    with PYPROJECT.open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert config.APP_VERSION == pyproject["project"]["version"]


def test_app_commit_wins_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    reloaded = reload_config(monkeypatch, app_commit=SHA, render_commit=OTHER_SHA)
    assert reloaded.COMMIT_SHA == SHA


def test_empty_app_commit_falls_through_to_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ARG APP_COMMIT=""` means an unstamped build leaves it empty — empty must not win."""
    reloaded = reload_config(monkeypatch, app_commit="", render_commit=SHA)
    assert reloaded.COMMIT_SHA == SHA


def test_unset_app_commit_falls_through_to_render(monkeypatch: pytest.MonkeyPatch) -> None:
    reloaded = reload_config(monkeypatch, app_commit=None, render_commit=SHA)
    assert reloaded.COMMIT_SHA == SHA


def test_empty_render_commit_yields_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    reloaded = reload_config(monkeypatch, app_commit="", render_commit="")
    assert reloaded.COMMIT_SHA == "unknown"


def test_unset_commit_variables_yield_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The honest answer for `uv run uvicorn` in a checkout."""
    reloaded = reload_config(monkeypatch, app_commit=None, render_commit=None)
    assert reloaded.COMMIT_SHA == "unknown"


@pytest.mark.parametrize(
    ("app_commit", "render_commit"),
    [(SHA, OTHER_SHA), ("", SHA), (None, SHA), ("", ""), (None, None), (SHA, None)],
)
def test_commit_sha_is_never_empty(
    monkeypatch: pytest.MonkeyPatch, app_commit: str | None, render_commit: str | None
) -> None:
    """A consumer must always have something to print, whatever the environment holds."""
    reloaded = reload_config(monkeypatch, app_commit=app_commit, render_commit=render_commit)
    assert reloaded.COMMIT_SHA
