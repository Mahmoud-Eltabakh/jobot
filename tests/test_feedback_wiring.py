"""Phase 5 gap closure: feedback wiring and owner-scoped suggestion endpoints."""

import shutil
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import AIProviderError, MockAIClient
from app.ai.feedback import FeedbackManager
from app.db.database import engine
from app.db.models import FilterRule, Job, JobStatus, SearchConfig, User
from app.db.vector import VectorStore


def _other_user() -> int:
    with Session(engine) as session:
        user = User(email="other-wiring@example.com", password_hash="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


@pytest.fixture
def store(monkeypatch) -> Generator[VectorStore, None, None]:
    """Private vector store plus a deterministic local embedding client."""
    temp_dir = tempfile.mkdtemp(prefix="jobot_wiring_test_")
    vector_store = VectorStore(persist_dir=temp_dir)
    monkeypatch.setattr("app.web.routes.get_vector_store", lambda: vector_store)
    monkeypatch.setattr("app.ai.feedback.get_embedding_client", lambda *a, **k: MockAIClient())
    yield vector_store
    shutil.rmtree(temp_dir, ignore_errors=True)


def _job(user_id: int, tag: str, title: str = "Onsite PHP Maintenance", status: str = JobStatus.SEEN.value) -> int:
    with Session(engine) as session:
        job = Job(user_id=user_id, source="linkedin", title=title, company="Co" + tag, location="Berlin",
                  url=f"https://jobs.test/{tag}", status=status, dedup_hash=f"wiring-{tag}")
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.id


def _docs(store: VectorStore) -> dict:
    return store.get_or_create_collection(VectorStore.COLLECTION_USER_FEEDBACK).get()


def test_status_change_records_vector_and_adjusts_score(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    job_id = _job(authenticated_user["id"], "neg")
    resp = authenticated_client.put(
        f"/api/jobs/{job_id}/status",
        data={"new_status": JobStatus.NOT_A_FIT.value, "notes": "onsite only, legacy"},
    )
    assert resp.status_code == 200
    assert "HX-Trigger-After-Settle" not in resp.headers
    stored = _docs(store)
    assert [m["sentiment"] for m in stored["metadatas"]] == ["negative"]

    import asyncio
    delta, reasons = asyncio.run(FeedbackManager.compute_feedback_score_adjustment(
        stored["documents"][0], store, embedding_client=MockAIClient()))
    assert delta < 0 and reasons


def test_feedback_adjustment_ignores_other_users_vectors(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    import asyncio
    job_id = _job(authenticated_user["id"], "scoped")
    authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.REJECTED.value})
    text = _docs(store)["documents"][0]

    def delta(user_id: int) -> int:
        return asyncio.run(FeedbackManager.compute_feedback_score_adjustment(
            text, store, embedding_client=MockAIClient(), user_id=user_id))[0]

    assert delta(authenticated_user["id"]) < 0
    assert delta(_other_user()) == 0


def test_positive_status_records_positive_vector(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    job_id = _job(authenticated_user["id"], "pos", title="FastAPI Engineer")
    authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.APPLIED.value})
    assert [m["sentiment"] for m in _docs(store)["metadatas"]] == ["positive"]


def test_neutral_move_does_not_embed(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    job_id = _job(authenticated_user["id"], "neutral")
    authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.SEEN.value})
    assert _docs(store)["ids"] == []


def test_negative_note_records_vector_without_overwriting_status_vector(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    job_id = _job(authenticated_user["id"], "note")
    authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.APPLIED.value})
    resp = authenticated_client.post(
        f"/api/jobs/{job_id}/notes", data={"note_text": "Requires German C1", "sentiment": "negative"})
    assert resp.status_code == 200
    assert sorted(m["sentiment"] for m in _docs(store)["metadatas"]) == ["negative", "positive"]


def test_other_users_job_is_not_recorded(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore,
) -> None:
    job_id = _job(_other_user(), "foreign")
    resp = authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.REJECTED.value})
    assert resp.status_code == 404
    assert _docs(store)["ids"] == []


def test_embedding_failure_is_reported_but_status_saved(
    authenticated_client: TestClient, authenticated_user: dict, store: VectorStore, monkeypatch,
) -> None:
    class Down(MockAIClient):
        async def embed(self, text):
            raise AIProviderError("ollama", "nomic-embed-text", "unavailable")

    monkeypatch.setattr("app.ai.feedback.get_embedding_client", lambda *a, **k: Down())
    job_id = _job(authenticated_user["id"], "down")
    resp = authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": JobStatus.REJECTED.value})
    assert resp.status_code == 200
    assert "not recorded" in resp.headers["HX-Trigger-After-Settle"]
    with Session(engine) as session:
        assert session.get(Job, job_id).status == JobStatus.REJECTED.value
    assert _docs(store)["ids"] == []


