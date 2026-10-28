# Phase 7: Profile Management, LinkedIn Profile Analysis & Skill-Driven Scraping

## Executive Summary
This phase introduces full Candidate Profile Management, interactive LinkedIn Profile analysis & ingestion, and dynamic skill-aware scraper query generation. This enables Jobot to search for jobs specifically aligned with the user's active skills and target titles, while providing a dedicated web tab to edit and fine-tune candidate preferences and sync embeddings in real time.

## Architectural Objectives
1. **Enhanced UserProfile Model**: Expand SQLite model with headline, bio, experience history, work preferences, and active search skill tags.
2. **Real-Time Vector Synchronization**: Any edit to the candidate profile immediately triggers ChromaDB chunking and re-embedding via `ProfileEmbedder`.
3. **LinkedIn Profile Ingestion & AI Analyzer**: Support LinkedIn profile analysis via URL, Playwright session cookies, or raw text extraction, extracting structured skills, headline, and career history using LLM.
4. **Skill-Driven Scraping Query Matrix**: Dynamic generation of search queries combining primary target titles with active profile skills across LinkedIn, StepStone, and Google Jobs.
5. **Modern Profile Editing UI**: A dedicated `/profile` dashboard view featuring an interactive tag manager, skill toggles for scrapers, LinkedIn synchronization controls, and instant saving via HTMX.
