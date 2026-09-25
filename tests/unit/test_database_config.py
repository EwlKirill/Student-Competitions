"""Where the database is, and when to refuse to start.

See specs/003-database-questions/contracts/configuration.md. Every case passes an explicit
environment rather than reading `os.environ`.

The module is used through `config.` at call time rather than imported by name: `test_config.py`
reloads `app.core.config`, which replaces `DatabaseConfigError` with a new class object.
"""

from pathlib import Path

import pytest

import app.core.config as config

PASSWORD = "s3cr3t-pa55"
HOST = "ep-secret-host.example"
QUERY = "?sslmode=require&channel_binding=require"
NEON_STYLE = f"neondb_owner:{PASSWORD}@{HOST}:5432/neondb{QUERY}"


def resolve(**environ: str) -> str:
    return config.resolve_database_url(environ)


def expected_default() -> str:
    root = Path(config.__file__).resolve().parent.parent.parent
    return f"sqlite:///{root / 'data' / 'student_competitions.sqlite3'}"


def test_sqlite_url_is_returned_unchanged(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'x.sqlite3'}"
    assert resolve(DATABASE_URL=url) == url


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_postgres_schemes_are_rewritten_to_psycopg(scheme: str) -> None:
    """Neon and CI hand out `postgresql://`; everything after the scheme survives exactly."""
    assert resolve(DATABASE_URL=f"{scheme}://{NEON_STYLE}") == f"postgresql+psycopg://{NEON_STYLE}"


def test_psycopg_url_is_returned_unchanged() -> None:
    url = f"postgresql+psycopg://{NEON_STYLE}"
    assert resolve(DATABASE_URL=url) == url


@pytest.mark.parametrize("environ", [{}, {"DATABASE_URL": ""}])
def test_default_is_the_local_sqlite_file(environ: dict[str, str]) -> None:
    assert config.resolve_database_url(environ) == expected_default()


def test_default_is_anchored_to_the_project_not_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve() == expected_default()
    assert not (tmp_path / "data").exists()


def test_default_path_is_under_the_project_root() -> None:
    assert (
        config.DEFAULT_SQLITE_PATH == config.PROJECT_ROOT / "data" / "student_competitions.sqlite3"
    )
    assert (config.PROJECT_ROOT / "app" / "__init__.py").is_file()


@pytest.mark.parametrize("render", ["true", "1"])
@pytest.mark.parametrize("database_url", [None, ""])
def test_render_without_a_url_refuses_to_fall_back(render: str, database_url: str | None) -> None:
    environ = {"RENDER": render}
    if database_url is not None:
        environ["DATABASE_URL"] = database_url
    with pytest.raises(config.DatabaseConfigError, match="DATABASE_URL is required"):
        config.resolve_database_url(environ)


def test_render_with_a_url_uses_it() -> None:
    assert resolve(DATABASE_URL=f"postgresql://{NEON_STYLE}", RENDER="true").startswith(
        "postgresql+psycopg://"
    )


def test_unparseable_url_is_refused() -> None:
    with pytest.raises(config.DatabaseConfigError, match="not a valid database URL"):
        resolve(DATABASE_URL=f"not a url {PASSWORD}")


@pytest.mark.parametrize("scheme", ["mysql", "sqlite+aiosqlite"])
def test_unsupported_scheme_is_refused_naming_only_the_scheme(scheme: str) -> None:
    with pytest.raises(config.DatabaseConfigError) as caught:
        resolve(DATABASE_URL=f"{scheme}://{NEON_STYLE}")
    assert f"unsupported scheme '{scheme}'" in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        f"mysql://{NEON_STYLE}",
        f"postgresql://neondb_owner:{PASSWORD}@{HOST}:notaport/neondb",
        f"://{PASSWORD}@{HOST}",
    ],
    ids=["unsupported-scheme", "bad-port", "no-scheme"],
)
def test_errors_never_reveal_any_part_of_the_url(url: str) -> None:
    """The message reaches deploy logs, so it carries neither the password nor the host, and
    SQLAlchemy's parse error — which quotes the URL — is not chained (FR-004, FR-032)."""
    with pytest.raises(config.DatabaseConfigError) as caught:
        resolve(DATABASE_URL=url)
    exc = caught.value
    for rendered in (str(exc), repr(exc)):
        assert PASSWORD not in rendered
        assert HOST not in rendered
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True


def test_database_config_error_is_a_runtime_error() -> None:
    assert issubclass(config.DatabaseConfigError, RuntimeError)
