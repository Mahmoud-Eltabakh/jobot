"""Shared pytest fixtures."""

import os

# Force all tests to run against an in-memory SQLite database
# Must be set BEFORE importing any application modules that instantiate the engine
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import database
from app.main import app


@pytest.fixture(autouse=True)
def clean_database_tables() -> None:
    """Ensure clean table state before each test run to avoid unique constraint collisions."""
    database.init_db()
    with database.engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())
    database.init_db()


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
