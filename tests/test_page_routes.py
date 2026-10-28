"""Canonical full-page route coverage for the authenticated workspace."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import engine
from app.db.models import Job, JobStatus


@pytest.mark.parametrize(
    ("path", "active_page", "fragment_path"),
    [
        ("/dashboard", "dashboard", "/web/views/kanban"),
        ("/jobs/board", "jobs-board", "/web/views/kanban"),
        ("/jobs/table", "jobs-table", "/web/views/table"),
        ("/queue", "queue", "/web/views/queue"),
        ("/profile", "profile", "/web/views/profile"),
        ("/settings", "settings", "/web/views/settings"),
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
    ["/dashboard", "/jobs/board", "/jobs/table", "/queue", "/profile", "/settings"],
)
def test_anonymous_workspace_pages_follow_authentication_policy(
    client: TestClient,
    path: str,
) -> None:
    """Workspace pages never expose a document to callers without a session."""
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 401


def test_table_filter_bar_preserves_the_table_fragment_destination(
    authenticated_client: TestClient,
) -> None:
    """Table filtering remains within the sortable table rather than switching views."""
    response = authenticated_client.get("/web/components/filter-bar?view=table")

    assert response.status_code == 200
    assert 'hx-get="/web/views/table"' in response.text


def test_table_page_preserves_filter_and_sort_state_on_direct_navigation(
    authenticated_client: TestClient,
    authenticated_user: dict,
) -> None:
    """A bookmarked table URL initializes the matching toolbar and fragment state."""
    with Session(engine) as session:
        session.add(Job(
            user_id=authenticated_user["id"],
            source="linkedin",
            title="Python State Sentinel",
            company="Stateful Jobs",
            location="Berlin",
            url="https://example.test/jobs/table-state",
            status=JobStatus.NEW.value,
            fit_score=81,
            dedup_hash="phase25-table-state",
        ))
        session.commit()

    response = authenticated_client.get(
        "/jobs/table?q=Python+State+Sentinel&sort_by=created_at&sort_order=asc"
    )

    assert response.status_code == 200
    assert 'hx-get="/web/views/table?q=Python+State+Sentinel&amp;sort_by=created_at&amp;sort_order=asc"' in response.text
    assert 'hx-get="/web/components/filter-bar?view=table&amp;q=Python+State+Sentinel&amp;sort_by=created_at&amp;sort_order=asc"' in response.text

    fragment = authenticated_client.get(
        "/web/views/table?q=Python+State+Sentinel&sort_by=created_at&sort_order=asc"
    )
    filter_bar = authenticated_client.get(
        "/web/components/filter-bar?view=table&q=Python+State+Sentinel"
    )
    assert "Python State Sentinel" in fragment.text
    assert 'value="Python State Sentinel"' in filter_bar.text


def test_legacy_filter_bar_defaults_to_the_kanban_fragment(
    authenticated_client: TestClient,
) -> None:
    """Existing consumers without a page selector retain their Kanban contract."""
    response = authenticated_client.get("/web/components/filter-bar")

    assert response.status_code == 200
    assert 'hx-get="/web/views/kanban"' in response.text


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