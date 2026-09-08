---
name: jobot-docs-sync
description: "Automatically create and update the Jobot Documentation Suite (docs/USER_MANUAL.md for users, docs/CONTRIBUTING.md for developers, and README.md) whenever codebase features, UI capabilities, or execution plans are updated."
argument-hint: "[--check | --force]"
---

<purpose>
Ensure both the Jobot User Manual (`docs/USER_MANUAL.md`) and the Developer Contribution Guide (`docs/CONTRIBUTING.md`), alongside `README.md`, remain strictly in sync with the actual codebase, UI capabilities, database schemas, scraper features, AI provider configurations, and deployment steps.
</purpose>

<triggers>
Run this skill whenever:
- A new phase or plan completes execution.
- New UI features, filter rules, or settings are added.
- New scraping platforms or backend options (Ollama / Cloud APIs) are modified.
- User requests manual documentation updates.
</triggers>

<instructions>
1. **Inspect Codebase State**:
   - Check `app/` routes, UI templates, database models (`app/db/models.py`), settings (`app/core/config.py`), and scrapers.
   - Read `.planning/ROADMAP.md` and `.planning/STATE.md` to see what has shipped.

2. **Maintain Documentation Artifacts**:
   - **`docs/USER_MANUAL.md` (For End-Users)**:
     - Quickstart Guide (Local Python run, Docker Compose, Kubernetes).
     - UI Walkthrough (Kanban, Table view, Filter & Search toolbar, Job Inspector, Notes).
     - Search & Scraper Configuration (StepStone, LinkedIn, Google Jobs).
     - Blacklist & Rule Management (Title exclusions, negative keywords, company blocks).
     - AI Provider Setup (Local Ollama vs. Cloud OpenAI/Groq API keys).
     - Status Lifecycle & Feedback Loop Guide.
   - **`docs/CONTRIBUTING.md` (For Developers & Contributors)**:
     - Architecture overview & Python-first principles.
     - Docker-first development environment setup (`docker-compose.dev.yml`).
     - Local virtual environment setup & testing procedures (`pytest`, `ruff`).
     - Directory structure map.
     - Development guidelines for Database Models, AI Providers, and Scrapers.
   - **`README.md`**: High-level overview, architecture badges, features, and setup commands.

3. **Verification**:
   - Ensure all code snippets, paths, commands, and environment variable names match the actual implementation.
   - Never document unbuilt or hallucinated features without marking them as roadmap items.

4. **Git Tracking**:
   - Commit documentation changes with message: `docs: sync user manual and contributor guide with latest codebase and plan changes`.
</instructions>
