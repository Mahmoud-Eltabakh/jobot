"""Canonical full-page route coverage for the authenticated workspace."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("path", "active_page", "fragment_path"),
    [
        ("/dashboard", "dashboard", "/web/views/kanban"),
    ],
)
def test_authenticated_workspace_pages_render_full_shell(
    authenticated_client: TestClient,
    path: str,
    active_page: str,
    fragment_path: str,
) -> None:
    """Canonical workspace URLs render the shared shell and their composition point."""
    response = authenticated_client.get(path)

    assert response.status_code == 200
    assert "<html" in response.text
    assert 'id="popup-notifications"' in response.text
    assert 'id="modal-container"' in response.text
    assert 'id="inspector-drawer"' in response.text
    assert f'data-page="{active_page}"' in response.text
    assert f'hx-get="{fragment_path}"' in response.text
    for destination in ("/dashboard", "/jobs/board", "/jobs/table", "/queue", "/profile", "/settings"):
        assert f'href="{destination}"' in response.text


@pytest.mark.parametrize(
    "path",
    ["/dashboard"],
)
def test_anonymous_workspace_pages_follow_authentication_policy(
    client: TestClient,
    path: str,
) -> None:
    """Workspace pages never expose a document to callers without a session."""
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 401


def test_root_redirects_authenticated_visitors_to_dashboard(
    authenticated_client: TestClient,
) -> None:
    """The legacy root remains a compatibility entry point for signed-in users."""
    response = authenticated_client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_root_preserves_first_run_registration_redirect(client: TestClient) -> None:
    """The first anonymous visitor still starts with account registration."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/register"