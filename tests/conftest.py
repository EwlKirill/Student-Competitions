"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Drive the real ASGI application in-process — no live server, no bound port."""
    with TestClient(app) as test_client:
        yield test_client
