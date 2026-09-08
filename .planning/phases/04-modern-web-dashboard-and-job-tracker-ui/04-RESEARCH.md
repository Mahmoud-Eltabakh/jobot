# Phase 4: Modern Web Dashboard & Job Tracker UI - Research

## Overview
Phase 4 implements the user-facing web dashboard for Jobot using a pure Python web stack: **FastAPI + Jinja2 + HTMX + Tailwind CSS**. It delivers an interactive, responsive interface with zero Node.js/npm dependencies, featuring an 8-column Kanban board, sortable/filterable Data Table view, split-pane Job Inspector, dynamic multi-criteria filter toolbar, and a comprehensive Settings panel for live AI provider and blacklist management.

## Technical Architecture & Design Decisions

### 1. Pure Python Frontend Stack (FastAPI + Jinja2 + HTMX + Tailwind CSS)
- **Zero Node.js Overhead**: Eliminates complex frontend build pipelines, bundling configs, and npm security vulnerabilities.
- **HTMX Reactivity**:
  - `hx-get`, `hx-post`, `hx-put`, `hx-target`, `hx-swap` for smooth partial-DOM updates without full page reloads.
  - Interactive status transitions, live search queries, and instant filter updates.
- **Tailwind CSS Styling**:
  - Modern Dark Theme (Zinc/Slate palette with Emerald match accents, Indigo status pills, and high-contrast typography).
  - Responsive layout adapting to mobile, tablet, and wide desktop displays.

### 2. View Architecture & Components
- **Kanban Board (`templates/components/kanban.html`)**:
  - 8 distinct swimlanes for application lifecycle:
    1. `seen` (New arrivals)
    2. `applied` (Application sent)
    3. `waiting for respond` (Awaiting response)
    4. `1. interview` (First round / screening)
    5. `2. interview` (Technical / team round)
    6. `3. interview` (Final round)
    7. `not a good fit` (Disqualified by candidate)
    8. `rejected` (Company rejection)
  - Card elements displaying Title, Company, Location badge, Remote badge, Salary tag, and Fit Score indicator (color-coded $\ge 80\%$ Emerald, $60-79\%$ Amber, $<60\%$ Slate).
  - One-click move buttons and stage dropdowns to change status via `PUT /api/jobs/{id}/status`.
- **Data Table View (`templates/components/table.html`)**:
  - Compact data grid with sorting on column headers (`Fit Score`, `Salary`, `Date Posted`, `Company`, `Title`).
  - Batch actions and row clicks opening the Job Inspector.
- **Job Inspector Drawer / Modal (`templates/components/job_inspector.html`)**:
  - Split-pane layout displaying:
    1. Full job description with highlighted keywords.
    2. AI match evaluation breakdown (Score gauge, Key Pros list, Potential Cons list, Missing Skills list, Recommendation badge).
    3. Direct application link button opening original posting in new tab.
    4. Interactive Candidate Notes & Status History log editor.

### 3. Multi-Criteria Sorting & Filtering Toolbar (`templates/components/filter_bar.html`)
- **HTMX-driven Live Filtering**:
  - **Dynamic Fit Score Threshold**: Range slider ($\ge 0\%$ to $\ge 90\%$).
  - **Work Model Filter**: Toggle buttons for `All`, `Remote Only`, `Hybrid`, `On-site`.
  - **Salary Minimum**: Input field with currency normalization.
  - **Source Checkboxes**: `LinkedIn`, `StepStone`, `Google Jobs`.
  - **Exclusion Switches**: `"Hide Rejected"`, `"Hide Not a Good Fit"`.
  - **Search Input**: Live debounce (`hx-trigger="keyup changed delay:300ms"`).

### 4. Settings & AI Provider Configurator (`templates/components/settings.html`)
- **AI Backend Toggle**: Switch between `Local Ollama` and `Cloud API / Custom Endpoint`.
- **Connection Test Button**: `POST /api/settings/test-ai` verifying provider connectivity with real-time health indicator.
- **Blacklist Manager**: Form to add, delete, and toggle `FilterRule` records (Title words, Company names, Negative keywords).

## Security Controls (STRIDE T-05)
- Jinja2 auto-escaping strictly active for all user and scraped text content.
- Clean URL scheme validation for outbound links.
- CSRF protections and safe HTMX target swaps.

## Validation Architecture
- FastAPI template rendering and route tests (`tests/test_web_routes.py`).
- HTMX partial-swap response validation tests (`tests/test_htmx_views.py`).
- Filter & sorting query parameter integration tests (`tests/test_ui_filters.py`).
- Expected test suite runtime: < 4 seconds.
