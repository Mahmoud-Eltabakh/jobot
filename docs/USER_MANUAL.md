# Jobot — User Manual & Operations Guide

Welcome to **Jobot**, your intelligent, privacy-first, automated job search and application tracking copilot.

---

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Quickstart & Installation](#2-quickstart--installation)
   - [First-Run Account Setup](#first-run-account-setup)
   - [Encryption Key Setup](#encryption-key-setup)
3. [Dashboard & Interface Guide](#3-dashboard--interface-guide)
   - [Kanban Board View](#kanban-board-view)
   - [Data Table View](#data-table-view)
   - [Active AI Queue Jobs & Control Center](#active-ai-queue-jobs--control-center)
   - [Multi-Criteria Sorting & Filtering](#multi-criteria-sorting--filtering)
   - [Job Inspector Drawer](#job-inspector-drawer)
4. [AI Cover Letter Generator & Resume Tailoring](#4-ai-cover-letter-generator--resume-tailoring)
   - [Custom Tone Cover Letters](#custom-tone-cover-letters)
   - [ATS-Optimized Resume Accomplishment Bullets](#ats-optimized-resume-accomplishment-bullets)
   - [1-Click Clipboard & Persistence](#1-click-clipboard--persistence)
5. [Profile Management & LinkedIn AI Ingestion](#5-profile-management--linkedin-ai-ingestion)
   - [Profile Editing & Skills Matrix](#profile-editing--skills-matrix)
   - [AI Executive Bio Generator](#ai-executive-bio-generator)
   - [LinkedIn Profile AI Ingestion & Sync](#linkedin-profile-ai-ingestion--sync)
   - [Dynamic Skill-Driven Search Matrix](#dynamic-skill-driven-search-matrix)
6. [AI Provider Setup & Hardware Acceleration](#6-ai-provider-setup--hardware-acceleration)
   - [Local Ollama (Default & Privacy-First)](#local-ollama-default--privacy-first)
   - [GPU & NPU Acceleration](#gpu--npu-hardware-acceleration)
   - [Cloud API Providers (OpenAI / Groq)](#cloud-api-providers-openai--groq)
7. [Normalized Scoring & UI Parameter Calibration](#7-normalized-scoring--ui-parameter-calibration)
   - [Normalized Sub-Factors](#normalized-sub-factors)
   - [Fine-Tuning Scales in Settings](#fine-tuning-scales-in-settings)
8. [Scrapers & Background Task Queue](#8-scrapers--background-task-queue)
9. [Title, Company & Keyword Blacklists](#9-title-company--keyword-blacklists)
10. [Adaptive Feedback Loop](#10-adaptive-feedback-loop)
11. [Docker & Kubernetes Deployment](#11-docker--kubernetes-deployment)

---

## 1. System Architecture
Jobot is built on a pure Python modern web stack:
- **Web UI & API**: FastAPI + Jinja2 + HTMX + Tailwind CSS (Zero Node.js/npm dependencies).
- **Scraping Engine**: `python-jobspy` (LinkedIn & Google Jobs) + Playwright (StepStone) with dynamic profile skill query synthesis.
- **AI Matching & RAG**: Local Ollama (`llama3.1`, `mistral`, `qwen2.5`, `job-searcher-qwen3`) OR Cloud AI APIs (OpenAI, Groq, Anthropic) + embedded ChromaDB vector store.
- **Application Generator**: Context-aware cover letter synthesizer and ATS-tailored resume generator.
- **Relational Database**: SQLite with SQLModel / SQLAlchemy (WAL mode enabled).
- **Task Queue**: SQLite-backed `ScrapeTask` queue with continuous `QueueWorker` background daemon.

---

## 2. Quickstart & Installation

### Local Python Setup
```bash
# 1. Clone repository and navigate to workspace
git clone https://github.com/Mahmoud-Eltabakh/jobot.git
cd Jobot

# 2. Create virtual environment
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies & Playwright browsers
pip install -r requirements.txt
playwright install chromium

# 4. Copy environment variables
cp .env.example .env

# 5. Start the web server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

### First-Run Account Setup

When the database has no registered users, Jobot opens the registration page. Create the first account with an email address, display name, and password of at least six characters. Returning users without an active session are redirected to login.

Sessions are stored as revocable opaque tokens in an HTTP-only cookie. Use **Logout** in the top navigation to revoke the current session. Jobs, profiles, notes, filters, application materials, queue tasks, AI settings, scoring weights, and Tailscale preferences are isolated by account.

### Encryption Key Setup

Sensitive profile fields, CV/LinkedIn content, LinkedIn credentials, and provider API keys are encrypted with an account-bound key derived from Jobot's master encryption key.

- In development, Jobot creates `data/.jobot-encryption-key` with owner-only permissions when `ENCRYPTION_KEY` is absent. Back up this file with the database; losing it makes encrypted fields unrecoverable.
- In production, set `ENCRYPTION_KEY` through the deployment secret manager. Jobot refuses to encrypt data without it.
- Set `ENCRYPTION_KEY_ID` to identify the active key.
- During rotation, move the old key to `PREVIOUS_ENCRYPTION_KEYS` using `old-id:old-key`, configure a new key and ID, start Jobot to migrate accessible records, verify them, and only then retire the previous key.

Never commit encryption keys, session cookies, or provider credentials to source control. A database backup without its matching encryption key is intentionally insufficient to recover protected data.

---

## 3. Secure Phone Access via SSH Tunnel

If you want to use Jobot on a phone or tablet while keeping the main workstation as the application brain, use SSH tunneling instead of exposing the app to the public internet.

### Why this pattern matters

- Jobot, Ollama, SQLite, ChromaDB, and the scraper workers stay on the host machine.
- Your phone functions as a thin client, not a second runtime.
- The connection is encrypted and authenticated via SSH.
- No direct public port is required for the app.

### Step-by-step

1. Make sure the host machine is running Jobot locally. The app should be bound to the local loopback interface or a private network address only.
2. Generate and install an SSH key for the host if you have not done so already.
3. Connect to the host with a tunnel that forwards the Jobot port:

```powershell
# Windows PowerShell
ssh -N -L 8000:127.0.0.1:8000 your-user@your-host
```

```bash
# Linux / macOS
ssh -N -L 8000:127.0.0.1:8000 your-user@your-host
```

4. Confirm the forwarded endpoint is reachable from the device you are using.
5. Open the Jobot UI through the forwarded address in the browser.
6. When finished, close the SSH tunnel and verify the process is no longer exposed to the wider network.

### Security rules

- Prefer key-based SSH authentication and disable password-only logins.
- Restrict forwarding to the exact Jobot port only.
- Do not open a public port on the router or firewall.
- Keep the database, AI stack, and scrapers local to the host.
- Treat mobile access as convenience access, not as a distributed deployment.

### Troubleshooting

- If the browser says connection refused, confirm that Jobot is actually running locally on the host and the port is correct.
- If SSH says permission denied, check the private key and authorized_keys setup.
- If the port is already in use, choose a different local forwarding port and update the browser target.
- If the tunnel is unstable, check for host firewall or network restrictions and prefer a private network path over public exposure.

### Tailscale SSH Settings panel

Open **Settings → Tailscale SSH Remote Access** to manage the connection profile:

- **Enable remote access profile** controls whether the saved profile is considered active.
- **Use MagicDNS** indicates that the Tailscale device hostname should be preferred over an IP address.
- **Tailscale hostname or IP** identifies the workstation running Jobot.
- **SSH user** is the operating-system account accepted by Tailscale SSH.
- **SSH port** defaults to `22`; change it only when your host SSH service uses a different port.
- **Jobot port** is the local application port to forward, normally `8000`.

The status badge is loaded separately so an unavailable Tailscale daemon does not delay the rest of Settings. It reports **Connected**, **Offline**, or **Not installed**. After saving a hostname and SSH user, reopen Settings to see the generated forwarding command.

Jobot intentionally does not run `tailscale up`, `tailscale down`, or SSH commands. Install Tailscale, authenticate the host, enable Tailscale SSH according to your tailnet policy, and run the displayed forwarding command from the remote device.

---

## 4. Dashboard & Interface Guide

### Kanban Board View
Organizes opportunities across 8 distinct lifecycle stages:
1. `seen` — Newly scraped & AI-evaluated jobs.
2. `applied` — Application submitted.
3. `waiting for respond` — Awaiting employer reply.
4. `1. interview` — First round / recruiter screening.
5. `2. interview` — Technical assessment / hiring manager interview.
6. `3. interview` — Final round / executive interview.
7. `not a good fit` — Disqualified based on candidate review.
8. `rejected` — Formal rejection by company.

### Data Table View
Sortable tabular view displaying job matches, company details, match scores, locations, and source platforms.

### Active AI Queue Jobs & Control Center
Navigate to the **AI Queue** tab in the top navigation bar for full real-time task queue management and background execution controls:
- **Live Real-Time Auto-Refresh**: Uses HTMX polling (`3s`) to display background job progress live.
- **KPI Metrics Cards**: Real-time counts of `Pending`, `In Progress`, `Completed`, `Failed`, and `Total Tasks`.
- **Worker Controls**:
  - **Pause / Resume Worker**: Pause or resume background task worker execution.
  - **Enqueue Full Discovery**: Manually trigger AI search strategy formulation and query execution.
  - **Retry Failed Tasks**: Reset all failed jobs back to `pending` status.
  - **Clear Completed / Queue**: Delete finished or stale queue tasks from SQLite.
- **Per-Task Row Actions**: Retry or delete individual tasks (`#ID`), view full payload details, retry attempts, and detailed error messages.

### Multi-Criteria Sorting & Filtering
Use the top toolbar to filter by:
- **Fit Score**: Dynamic slider ($\ge 70\%$, $\ge 80\%$, $\ge 90\%$).
- **Work Model**: `Remote Only`, `Hybrid`, or `On-site`.
- **Compensation**: Minimum salary threshold.
- **Source**: Checkboxes for `LinkedIn`, `StepStone`, `Google Jobs`.
- **Exclusions**: Quick toggles to *"Hide Rejected"* or *"Hide Not a Good Fit"*.

### Job Inspector Drawer
Click any job card to open the slide-over inspector featuring 4 dedicated tabs:
1. **Overview & Match**: 0–100% Fit Score, Key Strengths, Skill Gaps, and Full Job Description.
2. **AI Cover Letter**: 1-click tailored cover letter generator with customizable tones.
3. **Tailored Resume**: ATS-optimized accomplishment bullet points formulated for the role.
4. **Notes & Timeline**: Candidate interview impressions, recruiter comments, and status history.

---

## 5. AI Cover Letter Generator & Resume Tailoring

### Custom Tone Cover Letters
Inside the Job Inspector drawer, switch to the **AI Cover Letter** tab:
- Choose from 4 distinct professional tones:
  - **Professional**: Executive, polished tone emphasizing quantifiable contributions.
  - **Direct & Impactful**: Punchy 3-paragraph format highlighting matching tech stack.
  - **Enthusiastic**: Engaging and passionate about the company mission.
  - **Conversational**: Authentic, collaborative software engineering voice.
- Click **"Generate Cover Letter"** to generate a bespoke letter using your `UserProfile` and the target job description.

### ATS-Optimized Resume Accomplishment Bullets
Switch to the **Tailored Resume** tab:
- Click **"Tailor Resume Accomplishments"**.
- Jobot generates 4–6 impact-focused bullet points using the *Action Verb + Tech Stack + Quantified Impact* framework, along with an ATS keyword alignment matrix.

### 1-Click Clipboard & Persistence
- Edit generated materials directly in the browser.
- Click **"Copy to Clipboard"** for immediate pasting into application portals.
- Click **"Save Changes"** to persist your custom edits to SQLite.

---

## 6. Profile Management & LinkedIn AI Ingestion

### Profile Editing & Skills Matrix
Navigate to the **Profile** tab in the top navigation bar:
- **Personal & Work Preferences**: Edit your full name, headline, bio, experience years, minimum salary, and preferred work model (Remote First, Hybrid, On-site).
- **Target Roles & Locations**: Configure target titles (e.g., `Python Developer, Backend Architect`) and target locations.
- **Skills Tag Manager**: Modify and add technical and domain competencies.

### AI Executive Bio Generator
- Click **"Generate Bio with AI"** next to the Professional Bio field.
- Jobot automatically generates a 2-3 sentence executive summary based on your profile skills, experience, and target roles.

### LinkedIn Profile AI Ingestion & Sync
- Enter your public or authenticated **LinkedIn Profile URL** (`https://www.linkedin.com/in/username`).
- *(Optional)* Provide your `li_at` session cookie to fetch complete private sections (experience items, full skills).
- Click **"Sync Profile with li_at Cookie"**: Jobot extracts your experience and skills with AI, updates your SQLite profile, and re-computes semantic RAG vectors in ChromaDB.

### Dynamic Skill-Driven Search Matrix
- Under **Active Scraper Search Skills**, select or toggle the skills you want Jobot to target.
- When scrapers run (via the "Scrape Now" button or background schedule), Jobot dynamically generates multi-query search batches pairing your target roles with your active skills (e.g., `Python Developer FastAPI`, `Backend Engineer Docker`) across LinkedIn, StepStone, and Google Jobs.

---

## 7. AI Provider Setup & Hardware Acceleration

### Local Ollama (Default & Privacy-First)
In the **Settings** panel, choose your AI backend:
- Runs 100% locally with zero external API calls.
- Requires Ollama installed (`http://localhost:11434`).
- Recommended models: `llama3.1:8b`, `qwen2.5:7b`, or fine-tuned `job-searcher-qwen3` + `nomic-embed-text`.

### GPU & NPU Hardware Acceleration
- **NVIDIA CUDA**: Auto-detected by host Ollama or mounted via Docker Compose `deploy.resources.reservations.devices`.
- **AMD ROCm / DirectML**: Supported natively on Windows/Linux for Radeon RX series.
- **Intel Arc / NPUs (Intel Core Ultra, AMD Ryzen AI, Qualcomm Snapdragon X)**: Accelerated via DirectML / Vulkan / ONNX runtime.
- **Key Optimization Environment Variables**:
  - `OLLAMA_NUM_GPU=999`: Offloads all model layers to VRAM.
  - `OLLAMA_FLASH_ATTENTION=1`: Enables Flash Attention to reduce VRAM usage.
  - `OLLAMA_KEEP_ALIVE=24h`: Keeps model cached in GPU VRAM.

### Cloud API Providers (OpenAI / Groq)
- Select OpenAI, Groq, Anthropic, or custom OpenAI-compatible endpoints.
- Enter your API Key and click **Test Connection**.

---

## 8. Normalized Scoring & UI Parameter Calibration

### Normalized Sub-Factors
Jobot computes candidate-to-job fit scores by normalizing parameters into 0–100% ratios:
1. **Profile Skills Match Ratio (0–100%)**: Number of matched job skills divided by candidate profile skills. (0% overlap = instant disqualification).
2. **Target Title & Seniority Ratio (0–100%)**: Match between candidate target roles and requested seniority years.
3. **Workplace & Location Ratio (0–100%)**: Match for remote preferences and target locations.
4. **Experience Relevance Ratio (0–100%)**: Candidate experience years relative to benchmark requirements.
5. **Vector RAG Similarity Ratio (0–100%)**: ChromaDB dense embedding cosine similarity.

### Fine-Tuning Scales in Settings
Navigate to the **Settings** tab &rarr; **Scoring Engine Calibration & Fine-Tuning Scales**:
- Use interactive sliders (0–100) to adjust the relative weight of each scoring parameter.
- Click **"Save Scoring Scales"** to persist your custom weights.
- Click **"Rescore All Stored Jobs"** to instantly recalculate fit scores across your entire job database using your calibrated scales!

---

## 9. Scrapers & Background Task Queue
- **Automated Runs**: Scrapers automatically run on a periodic schedule (e.g., every 6, 12, or 24 hours).
- **Manual Trigger**: Click **"Scrape Now"** on the dashboard to immediately fetch the latest postings.
- **Deduplication**: Automatic SHA-256 deduplication prevents duplicate job cards.

---

## 10. Title, Company & Keyword Blacklists
Conserve compute and hide unwanted roles before AI scoring:
- **Title Blacklist**: Exclude terms like `"Director"`, `"Lead"`, `"Intern"`, `"Staff"`.
- **Company Blacklist**: Exclude specific employers.
- **Negative Keywords**: Exclude descriptions containing terms like `"C1 German"`, `"No Visa Sponsorship"`, `"50% Travel"`.

---

## 11. Adaptive Feedback Loop
- Tagging jobs as `not a good fit` or adding critical notes updates the vector database and suggests new blacklist keywords.
- Advancing jobs to `applied` or `interview` stages strengthens positive semantic embeddings for future scoring.

---

## 12. Docker & Kubernetes Deployment

### Docker Compose
Jobot provides two Docker launch modes:
1. **Mode 1: Host Ollama (Recommended if you already have Ollama installed on Windows/Mac/Linux)**
   - Connects Jobot container to your host machine's Ollama instance (`http://host.docker.internal:11434`).
   - Uses your native host GPU acceleration directly with zero extra container download.
   ```powershell
   # Windows PowerShell
   .\scripts\manage.ps1 docker-up-host-ollama
   # or: .\scripts\run-docker.ps1 host-ollama
   ```
   ```bash
   # Linux / macOS
   ./scripts/manage.sh docker-up-host-ollama
   # or: ./scripts/run-docker.sh --host-ollama
   ```

2. **Mode 2: Full Docker Stack (Jobot + Ollama container in Docker)**
   - Builds `jobot:latest` and pulls the `ollama/ollama:latest` container.
   ```powershell
   # Windows PowerShell
   .\scripts\manage.ps1 docker-up
   # or: .\scripts\run-docker.ps1 prod
   ```
   ```bash
   # Linux / macOS
   ./scripts/manage.sh docker-up
   # or: ./scripts/run-docker.sh prod
   ```

### Kubernetes
```bash
# Linux / macOS
./scripts/deploy-k8s.sh

# Windows PowerShell
.\scripts\deploy-k8s.ps1
```

---
*Last updated: 2026-09-08 — Maintained automatically via `/jobot-docs-sync`.*
