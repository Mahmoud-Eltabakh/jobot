# Security Policy

## Supported Versions

Jobot actively supports security updates for the `main` branch and latest release tags.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

We take the security and privacy of Jobot very seriously. Since Jobot handles local candidate CV data, credentials, and API keys, maintaining strict data boundaries is a core priority.

### How to Report

**Please do NOT open public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability or prompt injection risk:
1. Email the project maintainers directly or send a private advisory via GitHub.
2. Include a detailed description of the vulnerability, steps to reproduce, and potential impact.
3. Allow up to 48 hours for an initial response from maintainers.

### Security Architecture Principles
- **Privacy-First**: Jobot operates 100% locally when configured with Ollama — no candidate data, resumes, or scraped job records leave your local machine.
- **Prompt Injection Defense**: Input job descriptions are sanitized and bounded before being passed to LLMs.
- **Credential Storage**: API keys and session tokens are stored in local SQLite databases (`data/jobot.db`) and are never routed or sent to external telemetry.
