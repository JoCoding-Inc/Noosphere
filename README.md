<div align="center">

<img src="./assets/banner.svg" alt="Noosphere" width="100%"/>

**[English](./README.md)** · [한국어](./i18n/README.ko.md) · [日本語](./i18n/README.ja.md) · [中文（简体）](./i18n/README.zh-CN.md) · [中文（繁體）](./i18n/README.zh-TW.md) · [Español](./i18n/README.es.md) · [Français](./i18n/README.fr.md) · [Deutsch](./i18n/README.de.md) · [Português](./i18n/README.pt.md)

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/taeyoung1005)

</div>

---

> **AI-powered product validation simulator** — simulate how real communities would react to your product idea before launch.

Noosphere generates diverse personas across platforms like Hacker News, Product Hunt, Reddit, LinkedIn, and IndieHackers, then runs multi-round discussions using LLMs to surface criticism, sentiment, and actionable improvement suggestions.

---

## Demo

[![Noosphere Demo](https://img.youtube.com/vi/WPQOuvVJQXM/maxresdefault.jpg)](https://youtu.be/WPQOuvVJQXM)

---

## Table of Contents

- [Demo](#demo)
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Running the Project](#running-the-project)
- [API Reference](#api-reference)
- [License](#license)

---

## Overview

You describe your product. Noosphere spins up hundreds of AI personas — developers, investors, skeptics, early adopters — across multiple social platforms and has them discuss your idea in realistic ways. The simulation produces a structured report with:

- Sentiment breakdown by platform
- Criticism clusters with recurring themes
- Suggested improvements based on community feedback
- Exportable PDF report (via Typst)

---

## Features

- Multi-platform simulation: Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- OpenAI GPT integration
- Real-time streaming progress via Server-Sent Events (SSE)
- Resumable simulations with checkpointing
- Knowledge graph / ontology extraction from input
- PDF report export
- Full simulation history
- Mobile-responsive UI
- Docker-based deployment

---

## Tech Stack

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (async task queue)
- SQLite (persistence)
- OpenAI SDK
- Typst (PDF generation)

**Frontend**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**Infrastructure**
- Docker + Docker Compose
- Redis 7

---

## Prerequisites

- Docker & Docker Compose (recommended), **or** Python 3.11+ and Node.js 20+
- Redis (if running locally without Docker)
- OpenAI API key required

---

## Environment Variables

Copy the template and fill in your keys:

```bash
cp .env.example .env
```

### LLM API Key (required)

**`OPENAI_API_KEY`**
OpenAI API key.
- Sign up: https://platform.openai.com
- Go to **API keys** → **Create new secret key**

---

### Data Source API Keys (optional — enrich simulation context)

**`SERPER_API_KEY`**
Google Search API via Serper.dev. Enables web search for real-world context.
- Sign up: https://serper.dev
- Free tier: 2,500 queries/month

**`PRODUCT_HUNT_API_KEY`**
Product Hunt API for fetching trending products and community data.
- Apply at: https://api.producthunt.com/v2/docs

**`SEMANTIC_SCHOLAR_API_KEY`**
Semantic Scholar Academic API for research paper context.
- Request access: https://www.semanticscholar.org/product/api
- Free tier available; key is optional but increases rate limits.

**`GITHUB_TOKEN`**
GitHub Personal Access Token for fetching repository data.
- Go to: https://github.com/settings/tokens
- Click **Generate new token (classic)** → select `public_repo` scope → generate.

---

### Infrastructure

**`REDIS_URL`**
Connection URL for Redis (Celery broker).
Default: `redis://localhost:6379/0`
When using Docker Compose, set to `redis://redis:6379/0`.

**`DB_PATH`**
Path to the SQLite database file.
Default: `noosphere.db`

**`SOURCES_DB_PATH`**
Path to the sources/cache SQLite database.
Default: `noosphere_sources.db`

---

### Job Settings

**`MAX_JOBS`**
Maximum number of concurrent simulation jobs.
Default: `5`

**`SIM_QUEUE_TIMEOUT_SECONDS`**
How long a queued simulation waits before timing out.
Default: `900` (15 minutes)

**`SIM_HEARTBEAT_TIMEOUT_SECONDS`**
Heartbeat interval for detecting stalled simulations.
Default: `90`

---

### Rate Limiting

These prevent you from exceeding your LLM provider quotas.

**`OPENAI_RPM`** — OpenAI requests per minute. Default: `500`
**`OPENAI_RPM_SAFETY`** — Safety margin multiplier (0–1). Default: `0.80`
**`OPENAI_TPM`** — OpenAI tokens per minute. Default: `100000`

Check your actual limits in the OpenAI dashboard and adjust accordingly.

---

### Frontend

**`VITE_API_URL`** *(in `frontend/.env`)*
Backend API base URL. Defaults to `http://localhost:8000`.
Set this if your backend runs on a different host or port.

---

## Installation

### Option A: Docker Compose (Recommended)

```bash
git clone https://github.com/TaeyoungPark1005/Noosphere.git
cd Noosphere
cp .env.example .env
# Edit .env with your API keys

docker-compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Redis: localhost:6379

### Option B: Local Development

**Backend**

```bash
# Install Python dependencies (using uv or pip)
pip install -e ".[dev]"

# Start Redis
redis-server

# Start the FastAPI backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, start the Celery worker
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

---

## Running the Project

1. Open http://localhost:5173 in your browser.
2. Enter a product description on the home page.
3. Choose the number of simulation rounds, target platforms, and LLM provider.
4. Watch the simulation stream in real time.
5. View the structured report and export it as a PDF.
6. Access past simulations from the History page.

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/simulate` | Start a new simulation |
| GET | `/simulate-stream/{sim_id}` | SSE stream for live progress |
| GET | `/results/{sim_id}` | Fetch completed results |
| GET | `/simulate/{sim_id}/status` | Check simulation status |
| POST | `/simulate/{sim_id}/resume` | Resume a paused simulation |
| POST | `/simulate/{sim_id}/cancel` | Cancel a running simulation |
| GET | `/history` | List all past simulations |
| GET | `/export/{sim_id}` | Download PDF report |
| DELETE | `/simulate/{sim_id}` | Delete a simulation |

### POST `/simulate` — Request Body

```json
{
  "input_text": "string (required) — product description",
  "language": "string — output language, default: \"English\"",
  "num_rounds": "integer 1–30, default: 8",
  "max_agents": "integer 1–150, default: 30",
  "platforms": ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"],
  "activation_rate": "float 0.1–1.0, default: 0.25",
  "provider": "\"openai\", default: \"openai\"",
  "source_limits": "object — optional per-source rate overrides"
}
```

---

## License

MIT — see [LICENSE](./LICENSE) for details.
