<div align="center">

<img src="../assets/banner.svg" alt="Noosphere" width="100%"/>

</div>

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
- OpenAI GPT-Integration
- Echtzeit-Streaming via Server-Sent Events (SSE)
- Fortsetzbare Simulationen mit Checkpointing
- Wissensgraph / Ontologie-Extraktion aus Eingabetext
- PDF-Bericht-Export
- Vollständiger Simulationsverlauf
- Mobile-optimierte Benutzeroberfläche
- Docker-basiertes Deployment

---

## Technologie-Stack

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (asynchrone Task-Queue)
- SQLite (Persistenz)
- OpenAI SDK
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
- OpenAI-API-Schlüssel erforderlich

---

## Umgebungsvariablen

```bash
cp .env.example .env
```

### LLM-API-Schlüssel (erforderlich)

**`OPENAI_API_KEY`**
OpenAI-API-Schlüssel.
- Registrierung: https://platform.openai.com
- Gehen Sie zu **API keys** → **Create new secret key**

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

Überprüfen Sie die tatsächlichen Limits im OpenAI-Dashboard und passen Sie sie entsprechend an.

---

### Frontend

**`VITE_API_URL`** *(in `frontend/.env`)*
Backend-API-Basis-URL. Standard: `http://localhost:8000`

---

## Installation

### Option A: Docker Compose (empfohlen)

```bash
git clone https://github.com/JoCoding-Inc/Noosphere.git
cd Noosphere
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
3. Wählen Sie Simulationsrunden, Zielplattformen und LLM-Anbieter
4. Beobachten Sie die Simulation in Echtzeit
5. Überprüfen Sie den strukturierten Bericht und exportieren Sie ihn als PDF
6. Sehen Sie vergangene Simulationen auf der Verlaufsseite ein

---

## API-Referenz

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/health` | Dienststatus prüfen |
| POST | `/simulate` | Neue Simulation starten |
| GET | `/simulate-stream/{sim_id}` | Echtzeit-SSE-Stream |
| GET | `/results/{sim_id}` | Abgeschlossene Ergebnisse abrufen |
| GET | `/history` | Alle Simulationen auflisten |
| GET | `/export/{sim_id}` | PDF-Bericht herunterladen |
| POST | `/simulate/{sim_id}/cancel` | Laufende Simulation abbrechen |
| POST | `/simulate/{sim_id}/resume` | Pausierte Simulation fortsetzen |
| DELETE | `/simulate/{sim_id}` | Simulation löschen |
| GET | `/simulate/{sim_id}/status` | Simulationsstatus prüfen |
