"""Generate owned application text without synthetic outage replacements.

Cover letters and resume bullets use the independent applying assignment.
The job/profile owner is resolved before any provider request is made.
Contradictory owned records are rejected even with explicit client injection.
Legacy positional tone, instructions and generation-client arguments remain.
Existing prompts, candidate/job truncation and plain-text mode are preserved.
An injected client remains responsible for selected generation transport only.
Empty output is an explicit invalid response, not material ready to save.
Typed provider errors preserve safe provider/model/status metadata for callers.
Unexpected generation failures are sanitized without raw payload logging.
No template cover letter, fabricated achievement or alternate model is used.
Generation returns in-memory content; persistence is a separate owner action.
REST callers save only after a complete successful generation response.
Human review of facts and tone remains necessary before using generated text.
"""

import json
import logging

from sqlmodel import Session, select

from app.ai.client import AIProviderError, BaseAIClient, _provider_error, _validated_content, get_ai_client
from app.db.models import ApplicationMaterial, Job, UserProfile, utc_now

logger = logging.getLogger("jobot.ai.application_generator")

COVER_LETTER_SYSTEM_PROMPTS = {
    "professional": (
        "You are an executive career coach and elite resume/cover letter specialist. "
        "Write a polished, highly professional cover letter tailored specifically to the company and role. "
        "Highlight the candidate's strongest matching competencies, quantify achievements where appropriate, "
        "and bridge any skill gaps with relevant transferable experience. Format cleanly in Markdown."
    ),
    "enthusiastic": (
        "You are a modern tech recruiter and high-impact application strategist. "
        "Write an engaging, vibrant, and compelling cover letter demonstrating genuine passion for the company's domain "
        "and mission. Emphasize candidate strengths and enthusiasm for collaboration. Format cleanly in Markdown."
    ),
    "direct": (
        "You are a concise, high-impact hiring advisor. "
        "Write a direct, punchy, 3-paragraph cover letter that gets straight to the point: "
        "1) The role and why the candidate is a strong fit, 2) 3 key achievements matching the tech stack, "
        "3) A direct call to action for an interview. Format cleanly in Markdown."
    ),
    "conversational": (
        "You are a friendly, articulate software engineer writing a cover letter. "
        "Adopt a warm, authentic, conversational tone while clearly showcasing deep technical problem-solving ability. "
        "Format cleanly in Markdown."
    ),
}

RESUME_TAILORING_SYSTEM_PROMPT = """You are an ATS optimization expert and technical resume consultant.
Given the target job description and the candidate's current background and skill set:
1. Provide 4-6 high-impact, tailored accomplishment bullet points that the candidate can copy directly onto their resume.
2. Formulate each bullet using the 'Action Verb + Context/Tech Stack + Quantified Impact/Result' framework.
3. Strategically include relevant keywords from the job description while staying authentic to the candidate's profile.
4. Conclude with a brief 'ATS Keyword Alignment' summary table.
Format the output cleanly in Markdown.
"""


