# Phase 8: AI Cover Letter Generator & Resume Tailoring Engine

## Executive Summary
Phase 8 equips Jobot with an intelligent, 1-click tailored application generation engine. Using the candidate's verified `UserProfile`, raw CV, and the specific job's extracted requirements & RAG vector match details, Jobot generates high-impact, ATS-optimized cover letters and tailored CV bullet points.

## Core Capabilities
1. **Context-Aware Cover Letter Generation**: Generates personalized cover letters addressing the specific hiring company, role requirements, candidate achievements, and matching skills.
2. **Resume Bullet Point Tailoring**: Proposes 3-5 tailored bullet points aligning the candidate's past work experience directly with the target job posting's keywords and tech stack.
3. **Application Artifacts Data Model**: Persists generated cover letters and tailored resumes in SQLite, linked to the `Job` record with versioning and editing support.
4. **Interactive UI in Job Inspector**: One-click "Generate Cover Letter" and "Tailor Resume" buttons inside the Job Inspector drawer, featuring Markdown preview, live inline editing, and 1-click clipboard copy / PDF download.
5. **Multi-Model Support**: Works seamlessly across local Ollama (`llama3.1:8b`, `qwen2.5:7b`) and Cloud OpenAI-compatible endpoints.
