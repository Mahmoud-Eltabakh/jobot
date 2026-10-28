# Phase 12: Strict Real-Data Enforcement & Actionable Error UI

## Executive Summary
Audits the entire codebase to purge all synthetic mock data, placeholder jobs, and silent failure fallbacks from runtime code. If an external service is unavailable (e.g. Ollama offline, StepStone anti-bot block, or invalid LinkedIn credentials), Jobot raises explicit actionable diagnostic alerts in the UI instead of generating fake placeholder content.

## Architecture & Workflows
1. **Zero Runtime Synthetic Mocks**:
   - `AIScraperExtractor`, `StepStoneScraper`, and `LinkedInProfileAnalyzer` strictly operate on live network responses.
   - `JobEvaluator` requires active LLM client and raises explicit `AIProviderOfflineError` when backend is unreachable.
2. **Actionable UI Notification & Alert System**:
   - Global notification banner in `templates/base.html` rendering live system diagnostics (`Ollama Offline`, `LinkedIn Login Required`, `Scraper Rate Limited`).
   - One-click action buttons to retry, reconfigure endpoint, or test connection.
3. **Diagnostics Health & Status API**:
   - `GET /api/diagnostics/health` providing detailed live status of Ollama/OpenAI, Playwright browser, SQLite, ChromaDB, and task queue.
