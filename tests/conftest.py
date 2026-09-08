"""Shared pytest fixtures."""

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


@pytest.fixture
def client() -> TestClient:
    """Return FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client
