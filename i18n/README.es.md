# Noosphere

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · [中文（繁體）](./README.zh-TW.md) · **[Español](./README.es.md)** · [Français](./README.fr.md) · [Deutsch](./README.de.md) · [Português](./README.pt.md)

</div>

---

> **Simulador de validación de productos con IA** — simula cómo reaccionarían comunidades reales a tu idea antes de lanzarla.

Noosphere genera personas diversas en plataformas como Hacker News, Product Hunt, Reddit, LinkedIn e IndieHackers, y ejecuta discusiones de múltiples rondas con LLMs para extraer críticas, sentimientos y sugerencias de mejora accionables.

---

## Tabla de contenidos

- [Descripción general](#descripción-general)
- [Funcionalidades](#funcionalidades)
- [Tecnologías](#tecnologías)
- [Requisitos previos](#requisitos-previos)
- [Variables de entorno](#variables-de-entorno)
- [Instalación](#instalación)
- [Cómo ejecutarlo](#cómo-ejecutarlo)
- [Referencia de API](#referencia-de-api)

---

## Descripción general

Describes tu producto y Noosphere crea cientos de personas de IA (desarrolladores, inversores, escépticos, early adopters) en múltiples plataformas sociales y las pone a debatir tu idea de forma realista. La simulación produce un informe estructurado con:

- Análisis de sentimiento por plataforma
- Clústeres de críticas con temas recurrentes
- Mejoras sugeridas basadas en el feedback de la comunidad
- Informe PDF exportable (vía Typst)

---

## Funcionalidades

- Simulación multiplataforma: Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- Soporte multi-LLM: Anthropic Claude, OpenAI GPT, Google Gemini
- Streaming en tiempo real vía Server-Sent Events (SSE)
- Simulaciones reanudables con checkpoints
- Extracción de grafo de conocimiento / ontología desde el input
- Exportación de informe PDF
- Historial completo de simulaciones
- Despliegue con Docker

---

## Tecnologías

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (cola de tareas asíncrona)
- SQLite (persistencia)
- Anthropic, OpenAI, Google Generative AI SDKs
- Typst (generación de PDF)

**Frontend**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**Infraestructura**
- Docker + Docker Compose
- Redis 7

---

## Requisitos previos

- Docker & Docker Compose (recomendado), **o** Python 3.11+ y Node.js 20+
- Redis (si se ejecuta localmente sin Docker)
- Al menos una clave API de LLM: Anthropic, OpenAI o Google Gemini

---

## Variables de entorno

```bash
cp .env.example .env
```

### Claves API de LLM (al menos una obligatoria)

**`ANTHROPIC_API_KEY`**
Clave de la API de Claude de Anthropic.
- Regístrate en: https://console.anthropic.com
- Ve a **API Keys** → **Create Key**
- Se usa como proveedor LLM principal para la generación de personas y rondas de discusión.

**`OPENAI_API_KEY`**
Clave de la API de OpenAI.
- Regístrate en: https://platform.openai.com
- Ve a **API keys** → **Create new secret key**
- Se usa como proveedor LLM alternativo/fallback.

**`GEMINI_API_KEY`**
Clave de la API de Google Gemini.
- Obtén tu clave en: https://aistudio.google.com/app/apikey
- Se usa como proveedor LLM alternativo/fallback.

---

### Claves de fuentes de datos (opcionales)

**`SERPER_API_KEY`**
Google Search API vía Serper.dev. Habilita la búsqueda web para contexto del mundo real.
- Regístrate en: https://serper.dev
- Plan gratuito: 2.500 consultas/mes
- Ve a **Dashboard** → copia tu API key

**`PRODUCT_HUNT_API_KEY`**
API de Product Hunt para obtener productos trending y datos de comunidad.
- Solicita acceso en: https://api.producthunt.com/v2/docs
- Ve a **Developer Settings** → crea una aplicación → copia el API token

**`SEMANTIC_SCHOLAR_API_KEY`**
API académica de Semantic Scholar para contexto de papers de investigación.
- Solicita acceso en: https://www.semanticscholar.org/product/api
- Tiene plan gratuito; sin clave también funciona, pero con clave los rate limits son más altos.

**`GITHUB_TOKEN`**
GitHub Personal Access Token para obtener datos de repositorios.
- Genera el tuyo en: https://github.com/settings/tokens
- Haz clic en **Generate new token (classic)** → selecciona el scope `public_repo` → genera

---

### Infraestructura

**`REDIS_URL`**
URL de conexión a Redis (broker de Celery).
Por defecto: `redis://localhost:6379/0`
Con Docker Compose: `redis://redis:6379/0`

**`DB_PATH`** — Ruta del archivo SQLite. Por defecto: `noosphere.db`
**`SOURCES_DB_PATH`** — Ruta de la base de datos de caché. Por defecto: `noosphere_sources.db`

---

### Configuración de trabajos

**`MAX_JOBS`** — Simulaciones concurrentes máximas. Por defecto: `5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — Timeout de la cola. Por defecto: `900` (15 minutos)
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — Intervalo de heartbeat. Por defecto: `90`

---

### Límites de tasa

**`OPENAI_RPM`** — Solicitudes por minuto de OpenAI. Por defecto: `500`
**`OPENAI_RPM_SAFETY`** — Factor de margen de seguridad (0–1). Por defecto: `0.80`
**`OPENAI_TPM`** — Tokens por minuto de OpenAI. Por defecto: `100000`
**`ANTHROPIC_TPM`** — Tokens por minuto de Anthropic. Por defecto: `40000`
**`GEMINI_TPM`** — Tokens por minuto de Gemini. Por defecto: `250000`

Consulta los límites reales en el dashboard de cada proveedor y ajústalos en consecuencia.

---

### Frontend

**`VITE_API_URL`** *(en `frontend/.env`)*
URL base del backend. Por defecto: `http://localhost:8000`

---

## Instalación

### Opción A: Docker Compose (recomendado)

```bash
git clone https://github.com/your-username/noosphere.git
cd noosphere
cp .env.example .env
# Edita .env con tus claves API

docker-compose up --build
```

Servicios:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Redis: localhost:6379

### Opción B: Desarrollo local

**Backend**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# En otra terminal
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Se ejecuta en http://localhost:5173
```

---

## Cómo ejecutarlo

1. Abre http://localhost:5173 en tu navegador
2. Introduce la descripción de tu producto en la página principal
3. Elige el número de rondas y las plataformas objetivo
4. Observa la simulación en tiempo real
5. Revisa el informe estructurado y expórtalo como PDF
6. Consulta simulaciones anteriores en la página de historial

---

## Referencia de API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/simulate` | Iniciar nueva simulación |
| GET | `/simulate-stream/{id}` | Stream SSE en tiempo real |
| GET | `/results/{id}` | Obtener resultados completados |
| GET | `/history` | Listar todas las simulaciones |
| GET | `/export/{id}` | Descargar informe PDF |
| POST | `/simulate/{id}/cancel` | Cancelar simulación en curso |
| POST | `/simulate/{id}/resume` | Reanudar simulación pausada |
| DELETE | `/simulate/{id}` | Eliminar simulación |
| GET | `/simulate/{id}/status` | Consultar estado |
