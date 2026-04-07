<div align="center">

<img src="../assets/banner.svg" alt="Noosphere" width="100%"/>

</div>

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · [中文（繁體）](./README.zh-TW.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Deutsch](./README.de.md) · **[Português](./README.pt.md)**

</div>

---

> **Simulador de validação de produtos com IA** — simule como comunidades reais reagiriam à sua ideia antes do lançamento.

O Noosphere gera personas diversificadas em plataformas como Hacker News, Product Hunt, Reddit, LinkedIn e IndieHackers, e conduz discussões de múltiplas rodadas com LLMs para extrair críticas, sentimentos e sugestões de melhoria acionáveis.

---

## Índice

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Stack de tecnologia](#stack-de-tecnologia)
- [Pré-requisitos](#pré-requisitos)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Instalação](#instalação)
- [Como executar](#como-executar)
- [Referência de API](#referência-de-api)

---

## Visão geral

Você descreve seu produto. O Noosphere cria centenas de personas de IA (desenvolvedores, investidores, céticos, early adopters) em múltiplas plataformas sociais e as coloca para debater sua ideia de forma realista. A simulação produz um relatório estruturado com:

- Análise de sentimento por plataforma
- Clusters de críticas com temas recorrentes
- Melhorias sugeridas com base no feedback da comunidade
- Relatório PDF exportável (via Typst)

---

## Funcionalidades

- Simulação multiplataforma: Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- Integração com OpenAI GPT
- Streaming em tempo real via Server-Sent Events (SSE)
- Simulações retomáveis com checkpoints
- Extração de grafo de conhecimento / ontologia
- Exportação de relatório PDF
- Histórico completo de simulações
- Interface responsiva para mobile
- Deploy com Docker

---

## Stack de tecnologia

**Backend**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (fila de tarefas assíncrona)
- SQLite (persistência)
- OpenAI SDK
- Typst (geração de PDF)

**Frontend**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**Infraestrutura**
- Docker + Docker Compose
- Redis 7

---

## Pré-requisitos

- Docker & Docker Compose (recomendado), **ou** Python 3.11+ e Node.js 20+
- Redis (ao executar localmente sem Docker)
- Chave de API da OpenAI obrigatória

---

## Variáveis de ambiente

```bash
cp .env.example .env
```

### Chave de API LLM (obrigatória)

**`OPENAI_API_KEY`**
Chave da API da OpenAI.
- Cadastre-se em: https://platform.openai.com
- Vá em **API keys** → **Create new secret key**

---

### Chaves de fontes de dados (opcionais)

**`SERPER_API_KEY`**
Google Search API via Serper.dev. Habilita busca na web para contexto do mundo real.
- Cadastre-se em: https://serper.dev
- Plano gratuito: 2.500 consultas/mês
- Vá em **Dashboard** → copie sua API key

**`PRODUCT_HUNT_API_KEY`**
API do Product Hunt para buscar produtos em alta e dados da comunidade.
- Solicite acesso em: https://api.producthunt.com/v2/docs
- Vá em **Developer Settings** → crie uma aplicação → copie o API token

**`SEMANTIC_SCHOLAR_API_KEY`**
API acadêmica Semantic Scholar para contexto de artigos de pesquisa.
- Solicite acesso em: https://www.semanticscholar.org/product/api
- Plano gratuito disponível; funciona sem chave, mas com chave os rate limits são mais altos.

**`GITHUB_TOKEN`**
GitHub Personal Access Token para buscar dados de repositórios.
- Gere o seu em: https://github.com/settings/tokens
- Clique em **Generate new token (classic)** → selecione o scope `public_repo` → gere

---

### Infraestrutura

**`REDIS_URL`**
URL de conexão do Redis (broker do Celery).
Padrão: `redis://localhost:6379/0`
Com Docker Compose: `redis://redis:6379/0`

**`DB_PATH`** — Caminho do banco SQLite. Padrão: `noosphere.db`
**`SOURCES_DB_PATH`** — Caminho do banco de cache. Padrão: `noosphere_sources.db`

---

### Configuração de jobs

**`MAX_JOBS`** — Simulações concorrentes máximas. Padrão: `5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — Timeout da fila. Padrão: `900` (15 minutos)
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — Intervalo de heartbeat. Padrão: `90`

---

### Limites de taxa

**`OPENAI_RPM`** — Requisições por minuto da OpenAI. Padrão: `500`
**`OPENAI_RPM_SAFETY`** — Fator de margem de segurança (0–1). Padrão: `0.80`
**`OPENAI_TPM`** — Tokens por minuto da OpenAI. Padrão: `100000`

Consulte os limites reais no dashboard da OpenAI e ajuste conforme necessário.

---

### Frontend

**`VITE_API_URL`** *(em `frontend/.env`)*
URL base do backend. Padrão: `http://localhost:8000`

---

## Instalação

### Opção A: Docker Compose (recomendado)

```bash
git clone https://github.com/JoCoding-Inc/Noosphere.git
cd Noosphere
cp .env.example .env
# Edite .env com suas chaves de API

docker-compose up --build
```

Serviços:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Redis: localhost:6379

### Opção B: Desenvolvimento local

**Backend**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Em outro terminal
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Roda em http://localhost:5173
```

---

## Como executar

1. Abra http://localhost:5173 no navegador
2. Insira a descrição do seu produto na página inicial
3. Escolha o número de rodadas, as plataformas alvo e o provedor LLM
4. Acompanhe a simulação em tempo real
5. Revise o relatório estruturado e exporte como PDF
6. Consulte simulações anteriores na página de histórico

---

## Referência de API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Verificar saúde do serviço |
| POST | `/simulate` | Iniciar nova simulação |
| GET | `/simulate-stream/{sim_id}` | Stream SSE em tempo real |
| GET | `/results/{sim_id}` | Obter resultados concluídos |
| GET | `/history` | Listar todas as simulações |
| GET | `/export/{sim_id}` | Baixar relatório PDF |
| POST | `/simulate/{sim_id}/cancel` | Cancelar simulação em andamento |
| POST | `/simulate/{sim_id}/resume` | Retomar simulação pausada |
| DELETE | `/simulate/{sim_id}` | Excluir simulação |
| GET | `/simulate/{sim_id}/status` | Verificar status da simulação |
