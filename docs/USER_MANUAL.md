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
   - [Provider Vault and Task Assignments](#provider-vault-and-task-assignments)
   - [Manual Recovery and Local Vectors](#manual-recovery-and-local-vectors)
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
- **Log in once:** on the Profile tab, enter your LinkedIn email and password and press **Log in to LinkedIn**. Jobot signs in through a headless browser and stores only the encrypted `li_at` session cookie for your account; the email and password are not saved. Accounts that require a verification (2FA) challenge may fail to log in headlessly; use the cookie paste option below in that case.
- **Session status:** the badge next to the heading shows `Needs login`, `Session stored (not verified)`, `Logged In (Active)` or `Expired - log in again`. **Verify session** checks the stored cookie against LinkedIn on demand; the badge is never refreshed automatically, and a successful check does not guarantee later scrapes will not be rate limited or challenged.
- Enter your public or authenticated **LinkedIn Profile URL** (`https://www.linkedin.com/in/username`).
- *(Optional)* Provide your `li_at` session cookie instead of logging in, to fetch complete private sections (experience items, full skills).
- Click **"Sync Profile with li_at Cookie"**: Jobot extracts your experience and skills with AI, updates your SQLite profile, and re-computes semantic RAG vectors in ChromaDB.
- Automated login may conflict with LinkedIn's terms of use and may trigger account checks; it has been tested offline with mocks only, not against live LinkedIn.

### Dynamic Skill-Driven Search Matrix
- Under **Active Scraper Search Skills**, select or toggle the skills you want Jobot to target.
- When scrapers run (via the "Scrape Now" button or background schedule), Jobot dynamically generates multi-query search batches pairing your target roles with your active skills (e.g., `Python Developer FastAPI`, `Backend Engineer Docker`) across LinkedIn, StepStone, and Google Jobs.

---

## 7. AI Provider Setup & Hardware Acceleration

### Local Ollama (Default & Privacy-First)
In **Settings > AI Providers**, set the Ollama endpoint to the host reachable from Jobot. `http://localhost:11434` is the default; containers may need `http://host.docker.internal:11434` or the Ollama service hostname instead. An optional saved bearer token belongs only to that account and endpoint. Local generation uses the editable `ollama_model`, initially `llama3.1:8b`.

On the Ollama host, prepare the chosen generation model and the required vector model:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Profile writes, job similarity, feedback writes and feedback queries always use Ollama `nomic-embed-text`, independent of generation choices. A different `OLLAMA_EMBED_MODEL` does not override this application invariant. The explicit local embeddings check lists models; it does not certify vector quality. Scrapers, LinkedIn and frontend CDNs still need external access; local AI is not a guarantee of fully offline operation.

### GPU & NPU Hardware Acceleration
Acceleration depends on the installed Ollama build, operating system, drivers and supported hardware. Jobot sends requests to Ollama; it does not install GPU/NPU runtimes or certify device compatibility. Confirm supported hardware and model memory requirements with your Ollama installation before changing worker concurrency.

### Provider Vault and Task Assignments

The eight independent provider forms save encrypted, account-owned keys. Password fields always render empty; **Saved** reports presence only. Blank or whitespace-only secret submissions retain the existing key, not delete it. **Save Credentials** persists a replacement; **Test Connection** may use an unsaved replacement without saving it. A saved token cannot be tested against a changed unsaved endpoint unless you submit a new token explicitly.

| Provider ID | Editable default model hint | Endpoint |
|---|---|---|
| `ollama` | `llama3.1:8b` | Owner's `ollama_base_url`; optional bearer token |
| `openai` | `gpt-4o-mini` | `https://api.openai.com/v1` |
| `anthropic` | `claude-sonnet-4-5` | `https://api.anthropic.com` (native Messages API) |
| `gemini` | `gemini-2.5-flash` | `https://generativelanguage.googleapis.com` (native generateContent API) |
| `groq` | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1` |
| `deepseek` | `deepseek-chat` | `https://api.deepseek.com` |
| `openrouter` | `openai/gpt-4o-mini` | `https://openrouter.ai/api/v1` |
| `custom` | Explicit model required | Owner's `provider_custom_url`, OpenAI-compatible |

Model hints are not promises of current availability, billing access or output quality. OpenAI and other cloud providers use their fixed endpoints for Settings, probes and generation. Local/custom URLs accept HTTP or HTTPS but reject embedded credentials, query strings and fragments; redirects are not followed. Only connect to endpoints you trust with your private text and keys.

**Save Routing** persists these exact pairs:

| Stage | Provider field | Model field | Work |
|---|---|---|---|
| Scraping | `task_scraping_provider` | `task_scraping_model` | Search strategy, AI extraction and profile parsing/bio |
| Scoring | `task_scoring_provider` | `task_scoring_model` | Fit evaluation |
| Applying | `task_applying_provider` | `task_applying_model` | Cover letters and tailored resume bullets, not employer submission |

Keys use `provider_{provider}_key`, for example `provider_gemini_key`; provider model hints use `{provider}_model`. Task models are independently editable. Legacy `ai_provider`, `openai_api_key` and `openai_model` remain compatible for the same owner. A noncanonical legacy `openai_base_url` is rejected before the OpenAI key is sent; configure OpenAI-compatible endpoints with the `custom` provider, its own key and `provider_custom_url`. A successful settings save fills missing task/vault fields without overwriting explicit values; a legacy custom key migrates to custom, not OpenAI. Viewing/testing settings does not migrate credentials. Global/environment keys and another account's credentials are never inherited.

| Preset ID / Label | Scraping | Scoring | Applying |
|---|---|---|---|
| `local` / 100% Free / Local | `ollama` + owner's `ollama_model` | `ollama` + owner's `ollama_model` | `ollama` + owner's `ollama_model` |
| `hybrid` / Cost-Optimized Hybrid | `ollama` + owner's `ollama_model` | `ollama` + owner's `ollama_model` | `openai` + `gpt-4o-mini` |
| `cloud` / Max Quality Cloud | `openai` + `gpt-4o-mini` | `openai` + `gpt-4o-mini` | `openai` + `gpt-4o-mini` |

Presets change exactly six assignment fields atomically, never keys/endpoints. Hybrid/cloud require the owner's OpenAI key; a missing key produces visible 422 feedback with no writes. Partial manual routing configuration can be saved before keys are available, but a cloud call without its required key fails. Preset labels are product names, not measured cost savings or comparative quality; local models still consume hardware and energy.

Without owner overrides, Settings, connection tests, local/hybrid presets and execution use the installation's non-secret Ollama endpoint/model. Saving those displayed values does not redirect an existing host/container setup to localhost. Installation credentials are never inherited.

**Connection test limits:** tests are explicit, bounded to five seconds and non-generating. Cloud success reports **Reachable; credentials unverified** because model listing does not prove generation capability, billing or model entitlement. Opening Settings does not probe providers. Generation has a 120-second whole-operation deadline and cloud connection timeout of five seconds; failures do not silently select another model or fabricate content.

### Refreshing Model Suggestions (Phase 18)

Each provider card has a **Refresh models** button. It asks that provider for its own model list and offers the result as suggestions in the Model fields (provider cards and the Scraping/Scoring/Applying rows, which follow the provider selected for that task). Opening Settings never fetches lists, and the key travels only in the form body.

- **Listed is not verified.** A model that appears in the list is advertised by the provider; it is not proof that your key can generate with it. Only generation proves that.
- **Free text always works.** You can type any model ID. If a list is loaded and your ID is not in it, a non-blocking warning reads "Not in provider list. You can still save; generation may fail." Save is never disabled, and Jobot never rewrites or switches your model.
- **Caching.** Lists are cached for five minutes per account, provider, endpoint and key. A manual refresh bypasses the cache but is limited to once every five seconds per provider ("Wait a few seconds before refreshing again"). Changing a key or endpoint discards the cached list. Lists are never shared between accounts.
- **Test Connection** also checks your configured model against the list and reports listed, not in provider list, or not checked (when the list could not be fetched).
- **Ollama.** Test Connection checks that every Ollama-assigned chat model and `nomic-embed-text` exist on the host. Missing models show a display-only hint such as `ollama pull nomic-embed-text`; run it yourself on the Ollama host. Jobot never pulls or switches models for you. **Test Local Embeddings** shows the same hint when a reachable host lacks `nomic-embed-text`.

### Manual Recovery and Local Vectors

1. Inspect the selected provider/model and safe category in Settings, the Job Inspector or AI Queue. Authentication, quota, rate-limit, timeout and invalid-response errors are distinct; raw provider bodies and saved keys are not diagnostics.
2. Correct credentials/model/endpoint, wait for a rate limit to clear, or choose **Switch to Local Ollama**. This changes all three assignments only; it does not retry, enqueue work, change credentials or start Ollama.
3. Ensure the configured Ollama host has the selected model and `nomic-embed-text`. Then separately choose the owned task's **Retry** or regenerate the application material. A failed operation leaves previous job scores, materials and vectors intact; already successful earlier operations are not rolled back as one cross-store transaction.

Provider-failed queue tasks remain failed until an explicit retry. Settings **Rescore All Stored Jobs** displays safe failures with separate local-switch and Retry actions. Cover-letter Retry retains the tone and custom instructions in the original options form; switching providers does not generate or replace a letter.

An ordinary profile save can report a partial result when SQL data was saved but vector sync failed. CV/LinkedIn imports prepare vectors before persisting the imported profile; provider/vector failure preserves the previous profile instead of reporting successful sync.

For `embedding_dimension`, do not reset collections, delete `data/`, substitute zero vectors, switch to cloud embeddings or change the embedding model to bypass the error. Stop writes/workers, back up SQLite, the configured `CHROMA_DIR`, and matching encryption keys, and confirm the Ollama endpoint/model. If existing vectors belong to an incompatible space, an operator must plan an explicit re-index from the source profile/feedback into a separate backed-up store and validate it before replacement. Phase 17 provides no automatic re-index button or migration command. Switching generation to local alone cannot repair an incompatible vector collection. Shared vector collection partitioning and database/vector atomicity are not redesigned by this routing feature.

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
- **AI extraction fallback (StepStone)**: under **Settings > AI-Assisted Scraping & Query Strategy**, tick **Use AI extraction fallback (StepStone)** (off by default, saved per account). When StepStone's normal result cards cannot be parsed, the cleaned page is sent to your configured *scraping* model, and spam or non-job pages are discarded. AI search-query generation is always on and is not affected by this toggle. If the model is unavailable the scrape task fails visibly and is never replaced by guessed jobs. Page text goes to the provider you assigned to scraping, so choose a local model if that text must stay private.
- **Worker recovery and concurrency**: tasks left `in_progress` by a crashed worker are returned to pending at start, and the running worker also reclaims claims older than the lease (`task_lease_seconds`, default 900 seconds, minimum 60), so a task running longer than the lease may be executed twice. Changes to the scraper/evaluator concurrency settings are applied within about a minute without a restart; reductions take effect as surplus loops become idle.

---

## 10. Title, Company & Keyword Blacklists
Conserve compute and hide unwanted roles before AI scoring:
- **Title Blacklist**: Exclude terms like `"Director"`, `"Lead"`, `"Intern"`, `"Staff"`.
- **Company Blacklist**: Exclude specific employers.
- **Negative Keywords**: Exclude descriptions containing terms like `"C1 German"`, `"No Visa Sponsorship"`, `"50% Travel"`.

---

## 11. Adaptive Feedback Loop
- Moving a job to `applied` or an `interview` stage records a positive feedback vector; `not a good fit` or `rejected` records a negative one. A note with positive or negative sentiment records its own vector. Moves without a signal (for example `seen`) record nothing.
- Vectors are stored per account with the local `nomic-embed-text` model. Later jobs similar to your disliked roles lose up to 25 points of fit; similar to liked roles gain up to 10. If the embedding model is unreachable, your status or note is still saved and a warning explains that learning feedback was not recorded.
- **Settings → Suggestions from your feedback** proposes blacklist rules (recurring words in negative notes and repeatedly rejected titles) and search terms (from roles you applied to or interviewed for). Nothing is applied automatically: **Add rule** / **Add search** create a rule or search for your account, **Dismiss** stores the rule as inactive so it is not proposed again, and **Hide** only removes a search term from the current view. Suggestions are simple frequency heuristics and need at least two occurrences.

---

## 11a. System Alerts & Diagnostics
- A banner below the header is refreshed every 15 seconds and after view changes. It lists problems recorded by your failed queue tasks: AI provider unreachable, credential/quota problems, rate limits, LinkedIn session problems, and a paused queue, each with an **Open** button to the relevant view. It reports recorded failures only; it does not probe providers.
- `GET /api/diagnostics/health` (signed-in session required) returns database, vector store, queue counts, configured AI provider name and your current alerts. It contains no keys, cookies or URLs and does not test provider reachability; use the connection tests in Settings for that.
- Jobot never invents job listings: if a site page contains no parsable job cards, no jobs are returned.

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
*Last updated: 2026-10-28. Phase 17 routing and Phase 18 model-discovery documentation synchronized with implementation; Phase 17/18 UAT passed. Provider billing/entitlement, generation quality and exhaustive accessibility are not certified.*