def test_blacklist_suggestions_are_owner_scoped_and_approvable(
    authenticated_client: TestClient, authenticated_user: dict,
) -> None:
    uid = authenticated_user["id"]
    other = _other_user()
    for i in range(2):
        _job(uid, f"mine{i}", title="PHP Maintainer", status=JobStatus.NOT_A_FIT.value)
        _job(other, f"theirs{i}", title="COBOL Wrangler", status=JobStatus.NOT_A_FIT.value)

    suggestions = authenticated_client.get("/api/suggestions").json()["blacklist_rules"]
    patterns = {s["pattern"] for s in suggestions}
    assert "PHP Maintainer" in patterns and "COBOL Wrangler" not in patterns

    assert authenticated_client.post(
        "/api/suggestions/blacklist/approve", data={"rule_type": "title", "pattern": "PHP Maintainer"}).status_code == 200
    with Session(engine) as session:
        rule = session.exec(select(FilterRule).where(FilterRule.user_id == uid)).one()
        assert rule.is_active
    # An approved pattern is no longer suggested.
    assert "PHP Maintainer" not in {
        s["pattern"] for s in authenticated_client.get("/api/suggestions").json()["blacklist_rules"]}


def test_dismiss_stores_inactive_rule_and_invalid_type_rejected(
    authenticated_client: TestClient, authenticated_user: dict,
) -> None:
    uid = authenticated_user["id"]
    authenticated_client.post("/api/suggestions/blacklist/dismiss", data={"rule_type": "keyword", "pattern": "Travel"})
    with Session(engine) as session:
        assert not session.exec(select(FilterRule).where(FilterRule.user_id == uid)).one().is_active
    bad = authenticated_client.post("/api/suggestions/blacklist/approve", data={"rule_type": "x", "pattern": "y"})
    assert bad.status_code == 422


def test_search_term_suggestions_scoped_and_approvable(
    authenticated_client: TestClient, authenticated_user: dict,
) -> None:
    uid = authenticated_user["id"]
    other = _other_user()
    for i in range(2):
        _job(uid, f"app{i}", title="FastAPI Backend Developer", status=JobStatus.APPLIED.value)
        _job(other, f"oapp{i}", title="Fortran Specialist Wizard", status=JobStatus.APPLIED.value)

    terms = authenticated_client.get("/api/suggestions").json()["search_terms"]
    assert terms and not any("Fortran" in t for t in terms)

    resp = authenticated_client.post(
        "/api/suggestions/search-terms/approve",
        data={"keywords": terms[0], "location": "Berlin", "source": "stepstone"})
    assert resp.status_code == 200
    with Session(engine) as session:
        config = session.exec(select(SearchConfig).where(SearchConfig.user_id == uid)).one()
        assert (config.keywords, config.source, config.location) == (terms[0], "stepstone", "Berlin")
    assert terms[0] not in authenticated_client.get("/api/suggestions").json()["search_terms"]


def test_suggestions_require_authentication_and_settings_embeds_panel(
    client: TestClient, authenticated_client: TestClient,
) -> None:
    assert client.get("/api/suggestions").status_code in (401, 403)
    assert "/api/suggestions/panel" in authenticated_client.get("/web/views/settings").text
    assert authenticated_client.get("/api/suggestions/panel").status_code == 200


def test_backfill_assigns_legacy_feedback_vectors_to_job_owner(
    authenticated_user: dict, store: VectorStore,
) -> None:
    uid = authenticated_user["id"]
    owned = _job(uid, "legacy-owned")
    collection = store.get_or_create_collection(VectorStore.COLLECTION_USER_FEEDBACK)
    emb = [0.1, 0.2, 0.3]
    collection.add(
        ids=["legacy_owned", "legacy_orphan", "modern"],
        documents=["a", "b", "c"],
        embeddings=[emb, emb, emb],
        metadatas=[
            {"job_id": owned, "sentiment": "negative"},
            {"job_id": 987654, "sentiment": "negative"},
            {"job_id": owned, "user_id": 999, "sentiment": "positive"},
        ],
    )
    with Session(engine) as session:
        assert FeedbackManager.backfill_feedback_owners(session, store) == {"updated": 1, "skipped": 1}
        assert FeedbackManager.backfill_feedback_owners(session, store) == {"updated": 0, "skipped": 1}

    metas = dict(zip(*[_docs(store)[k] for k in ("ids", "metadatas")]))
    assert metas["legacy_owned"]["user_id"] == uid
    assert "user_id" not in metas["legacy_orphan"]
    assert metas["modern"]["user_id"] == 999  # existing owner never overwritten
