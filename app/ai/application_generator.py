"""AI Application Generator: Tailored Cover Letters & Resume Bullet Points."""

import json
import logging
from typing import Any, Optional
from sqlmodel import Session, select

from app.ai.client import BaseAIClient, get_ai_client
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

    @classmethod
    async def generate_cover_letter(
        cls,
        job: Job,
        user_profile: UserProfile,
        tone: str = "professional",
        custom_instructions: Optional[str] = None,
        ai_client: Optional[BaseAIClient] = None,
    ) -> str:
        """Generate a tailored cover letter for a specific job posting."""
        system_prompt = COVER_LETTER_SYSTEM_PROMPTS.get(tone, COVER_LETTER_SYSTEM_PROMPTS["professional"])
        client = ai_client or get_ai_client()

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
            return content.strip()
        except Exception as err:
            logger.warning("Cover letter generation failed (%s), returning template fallback", err)
            return cls._fallback_cover_letter(job, user_profile, tone)

    @classmethod
    async def generate_tailored_resume_points(
        cls,
        job: Job,
        user_profile: UserProfile,
        ai_client: Optional[BaseAIClient] = None,
    ) -> str:
        """Generate ATS-optimized accomplishment bullet points aligned with the target job."""
        client = ai_client or get_ai_client()
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
            return content.strip()
        except Exception as err:
            logger.warning("Resume tailoring generation failed (%s), returning fallback", err)
            return cls._fallback_resume_points(job, user_profile)

    @classmethod
    def save_material(
        cls,
        session: Session,
        job_id: int,
        material_type: str,
        content_markdown: str,
        tone: str = "professional",
    ) -> ApplicationMaterial:
        """Persist or update application material in database."""
        existing = session.exec(
            select(ApplicationMaterial).where(
                ApplicationMaterial.job_id == job_id,
                ApplicationMaterial.material_type == material_type,
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

    @classmethod
    def _fallback_cover_letter(cls, job: Job, user_profile: UserProfile, tone: str) -> str:
        """Fallback cover letter template when AI provider is offline."""
        skills = json.loads(user_profile.skills_json or "[]")
        top_skills = ", ".join(skills[:4]) if skills else "modern software engineering practices"

        return f"""# Application for {job.title}

Dear Hiring Team at {job.company},

I am writing to express my enthusiastic interest in the **{job.title}** position. With over {user_profile.experience_years} years of professional experience and core competencies in **{top_skills}**, I am confident in my ability to immediately contribute to {job.company}'s engineering objectives.

In my recent projects, I have specialized in architecting reliable, scalable solutions while collaborating with cross-functional teams. Reviewing the job requirements for this role, my background directly aligns with your need for strong technical delivery and problem-solving.

I would welcome the opportunity to discuss how my skill set and enthusiasm can support {job.company}'s ongoing success. Thank you for your time and consideration.

Sincerely,  
**{user_profile.full_name}**  
{user_profile.headline or ''}
"""

    @classmethod
    def _fallback_resume_points(cls, job: Job, user_profile: UserProfile) -> str:
        """Fallback tailored resume bullet points."""
        skills = json.loads(user_profile.skills_json or "[]")
        skill_1 = skills[0] if len(skills) > 0 else "Python"
        skill_2 = skills[1] if len(skills) > 1 else "FastAPI"

        return f"""### Tailored Resume Bullets for {job.title} at {job.company}

- **Architected and Deployed Scalable Services**: Designed end-to-end backend microservices utilizing **{skill_1}** and **{skill_2}**, improving application throughput and reliability by 35%.
- **Automated Data Pipelines & Scraping Workflows**: Engineered automated data ingestion pipelines ensuring sub-second retrieval times and high availability.
- **Cross-Functional Collaboration**: Partnered with product and infrastructure engineers to streamline delivery pipelines using **Docker** and modern CI/CD practices.

### ATS Keyword Alignment
| Keyword / Skill | Status in Profile | Match Level |
| :--- | :--- | :--- |
| {skill_1} | Verified in Profile | Strong Match |
| {skill_2} | Verified in Profile | Strong Match |
| System Architecture | Active Competency | High |
"""
