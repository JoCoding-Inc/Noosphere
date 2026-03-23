# Noosphere

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · [中文（繁體）](./README.zh-TW.md) · [Español](./README.es.md) · [Français](./README.fr.md) · **[Deutsch](./README.de.md)** · [Português](./README.pt.md)

</div>

---

> **KI-gestützter Produktvalidierungs-Simulator** — simulieren Sie, wie echte Communities auf Ihre Produktidee reagieren würden, bevor Sie es launchen.

Noosphere generiert vielfältige Personas auf Plattformen wie Hacker News, Product Hunt, Reddit, LinkedIn und IndieHackers und führt mithilfe von LLMs mehrrundige Diskussionen durch, um Kritik, Stimmungen und umsetzbare Verbesserungsvorschläge zu extrahieren.

---

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Funktionen](#funktionen)
- [Technologie-Stack](#technologie-stack)
- [Voraussetzungen](#voraussetzungen)
- [Umgebungsvariablen](#umgebungsvariablen)
- [Installation](#installation)
- [Ausführung](#ausführung)
- [API-Referenz](#api-referenz)

---

## Überblick

Sie beschreiben Ihr Produkt. Noosphere erstellt Hunderte von KI-Personas (Entwickler, Investoren, Skeptiker, Early Adopters) auf mehreren sozialen Plattformen und lässt sie realistisch über Ihre Idee diskutieren. Die Simulation liefert einen strukturierten Bericht mit:

- Stimmungsanalyse je Plattform
- Kritik-Cluster mit wiederkehrenden Themen
- Verbesserungsvorschläge auf Basis des Community-Feedbacks
- Exportierbarer PDF-Bericht (via Typst)

---

## Funktionen

- Multi-Plattform-Simulation: Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- Multi-LLM-Unterstützung: Anthropic Claude, OpenAI GPT, Google Gemini
- Echtzeit-Streaming via Server-Sent Events (SSE)
- Fortsetzbare Simulationen mit Checkpointing
- Wissensgraph / Ontologie-Extraktion aus Eingabetext
- PDF-Bericht-Export
- Vollständiger Simulationsverlauf
- Docker-basiertes Deployment

---

## Technologie-Stack

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (asynchrone Task-Queue)
- SQLite (Persistenz)
- Anthropic, OpenAI, Google Generative AI SDKs
- Typst (PDF-Generierung)

**Frontend**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**Infrastruktur**
- Docker + Docker Compose
- Redis 7

---

## Voraussetzungen

- Docker & Docker Compose (empfohlen), **oder** Python 3.11+ und Node.js 20+
- Redis (bei lokaler Ausführung ohne Docker)
- Mindestens ein LLM-API-Schlüssel: Anthropic, OpenAI oder Google Gemini

---

## Umgebungsvariablen

```bash
cp .env.example .env
```

### LLM-API-Schlüssel (mindestens einer erforderlich)

**`ANTHROPIC_API_KEY`**
Claude-API-Schlüssel von Anthropic.
- Registrierung: https://console.anthropic.com
- Gehen Sie zu **API Keys** → **Create Key**
- Wird als primärer LLM-Anbieter für Persona-Generierung und Diskussionsrunden verwendet.

**`OPENAI_API_KEY`**
OpenAI-API-Schlüssel.
- Registrierung: https://platform.openai.com
- Gehen Sie zu **API keys** → **Create new secret key**
- Wird als alternativer/Fallback-LLM-Anbieter verwendet.

**`GEMINI_API_KEY`**
Google-Gemini-API-Schlüssel.
- Schlüssel erhalten: https://aistudio.google.com/app/apikey
- Wird als alternativer/Fallback-LLM-Anbieter verwendet.

---

### Datenquellen-API-Schlüssel (optional)

**`SERPER_API_KEY`**
Google Search API via Serper.dev. Aktiviert die Websuche für realen Kontext.
- Registrierung: https://serper.dev
- Kostenloser Plan: 2.500 Anfragen/Monat
- Gehen Sie zu **Dashboard** → kopieren Sie Ihren API-Schlüssel

**`PRODUCT_HUNT_API_KEY`**
Product Hunt API zum Abrufen von Trending-Produkten und Community-Daten.
- Beantragung: https://api.producthunt.com/v2/docs
- Gehen Sie zu **Developer Settings** → erstellen Sie eine Anwendung → kopieren Sie den API-Token

**`SEMANTIC_SCHOLAR_API_KEY`**
Semantic Scholar Academic API für den Kontext von Forschungspublikationen.
- Zugang beantragen: https://www.semanticscholar.org/product/api
- Kostenloser Plan verfügbar; funktioniert auch ohne Schlüssel, aber mit Schlüssel sind die Rate-Limits höher.

**`GITHUB_TOKEN`**
GitHub Personal Access Token zum Abrufen von Repository-Daten.
- Generieren Sie Ihren unter: https://github.com/settings/tokens
- Klicken Sie auf **Generate new token (classic)** → wählen Sie den Scope `public_repo` → generieren

---

### Infrastruktur

**`REDIS_URL`**
Redis-Verbindungs-URL (Celery-Broker).
Standard: `redis://localhost:6379/0`
Mit Docker Compose: `redis://redis:6379/0`

**`DB_PATH`** — SQLite-Datenbankpfad. Standard: `noosphere.db`
**`SOURCES_DB_PATH`** — Cache-Datenbankpfad. Standard: `noosphere_sources.db`

---

### Job-Konfiguration

**`MAX_JOBS`** — Maximale gleichzeitige Simulationen. Standard: `5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — Warteschlangen-Timeout. Standard: `900` (15 Minuten)
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — Heartbeat-Intervall. Standard: `90`

---

### Rate-Limiting

**`OPENAI_RPM`** — OpenAI-Anfragen pro Minute. Standard: `500`
**`OPENAI_RPM_SAFETY`** — Sicherheitsmarge-Faktor (0–1). Standard: `0.80`
**`OPENAI_TPM`** — OpenAI-Tokens pro Minute. Standard: `100000`
**`ANTHROPIC_TPM`** — Anthropic-Tokens pro Minute. Standard: `40000`
**`GEMINI_TPM`** — Gemini-Tokens pro Minute. Standard: `250000`

Überprüfen Sie die tatsächlichen Limits im Dashboard jedes Anbieters und passen Sie sie entsprechend an.

---

### Frontend

**`VITE_API_URL`** *(in `frontend/.env`)*
Backend-API-Basis-URL. Standard: `http://localhost:8000`

---

## Installation

### Option A: Docker Compose (empfohlen)

```bash
git clone https://github.com/your-username/noosphere.git
cd noosphere
cp .env.example .env
# Bearbeiten Sie .env mit Ihren API-Schlüsseln

docker-compose up --build
```

Dienste:
- Frontend: http://localhost:5173
- Backend-API: http://localhost:8000
- Redis: localhost:6379

### Option B: Lokale Entwicklung

**Backend**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# In einem anderen Terminal
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Läuft auf http://localhost:5173
```

---

## Ausführung

1. Öffnen Sie http://localhost:5173 im Browser
2. Geben Sie auf der Startseite Ihre Produktbeschreibung ein
3. Wählen Sie Simulationsrunden und Zielplattformen
4. Beobachten Sie die Simulation in Echtzeit
5. Überprüfen Sie den strukturierten Bericht und exportieren Sie ihn als PDF
6. Sehen Sie vergangene Simulationen auf der Verlaufsseite ein

---

## API-Referenz

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| POST | `/simulate` | Neue Simulation starten |
| GET | `/simulate-stream/{id}` | Echtzeit-SSE-Stream |
| GET | `/results/{id}` | Abgeschlossene Ergebnisse abrufen |
| GET | `/history` | Alle Simulationen auflisten |
| GET | `/export/{id}` | PDF-Bericht herunterladen |
| POST | `/simulate/{id}/cancel` | Laufende Simulation abbrechen |
| POST | `/simulate/{id}/resume` | Pausierte Simulation fortsetzen |
| DELETE | `/simulate/{id}` | Simulation löschen |
| GET | `/simulate/{id}/status` | Simulationsstatus prüfen |
