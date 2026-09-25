"""No route writes anything yet (FR-018, FR-033).

Checked over the whole route table rather than per route, so a write route added by mistake
fails here whatever its path. The question operations exist, but nothing can reach them over
HTTP until milestone 6 adds them behind a role check.
"""

from starlette.routing import Mount

from app.main import app

READ_ONLY_METHODS = {"GET", "HEAD"}


def test_every_route_is_read_only() -> None:
    offending = {
        route.path: sorted(route.methods - READ_ONLY_METHODS)
        for route in app.routes
        if getattr(route, "methods", None) and route.methods - READ_ONLY_METHODS
    }
    assert not offending, f"routes accepting a write method: {offending}"


def test_the_static_files_are_the_only_mount() -> None:
    mounts = [route.path for route in app.routes if isinstance(route, Mount)]
    assert mounts == ["/static"]
