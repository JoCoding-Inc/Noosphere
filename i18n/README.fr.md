# Noosphere

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · [中文（繁體）](./README.zh-TW.md) · [Español](./README.es.md) · **[Français](./README.fr.md)** · [Deutsch](./README.de.md) · [Português](./README.pt.md)

</div>

---

> **Simulateur de validation de produit par IA** — simulez comment de vraies communautés réagiraient à votre idée avant le lancement.

Noosphere génère des personas diversifiées sur des plateformes comme Hacker News, Product Hunt, Reddit, LinkedIn et IndieHackers, puis conduit des discussions en plusieurs tours via des LLMs pour faire émerger critiques, sentiments et suggestions d'amélioration.

---

## Table des matières

- [Présentation](#présentation)
- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Prérequis](#prérequis)
- [Variables d'environnement](#variables-denvironnement)
- [Installation](#installation)
- [Lancement](#lancement)
- [Référence API](#référence-api)

---

## Présentation

Vous décrivez votre produit. Noosphere crée des centaines de personas IA (développeurs, investisseurs, sceptiques, early adopters) sur plusieurs plateformes sociales et les met en débat de façon réaliste. La simulation produit un rapport structuré incluant :

- Analyse des sentiments par plateforme
- Clusters de critiques regroupés par thèmes récurrents
- Améliorations suggérées à partir des retours communautaires
- Export PDF (via Typst)

---

## Fonctionnalités

- Simulation multi-plateformes : Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- Support multi-LLM : Anthropic Claude, OpenAI GPT, Google Gemini
- Streaming en temps réel via Server-Sent Events (SSE)
- Simulations reprises grâce aux checkpoints
- Extraction de graphe de connaissance / ontologie
- Export de rapport PDF
- Historique complet des simulations
- Déploiement Docker

---

## Stack technique

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (file de tâches asynchrones)
- SQLite (persistance)
- Anthropic, OpenAI, Google Generative AI SDKs
- Typst (génération PDF)

**Frontend**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**Infrastructure**
- Docker + Docker Compose
- Redis 7

---

## Prérequis

- Docker & Docker Compose (recommandé), **ou** Python 3.11+ et Node.js 20+
- Redis (en développement local sans Docker)
- Au moins une clé API LLM : Anthropic, OpenAI ou Google Gemini

---

## Variables d'environnement

```bash
cp .env.example .env
```

### Clés API LLM (au moins une obligatoire)

**`ANTHROPIC_API_KEY`**
Clé API Claude d'Anthropic.
- Inscrivez-vous sur : https://console.anthropic.com
- Allez dans **API Keys** → **Create Key**
- Utilisée comme fournisseur LLM principal pour la génération de personas et les tours de discussion.

**`OPENAI_API_KEY`**
Clé API OpenAI.
- Inscrivez-vous sur : https://platform.openai.com
- Allez dans **API keys** → **Create new secret key**
- Utilisée comme fournisseur LLM alternatif/fallback.

**`GEMINI_API_KEY`**
Clé API Google Gemini.
- Obtenez votre clé sur : https://aistudio.google.com/app/apikey
- Utilisée comme fournisseur LLM alternatif/fallback.

---

### Clés de sources de données (optionnelles)

**`SERPER_API_KEY`**
Google Search API via Serper.dev. Active la recherche web pour le contexte du monde réel.
- Inscription : https://serper.dev
- Offre gratuite : 2 500 requêtes/mois
- Allez dans **Dashboard** → copiez votre clé API

**`PRODUCT_HUNT_API_KEY`**
API Product Hunt pour récupérer les produits tendance et les données communautaires.
- Demande d'accès : https://api.producthunt.com/v2/docs
- Allez dans **Developer Settings** → créez une application → copiez le token API

**`SEMANTIC_SCHOLAR_API_KEY`**
API académique Semantic Scholar pour le contexte des publications de recherche.
- Demande d'accès : https://www.semanticscholar.org/product/api
- Offre gratuite disponible ; fonctionne sans clé, mais les limites de débit sont plus élevées avec.

**`GITHUB_TOKEN`**
GitHub Personal Access Token pour récupérer les données de dépôts.
- Générez le vôtre sur : https://github.com/settings/tokens
- Cliquez sur **Generate new token (classic)** → sélectionnez le scope `public_repo` → générez

---

### Infrastructure

**`REDIS_URL`**
URL de connexion Redis (broker Celery).
Par défaut : `redis://localhost:6379/0`
Avec Docker Compose : `redis://redis:6379/0`

**`DB_PATH`** — Chemin du fichier SQLite. Par défaut : `noosphere.db`
**`SOURCES_DB_PATH`** — Chemin de la base de cache. Par défaut : `noosphere_sources.db`

---

### Configuration des jobs

**`MAX_JOBS`** — Simulations concurrentes maximum. Par défaut : `5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — Timeout de la file d'attente. Par défaut : `900` (15 minutes)
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — Intervalle heartbeat. Par défaut : `90`

---

### Limites de débit

**`OPENAI_RPM`** — Requêtes par minute OpenAI. Par défaut : `500`
**`OPENAI_RPM_SAFETY`** — Facteur de marge de sécurité (0–1). Par défaut : `0.80`
**`OPENAI_TPM`** — Tokens par minute OpenAI. Par défaut : `100000`
**`ANTHROPIC_TPM`** — Tokens par minute Anthropic. Par défaut : `40000`
**`GEMINI_TPM`** — Tokens par minute Gemini. Par défaut : `250000`

Consultez les limites réelles dans le tableau de bord de chaque fournisseur et ajustez en conséquence.

---

### Frontend

**`VITE_API_URL`** *(dans `frontend/.env`)*
URL de base du backend. Par défaut : `http://localhost:8000`

---

## Installation

### Option A : Docker Compose (recommandé)

```bash
git clone https://github.com/your-username/noosphere.git
cd noosphere
cp .env.example .env
# Éditez .env avec vos clés API

docker-compose up --build
```

Services :
- Frontend : http://localhost:5173
- Backend API : http://localhost:8000
- Redis : localhost:6379

### Option B : Développement local

**Backend**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Dans un autre terminal
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Se lance sur http://localhost:5173
```

---

## Lancement

1. Ouvrez http://localhost:5173 dans votre navigateur
2. Saisissez la description de votre produit sur la page d'accueil
3. Choisissez le nombre de tours de simulation et les plateformes cibles
4. Observez la simulation en temps réel
5. Consultez le rapport structuré et exportez-le en PDF
6. Retrouvez vos simulations passées dans la page Historique

---

## Référence API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/simulate` | Démarrer une nouvelle simulation |
| GET | `/simulate-stream/{id}` | Flux SSE en temps réel |
| GET | `/results/{id}` | Récupérer les résultats |
| GET | `/history` | Lister toutes les simulations |
| GET | `/export/{id}` | Télécharger le rapport PDF |
| POST | `/simulate/{id}/cancel` | Annuler une simulation en cours |
| POST | `/simulate/{id}/resume` | Reprendre une simulation en pause |
| DELETE | `/simulate/{id}` | Supprimer une simulation |
| GET | `/simulate/{id}/status` | Consulter le statut |
