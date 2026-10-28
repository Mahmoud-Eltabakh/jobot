"""Tests for Job Evaluator agent, prompt injection protection, and database update."""

import json
from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session, select

from app.ai.client import AIProviderError, MockAIClient
from app.ai.evaluator import JobEvaluator, JobFitEvaluation
from app.db.database import engine, init_db
from app.db.models import Job, JobStatus, UserProfile
from app.db.vector import VectorStore


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path) -> None:
    init_db()
    store = VectorStore(str(tmp_path / "evaluator-vectors"))
    local = MockAIClient()
    local.embed = AsyncMock(wraps=local.embed)
    monkeypatch.setattr("app.ai.evaluator.get_vector_store", lambda: store)
    monkeypatch.setattr("app.ai.evaluator.get_embedding_client", lambda *args: local)


def test_job_fit_evaluation_schema_validation() -> None:
    """Verify JobFitEvaluation bounds and field constraints."""
    eval_data = {
        "fit_score": 92,
        "fit_summary": "Excellent technical fit with strong Python/FastAPI background.",
        "pros": ["5 years Python experience", "FastAPI mastery"],
        "cons": ["No C++ experience"],
        "missing_skills": ["C++"],
        "recommendation": "Strong Match",
    }
    obj = JobFitEvaluation.model_validate(eval_data)
    assert obj.fit_score == 92
    assert obj.recommendation == "Strong Match"

    # Score out of bounds should raise ValidationError
    with pytest.raises(Exception):
        JobFitEvaluation.model_validate({**eval_data, "fit_score": 150})


@pytest.mark.asyncio
async def test_evaluate_job_with_mock_client() -> None:
    """Test JobEvaluator returns structured evaluation using MockAIClient."""
    mock_client = MockAIClient(
        default_response=json.dumps({
            "fit_score": 88,
            "fit_summary": "Great match for the senior backend position.",
            "pros": ["Python", "FastAPI", "Docker"],
            "cons": ["GraphQL not explicitly listed"],
            "missing_skills": ["GraphQL"],
            "recommendation": "Strong Match"
        })
    )

    result = await JobEvaluator.evaluate_job(
        candidate_summary="Senior Python Engineer with 6 years experience in FastAPI and Docker.",
        job_description="Looking for Senior Python Developer with FastAPI and GraphQL skills.",
        ai_client=mock_client,
    )

    assert result.fit_score == 88
    assert "FastAPI" in result.pros
    assert result.missing_skills == ["GraphQL"]
    assert result.recommendation == "Strong Match"