class ApplicationGenerator:
    """Generates tailored cover letters and resume points using AI LLM."""

    @staticmethod
    def _generation_owner(job: Job, user_profile: UserProfile) -> int | None:
        """Reject contradictory owners even when a client is explicitly injected.

        Unsaved profiles may lack an owner; in that case the owned job is
        authoritative. Legacy unowned records retain installation behavior,
        but owned generation never borrows the installation's credentials.
        """
        if job.user_id is not None and user_profile.user_id is not None and job.user_id != user_profile.user_id:
            raise AIProviderError("ollama", "", "configuration")
        return job.user_id if job.user_id is not None else user_profile.user_id

    @classmethod
    async def generate_cover_letter(
        cls,
        job: Job,
        user_profile: UserProfile,
        tone: str = "professional",
        custom_instructions: str | None = None,
        ai_client: BaseAIClient | None = None,
    ) -> str:
        """Generate real content using the owner's applying configuration.

        Tone selects the established system prompt, not the provider/model.
        Custom instructions remain in the user prompt with candidate details.
        An owned job is authoritative when an unsaved profile lacks an owner.
        Error propagation is deliberate: callers must not save a template or
        report success after quota, outage, invalid or empty provider output.
        This method itself performs no persistent material or profile writes.
        """
        system_prompt = COVER_LETTER_SYSTEM_PROMPTS.get(tone, COVER_LETTER_SYSTEM_PROMPTS["professional"])
        owner = cls._generation_owner(job, user_profile)
        client = ai_client or get_ai_client(user_id=owner, task_type="applying")

        skills = json.loads(user_profile.skills_json or "[]")
        target_titles = json.loads(user_profile.target_titles_json or "[]")

        prompt = f"""Target Company: {job.company}
Target Role: {job.title}
Location: {job.location} ({'Remote' if job.is_remote else 'On-site/Hybrid'})

Job Description Details:
{job.description[:4000]}

Candidate Information:
Name: {user_profile.full_name}
Headline: {user_profile.headline or (target_titles[0] if target_titles else 'Software Professional')}
Experience: {user_profile.experience_years} years
Core Skills: {', '.join(skills[:12])}
Summary/Bio: {user_profile.bio or 'Experienced professional.'}
Candidate CV Details:
{user_profile.cv_raw_text[:3000] if user_profile.cv_raw_text else 'N/A'}

AI Fit Analysis:
Pros: {job.pros_json or '[]'}
Missing/Gaps: {job.missing_skills_json or '[]'}

Additional User Instructions:
{custom_instructions if custom_instructions else 'None'}

Please generate a compelling, tailored cover letter. Do not include placeholder tokens like [Your Name] — use the provided candidate details directly.
"""

        try:
            content = await client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=False,
            )
            return _validated_content(getattr(client, "provider", "ollama"), getattr(client, "model", ""), content, False).strip()
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error(getattr(client, "provider", "ollama"), getattr(client, "model", ""), err) from None

    @classmethod
    async def generate_tailored_resume_points(
        cls,
        job: Job,
        user_profile: UserProfile,
        ai_client: BaseAIClient | None = None,
    ) -> str:
        """Generate ATS bullets through the same owned applying boundary.

        Preserve the existing resume prompt and plain-text Markdown contract.
        No fallback invents achievements when the selected service fails.
        Persistence remains separate and can occur only after this returns.
        """
        owner = cls._generation_owner(job, user_profile)
        client = ai_client or get_ai_client(user_id=owner, task_type="applying")
        skills = json.loads(user_profile.skills_json or "[]")

        prompt = f"""Target Position: {job.title} at {job.company}
Job Description:
{job.description[:4000]}

Candidate Profile:
Name: {user_profile.full_name}
Headline: {user_profile.headline}
Skills: {', '.join(skills)}
Bio & Experience: {user_profile.bio}
CV Raw Background:
{user_profile.cv_raw_text[:3000] if user_profile.cv_raw_text else 'N/A'}

Generate tailored resume accomplishment bullet points and ATS keyword alignment.
"""

        try:
            content = await client.generate(
                prompt=prompt,
                system_prompt=RESUME_TAILORING_SYSTEM_PROMPT,
                json_mode=False,
            )
            return _validated_content(getattr(client, "provider", "ollama"), getattr(client, "model", ""), content, False).strip()
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error(getattr(client, "provider", "ollama"), getattr(client, "model", ""), err) from None

    @classmethod
    def save_material(
        cls,
        session: Session,
        job_id: int,
        material_type: str,
        content_markdown: str,
        user_id: int,
        tone: str = "professional",
    ) -> ApplicationMaterial:
        """Persist material inside the supplied authenticated ownership boundary.

        Existing materials are matched by owner, job and material type.
        Generation callers must reach this method only after successful output;
        provider failures leave both old content and timestamps unchanged.
        """
        existing = session.exec(
            select(ApplicationMaterial).where(
                ApplicationMaterial.job_id == job_id,
                ApplicationMaterial.material_type == material_type,
                ApplicationMaterial.user_id == user_id,
            )
        ).first()

        if existing:
            existing.content_markdown = content_markdown
            existing.tone = tone
            existing.updated_at = utc_now()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        material = ApplicationMaterial(
            user_id=user_id,
            job_id=job_id,
            material_type=material_type,
            tone=tone,
            content_markdown=content_markdown,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(material)
        session.commit()
        session.refresh(material)
        return material
