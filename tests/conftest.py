"""Shared pytest fixtures."""

from collections.abc import Iterator
from importlib import import_module
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import database
from app.main import app


@pytest.fixture
def provider_transport(monkeypatch):
    """Intercept native HTTPX and the installed OpenAI SDK's actual backend.

    The SDK may use httpx2 rather than httpx. Patch transport selection on
    both classes before constructing adapters, including short-lived probes.
    Unexpected requests must fail in the handler, never fall through to I/O.
    """
    import httpx
    import openai

    sdk_backend = next(base.__module__.partition(".")[0]
                       for base in openai.DefaultAsyncHttpxClient.__mro__
                       if base.__name__ == "AsyncClient")

    def install(handler):
        for module_name in {"httpx", sdk_backend}:
            backend = import_module(module_name)

            def respond(request, backend=backend):
                result = handler(request)
                if isinstance(result, httpx.Response):
                    return backend.Response(result.status_code, headers=dict(result.headers), content=result.content)
                return result

            transport = backend.MockTransport(respond)

            def select_transport(client, url, transport=transport):
                assert client.follow_redirects is False
                return transport

            monkeypatch.setattr(backend.AsyncClient, "_transport_for_url", select_transport)

    return install


@pytest.fixture(autouse=True)
def clean_database_tables() -> None:
    """Ensure clean table state before each test run to avoid unique constraint collisions."""
    database.init_db()
    with database.engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())
    with database.Session(database.engine) as session:
        database.seed_default_settings(session)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


def register_test_account(test_client: TestClient) -> dict[str, Any]:
    """Register a real account and leave its session cookie on the client."""
    response = test_client.post(
        "/api/auth/register",
        json={
            "email": "authenticated-test@example.com",
            "password": "AuthenticatedPassword123",
            "full_name": "Authenticated Test User",
        },
    )
    assert response.status_code == 200, response.text
    assert "jobot_session" in test_client.cookies
    return response.json()


@pytest.fixture
def authenticated_client() -> Iterator[TestClient]:
    """Yield a client authenticated through the public registration API."""
    with TestClient(app) as test_client:
        register_test_account(test_client)
        yield test_client


@pytest.fixture
def authenticated_user(authenticated_client: TestClient) -> dict[str, Any]:
    """Return the account represented by the authenticated client's session."""
    response = authenticated_client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    return response.json()