@pytest.mark.asyncio
async def test_evaluate_and_update_job_database() -> None:
    """Test evaluate_and_update_job updates SQLite Job record."""
    mock_client = MockAIClient(
        default_response=json.dumps({
            "fit_score": 95,
            "fit_summary": "Top tier candidate for this role.",
            "pros": ["Direct experience with Python and SQLModel"],
            "cons": [],
            "missing_skills": [],
            "recommendation": "Strong Match"
        })
    )

    with Session(engine) as session:
        # Create candidate profile
        profile = UserProfile(
            full_name="Jane Doe",
            target_titles_json='["Senior Python Engineer"]',
            skills_json='["Python", "FastAPI", "SQLModel"]',
            cv_raw_text="Jane Doe, Senior Python Engineer...",
        )
        session.add(profile)

        # Create job
        job = Job(
            source="linkedin",
            title="Senior Python Backend Developer",
            company="InnovateTech",
            location="Remote",
            url="https://linkedin.com/jobs/view/9999",
            description="Seeking senior python dev with FastAPI experience.",
            status=JobStatus.SEEN.value,
            dedup_hash="hash-eval-test-12345",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    with Session(engine) as session:
        updated_job = await JobEvaluator.evaluate_and_update_job(
            job_id=job_id,
            session=session,
            ai_client=mock_client,
        )

        assert updated_job is not None
        assert updated_job.fit_score == 95
        assert "Top tier" in updated_job.fit_summary
        assert "SQLModel" in updated_job.pros_json


@pytest.mark.asyncio
async def test_evaluate_and_delete_non_matching_job() -> None:
    """Verify that jobs with 0 matching skills are deleted from databank."""
    mock_client = MockAIClient(default_response='{"fit_score":0,"recommendation":"Not a Fit"}')

    with Session(engine) as session:
        profile = UserProfile(
            full_name="Backend Dev",
            skills_json='["Python", "FastAPI"]',
        )
        session.add(profile)

        # Job with no matching skills
        unrelated_job = Job(
            source="linkedin",
            title="Registered Nurse",
            company="HealthCare Inc",
            location="Onsite",
            url="https://example.com/nurse-job",
            description="Seeking registered nurse for hospital ward duties.",
            status=JobStatus.SEEN.value,
            dedup_hash="hash-non-match-111",
        )
        session.add(unrelated_job)
        session.commit()
        session.refresh(unrelated_job)
        job_id = unrelated_job.id

    with Session(engine) as session:
        result = await JobEvaluator.evaluate_and_update_job(
            job_id=job_id,
            session=session,
            ai_client=mock_client,
        )
        assert result is None  # Job was deleted

    # Confirm job no longer exists in SQLite databank
    with Session(engine) as session:
        db_job = session.get(Job, job_id)
        assert db_job is None


def test_purge_non_matching_jobs() -> None:
    """Test purge_non_matching_jobs removes zero fit score / unmatched skill records."""
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Python Dev",
            skills_json='["Python", "FastAPI"]',
        )
        session.add(profile)

        j_good = Job(
            source="linkedin",
            title="FastAPI Engineer",
            company="Tech Corp",
            location="Remote",
            url="https://example.com/good",
            description="Python FastAPI backend role",
            fit_score=85,
            dedup_hash="hash-good-1",
        )
        j_bad = Job(
            source="stepstone",
            title="Chef",
            company="Restaurant",
            location="Onsite",
            url="https://example.com/bad",
            description="Sous chef needed for restaurant kitchen",
            fit_score=0,
            dedup_hash="hash-bad-2",
        )
        session.add(j_good)
        session.add(j_bad)
        session.commit()

        purged_count = JobEvaluator.purge_non_matching_jobs(session)
        assert purged_count >= 1

        remaining = session.exec(select(Job)).all()
        titles = [j.title for j in remaining]
        assert "FastAPI Engineer" in titles
        assert "Chef" not in titles


def test_normalized_scoring_with_custom_weights() -> None:
    """Test normalized scoring using custom parameter weights."""
    custom_weights = {
        "skills": 50.0,
        "title": 20.0,
        "location": 20.0,
        "experience": 10.0,
        "vector": 0.0,
    }

    eval_result = JobEvaluator.compute_actual_skill_fit(
        candidate_summary="Name: Dev\nSkills: [\"Python\", \"FastAPI\"]\nTarget Titles: [\"Backend Developer\"]\nExperience: 5 years",
        job_description="Looking for Senior Backend Developer with Python and FastAPI skills.",
        candidate_skills=["Python", "FastAPI"],
        target_titles=["Backend Developer"],
        scoring_weights=custom_weights,
    )

    assert eval_result.fit_score > 0
    assert eval_result.breakdown is not None
    assert eval_result.breakdown.skills_score == 100


