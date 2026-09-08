# Phase 9: AI-Assisted Intelligent Web Scraping Engine

## Executive Summary
Traditional web scrapers rely on brittle CSS selectors and static search strings. Job sites frequently update their DOM hierarchies, load dynamic content, or obfuscate details like salaries and remote status.
Phase 9 introduces an **AI-Assisted Scraping Engine** where:
1. **AI Query Strategist**: Formulates Boolean and semantic search terms optimized per platform (LinkedIn, StepStone, Google Jobs) based on the candidate's skills and market response.
2. **AI DOM/Text Extractor (`AIScraperExtractor`)**: Extracts clean, normalized structured job data (`title`, `company`, `location`, `salary_min`, `salary_max`, `is_remote`, `required_skills`, `visa_sponsorship`, `language_requirement`) directly from arbitrary rendered HTML or markdown without requiring hardcoded CSS selectors.
3. **Hybrid Extraction Pipeline**: Combines high-speed heuristic scraping with zero-shot AI fallback parsing when DOM structures change or when job descriptions are unstructured.
4. **AI Job Legitimacy Filter**: Detects spam, duplicate agency reposts, and promotional ads before database insertion.
