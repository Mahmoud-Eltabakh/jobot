"""Canonical full-page route coverage for the authenticated workspace."""

import json
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.database import engine
from app.db.models import Job, JobStatus, ScrapeTask, UserProfile, UserSetting
from app.main import app


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


def test_job_and_queue_composition_remains_owner_scoped(
    authenticated_client: TestClient,
    authenticated_user: dict,
) -> None:
    """Canonical job and queue pages compose only the authenticated account's data."""
    with TestClient(app) as second_client:
        registration = second_client.post(
            "/api/auth/register",
            json={
                "email": "phase25-second@example.com",
                "password": "SecondAccountPassword123",
                "full_name": "Phase 25 Second",
            },
        )
        assert registration.status_code == 200
        second_user = registration.json()

        with Session(engine) as session:
            first_job = Job(
                user_id=authenticated_user["id"], source="linkedin", title="First Job Sentinel",
                company="First Co", location="Berlin", url="https://example.test/first-job",
                status=JobStatus.NEW.value, fit_score=91, dedup_hash="phase25-first-job",
            )
            second_job = Job(
                user_id=second_user["id"], source="linkedin", title="Second Job Sentinel",
                company="Second Co", location="Hamburg", url="https://example.test/second-job",
                status=JobStatus.NEW.value, fit_score=82, dedup_hash="phase25-second-job",
            )
            first_task = ScrapeTask(
                user_id=authenticated_user["id"], task_type="scrape_query",
                payload_json=json.dumps({"keywords": "First Queue Sentinel"}), status="failed",
            )
            second_task = ScrapeTask(
                user_id=second_user["id"], task_type="scrape_query",
                payload_json=json.dumps({"keywords": "Second Queue Sentinel"}), status="failed",
            )
            session.add_all([first_job, second_job, first_task, second_task])
            session.commit()
            session.refresh(first_job)
            session.refresh(first_task)

        for client, own_job, other_job, own_task, other_task in (
            (authenticated_client, "First Job Sentinel", "Second Job Sentinel", "First Queue Sentinel", "Second Queue Sentinel"),
            (second_client, "Second Job Sentinel", "First Job Sentinel", "Second Queue Sentinel", "First Queue Sentinel"),
        ):
            assert 'hx-get="/web/views/table"' in client.get("/jobs/table").text
            assert 'hx-get="/web/views/queue"' in client.get("/queue").text
            table = client.get("/web/views/table")
            queue = client.get("/web/views/queue")
            assert own_job in table.text and other_job not in table.text
            assert own_task in queue.text and other_task not in queue.text

        assert second_client.get(f"/web/job/{first_job.id}/inspect").status_code == 404
        assert second_client.delete(f"/web/queue/tasks/{first_task.id}").status_code == 404


def test_profile_and_settings_composition_remains_owner_scoped(
    authenticated_client: TestClient,
    authenticated_user: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical profile and settings pages compose only each account's values."""
    monkeypatch.setitem(
        sys.modules,
        "app.auth.linkedin_client",
        SimpleNamespace(LinkedInOIDCClient=lambda: SimpleNamespace(is_configured=False)),
    )
    with TestClient(app) as second_client:
        registration = second_client.post(
            "/api/auth/register",
            json={
                "email": "phase25-profile-second@example.com",
                "password": "SecondProfilePassword123",
                "full_name": "Profile Second",
            },
        )
        assert registration.status_code == 200
        second_user = registration.json()

        with Session(engine) as session:
            first_profile = session.exec(select(UserProfile).where(
                UserProfile.user_id == authenticated_user["id"]
            )).one()
            second_profile = session.exec(select(UserProfile).where(
                UserProfile.user_id == second_user["id"]
            )).one()
            first_profile.full_name = "First Profile Sentinel"
            second_profile.full_name = "Second Profile Sentinel"
            session.add_all([
                UserSetting(user_id=authenticated_user["id"], key="tailscale_hostname", value_json=json.dumps("first-settings-sentinel")),
                UserSetting(user_id=second_user["id"], key="tailscale_hostname", value_json=json.dumps("second-settings-sentinel")),
            ])
            session.commit()

        for client, own_profile, other_profile, own_setting, other_setting in (
            (authenticated_client, "First Profile Sentinel", "Second Profile Sentinel", "first-settings-sentinel", "second-settings-sentinel"),
            (second_client, "Second Profile Sentinel", "First Profile Sentinel", "second-settings-sentinel", "first-settings-sentinel"),
        ):
            assert 'hx-get="/web/views/profile"' in client.get("/profile").text
            assert 'hx-get="/web/views/settings"' in client.get("/settings").text
            profile = client.get("/web/views/profile")
            settings = client.get("/web/views/settings")
            assert own_profile in profile.text and other_profile not in profile.text
            assert own_setting in settings.text and other_setting not in settings.text