def test_history_education_and_project_signals_raise_fit_score() -> None:
    """Historical profile evidence should raise the score when it matches the job requirements."""
    custom_weights = {
        "skills": 35.0,
        "title": 20.0,
        "location": 10.0,
        "experience": 10.0,
        "vector": 0.0,
        "history_skills": 15.0,
        "education": 5.0,
        "projects": 5.0,
    }

    eval_result = JobEvaluator.compute_actual_skill_fit(
        candidate_summary=(
            'Name: Dev\n'
            'Skills: ["Python", "FastAPI"]\n'
            'Target Titles: ["Backend Engineer"]\n'
            'Experience History: [{"title": "Senior Python Engineer", "company": "Acme", "description": "Built FastAPI and Redis microservices in Python."}]\n'
            'Education: [{"school": "MIT", "degree": "B.S.", "field_of_study": "Computer Science"}]\n'
            'Projects: [{"name": "Inventory API", "technologies": ["FastAPI", "Redis", "PostgreSQL"]}]\n'
            'Experience: 5 years'
        ),
        job_description="Looking for Backend Engineer with Python, FastAPI, Redis, and PostgreSQL experience in a microservices platform.",
        candidate_skills=["Python", "FastAPI"],
        target_titles=["Backend Engineer"],
        scoring_weights=custom_weights,
    )

    assert eval_result.fit_score >= 75
    assert eval_result.breakdown is not None
    assert eval_result.breakdown.skills_score >= 50


@pytest.mark.asyncio
async def test_rescore_all_jobs_method() -> None:
    """Test rescore_all_jobs updates database jobs."""
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Jane Developer",
            skills_json='["Python", "FastAPI"]',
            target_titles_json='["Backend Engineer"]',
        )
        session.add(profile)

        job = Job(
            source="linkedin",
            title="Backend Engineer",
            company="Innovate",
            location="Remote",
            url="https://example.com/rescore-job",
            description="Python FastAPI backend role.",
            fit_score=50,
            dedup_hash="rescore_test_hash_123",
        )
        session.add(job)
        session.commit()

        mock_client = MockAIClient(default_response='{"fit_score":85,"recommendation":"Strong Match"}')
        count = await JobEvaluator.rescore_all_jobs(session=session, ai_client=mock_client)
        assert count >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["{}", "[]", "not-json"])
async def test_invalid_scoring_is_not_a_baseline_success(response):
    with pytest.raises(AIProviderError) as error:
        await JobEvaluator.evaluate_job("Skills: [\"Python\"]", "Python", MockAIClient(response))
    assert error.value.category == "invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["rate_limit", "quota", "unavailable"])
async def test_scoring_failure_preserves_job_and_propagates_rescore(category, monkeypatch):
    client = MockAIClient()
    failure = AIProviderError("openai", "owner-model", category, 429 if category == "rate_limit" else None)
    client.generate = AsyncMock(side_effect=failure)
    monkeypatch.setattr("app.ai.evaluator.get_embedding_client", lambda *args: MockAIClient(), raising=False)
    with Session(engine) as session:
        session.add(UserProfile(full_name="Python Dev", skills_json='["Python"]'))
        job = Job(title="Nurse", company="Test", location="Onsite", source="test", url="https://example.com", dedup_hash="must-preserve", fit_score=0, fit_summary="Original")
        session.add(job)
        session.commit()
        for operation in (
            lambda: JobEvaluator.evaluate_and_update_job(job.id, session, client),
            lambda: JobEvaluator.rescore_all_jobs(session, client),
        ):
            with pytest.raises(AIProviderError) as error:
                await operation()
            assert error.value is failure
            session.refresh(job)
            assert job.fit_score == 0 and job.fit_summary == "Original"
        assert client.generate.await_count == 2


@pytest.mark.asyncio
async def test_owned_evaluator_separates_scoring_and_local_vectors(monkeypatch, tmp_path, authenticated_user):
    owner = authenticated_user["id"]
    store = VectorStore(str(tmp_path / "vectors"))
    store.upsert_documents(VectorStore.COLLECTION_CV_PROFILE, ["profile"], ["Python"], [{"user_id": owner}], [[1.0, 0.0]])
    store.upsert_documents(VectorStore.COLLECTION_USER_FEEDBACK, ["feedback"], ["Python"], [{"user_id": owner, "sentiment":"positive"}], [[1.0, 0.0]])
    cloud, local = MockAIClient('{"fit_score":88}'), MockAIClient()
    cloud.embed = AsyncMock(return_value=[1.0, 0.0])
    local.embed = AsyncMock(return_value=[1.0, 0.0])
    calls = []

    def generation(session, user_id, *, task_type="scoring"):
        calls.append((user_id, task_type))
        return cloud

    def embeddings(session, user_id):
        calls.append((user_id, "embeddings"))
        return local

    monkeypatch.setattr("app.ai.evaluator.get_ai_client", generation, raising=False)
    monkeypatch.setattr("app.ai.evaluator.get_embedding_client", embeddings, raising=False)
    monkeypatch.setattr("app.ai.evaluator.get_vector_store", lambda: store)
    with Session(engine) as session:
        session.add(UserProfile(user_id=owner, full_name="Test", skills_json='["Python"]'))
        job = Job(user_id=owner, title="Python", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash="owned-local-score", fit_score=41)
        session.add(job)
        session.commit()
        assert await JobEvaluator.rescore_all_jobs(session, user_id=owner) == 1
        assert calls == [(owner, "scoring"), (owner, "embeddings")]
        assert local.embed.await_count == 2
        cloud.embed.assert_not_awaited()
        assert session.get(Job, job.id).fit_score == 88
        local.embed.side_effect = AIProviderError("ollama", "nomic-embed-text", "unavailable")
        with pytest.raises(AIProviderError):
            await JobEvaluator.evaluate_and_update_job(job.id, session, cloud, owner, embedding_client=local)
        assert session.get(Job, job.id).fit_score == 88
        assert store.count(VectorStore.COLLECTION_CV_PROFILE) == 1


@pytest.mark.asyncio
async def test_saved_history_weights_change_stored_fit_score() -> None:
    """History/education/project weights must move the persisted fit_score."""
    from app.db.database import set_app_setting

    llm = MockAIClient(default_response=json.dumps({"fit_score": 60, "recommendation": "Potential Match"}))
    history = json.dumps([{"title": "Engineer", "company": "Python", "description": "FastAPI Redis"}])

    with Session(engine) as session:
        session.add(UserProfile(full_name="Dev", skills_json='["Python"]'))
        session.add(Job(
            source="t", title="Engineer", company="X", location="Remote", url="https://example.com/w1",
            description="Python FastAPI Redis Engineer", dedup_hash="w-1",
        ))
        session.commit()
        job_id = session.exec(select(Job)).first().id

    async def score() -> int:
        with Session(engine) as session:
            job = await JobEvaluator.evaluate_and_update_job(job_id, session, ai_client=llm)
            return job.fit_score

    # Baseline: profile without history keeps the model score
    assert await score() == 60

    with Session(engine) as session:
        profile = session.exec(select(UserProfile)).first()
        profile.experience_history_json = history
        session.add(profile)
        session.commit()

    set_app_setting("weight_history_skills", 0)
    set_app_setting("weight_education", 0)
    set_app_setting("weight_projects", 0)
    assert await score() == 60

    set_app_setting("weight_history_skills", 10)
    low = await score()
    set_app_setting("weight_history_skills", 100)
    high = await score()
    assert 60 < low < high


def test_seniority_progression_raises_seniority_score() -> None:
    def summary(titles: list[str]) -> str:
        hist = json.dumps([{"title": t, "company": f"C{i}"} for i, t in enumerate(titles)])
        return f'Skills: ["Python"]\nExperience History: {hist}\nExperience: 2 years'

    job = "Senior Python developer"
    flat = JobEvaluator.compute_actual_skill_fit(summary(["Senior Dev", "Senior Dev"]), job)
    grown = JobEvaluator.compute_actual_skill_fit(summary(["Junior Dev", "Senior Dev"]), job)
    assert grown.breakdown.seniority_score > flat.breakdown.seniority_score
