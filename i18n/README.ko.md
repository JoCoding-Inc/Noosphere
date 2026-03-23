# Noosphere

<div align="center">

[English](../README.md) · **[한국어](./README.ko.md)** · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · [中文（繁體）](./README.zh-TW.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Deutsch](./README.de.md) · [Português](./README.pt.md)

</div>

---

> **AI 기반 제품 검증 시뮬레이터** — 출시 전에 실제 커뮤니티가 당신의 아이디어에 어떻게 반응할지 시뮬레이션하세요.

Noosphere는 Hacker News, Product Hunt, Reddit, LinkedIn, IndieHackers 등 플랫폼의 다양한 페르소나를 생성하고, LLM을 통해 다회전 토론을 진행해 비판·감정·개선 제안을 도출합니다.

---

## 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [사전 요구사항](#사전-요구사항)
- [환경 변수](#환경-변수)
- [설치](#설치)
- [실행 방법](#실행-방법)
- [API 레퍼런스](#api-레퍼런스)

---

## 개요

제품을 설명하면 Noosphere가 수백 개의 AI 페르소나(개발자, 투자자, 회의론자, 얼리어답터 등)를 생성해 여러 소셜 플랫폼에서 현실적인 토론을 진행합니다. 시뮬레이션 결과는 다음을 포함한 구조화된 보고서로 제공됩니다:

- 플랫폼별 감정 분석
- 반복되는 주제를 모은 비판 클러스터
- 커뮤니티 피드백 기반 개선 제안
- Typst로 생성된 PDF 내보내기

---

## 주요 기능

- 다중 플랫폼 시뮬레이션: Hacker News, Product Hunt, Reddit Startups, LinkedIn, IndieHackers
- 다중 LLM 지원: Anthropic Claude, OpenAI GPT, Google Gemini
- Server-Sent Events(SSE)를 통한 실시간 스트리밍
- 체크포인트 기반 재개 가능한 시뮬레이션
- 입력 텍스트에서 지식 그래프 / 온톨로지 추출
- PDF 보고서 내보내기
- 전체 시뮬레이션 히스토리
- Docker 기반 배포

---

## 기술 스택

**백엔드**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis (비동기 작업 큐)
- SQLite (데이터 저장)
- Anthropic, OpenAI, Google Generative AI SDK
- Typst (PDF 생성)

**프론트엔드**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**인프라**
- Docker + Docker Compose
- Redis 7

---

## 사전 요구사항

- Docker & Docker Compose (권장), **또는** Python 3.11+ 및 Node.js 20+
- Redis (Docker 없이 로컬 실행 시)
- LLM API 키 최소 하나: Anthropic, OpenAI, 또는 Google Gemini

---

## 환경 변수

템플릿을 복사한 뒤 키를 입력하세요:

```bash
cp .env.example .env
```

### LLM API 키 (최소 하나 필수)

**`ANTHROPIC_API_KEY`**
Anthropic의 Claude API 키입니다.
- 가입: https://console.anthropic.com
- **API Keys** → **Create Key**에서 발급
- 페르소나 생성 및 토론 라운드의 기본 LLM 제공자로 사용됩니다.

**`OPENAI_API_KEY`**
OpenAI API 키입니다.
- 가입: https://platform.openai.com
- **API keys** → **Create new secret key**에서 발급
- 대체/폴백 LLM 제공자로 사용됩니다.

**`GEMINI_API_KEY`**
Google Gemini API 키입니다.
- 키 발급: https://aistudio.google.com/app/apikey
- 대체/폴백 LLM 제공자로 사용됩니다.

---

### 데이터 소스 API 키 (선택 사항 — 시뮬레이션 맥락 강화)

**`SERPER_API_KEY`**
Serper.dev를 통한 Google Search API입니다. 실세계 맥락을 위한 웹 검색을 활성화합니다.
- 가입: https://serper.dev
- 무료 티어: 월 2,500 쿼리
- **Dashboard**에서 API 키 확인 및 복사

**`PRODUCT_HUNT_API_KEY`**
트렌딩 제품 및 커뮤니티 데이터 수집을 위한 Product Hunt API입니다.
- 신청: https://api.producthunt.com/v2/docs
- **Developer Settings** → 앱 생성 → API 토큰 복사

**`SEMANTIC_SCHOLAR_API_KEY`**
연구 논문 맥락을 위한 Semantic Scholar Academic API입니다.
- 액세스 신청: https://www.semanticscholar.org/product/api
- 무료 티어 사용 가능. 키가 없어도 동작하나, 키가 있으면 레이트 리밋이 완화됩니다.

**`GITHUB_TOKEN`**
저장소 데이터 조회를 위한 GitHub Personal Access Token입니다.
- 발급: https://github.com/settings/tokens
- **Generate new token (classic)** → `public_repo` 스코프 선택 후 생성

---

### 인프라

**`REDIS_URL`**
Redis 연결 URL (Celery 브로커).
기본값: `redis://localhost:6379/0`
Docker Compose 사용 시: `redis://redis:6379/0`

**`DB_PATH`**
SQLite 데이터베이스 파일 경로.
기본값: `noosphere.db`

**`SOURCES_DB_PATH`**
소스/캐시 SQLite 데이터베이스 경로.
기본값: `noosphere_sources.db`

---

### 작업 설정

**`MAX_JOBS`** — 동시 실행 가능한 시뮬레이션 최대 수. 기본값: `5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — 큐에 대기 중인 시뮬레이션의 타임아웃. 기본값: `900` (15분)
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — 중단된 시뮬레이션 감지 주기. 기본값: `90`

---

### 레이트 리밋

LLM 제공자의 쿼터를 초과하지 않도록 조절합니다.

**`OPENAI_RPM`** — OpenAI 분당 요청 수. 기본값: `500`
**`OPENAI_RPM_SAFETY`** — 안전 여유 배수 (0–1). 기본값: `0.80`
**`OPENAI_TPM`** — OpenAI 분당 토큰 수. 기본값: `100000`
**`ANTHROPIC_TPM`** — Anthropic 분당 토큰 수. 기본값: `40000`
**`GEMINI_TPM`** — Gemini 분당 토큰 수. 기본값: `250000`

각 제공자 대시보드에서 실제 한도를 확인하고 조정하세요.

---

### 프론트엔드

**`VITE_API_URL`** *(`frontend/.env`에 설정)*
백엔드 API 기본 URL. 기본값: `http://localhost:8000`
백엔드가 다른 호스트나 포트에서 실행 중이라면 설정하세요.

---

## 설치

### 방법 A: Docker Compose (권장)

```bash
git clone https://github.com/your-username/noosphere.git
cd noosphere
cp .env.example .env
# .env에 API 키 입력

docker-compose up --build
```

서비스:
- 프론트엔드: http://localhost:5173
- 백엔드 API: http://localhost:8000
- Redis: localhost:6379

### 방법 B: 로컬 개발

**백엔드**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 별도 터미널에서
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**프론트엔드**

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173 에서 실행됩니다
```

---

## 실행 방법

1. 브라우저에서 http://localhost:5173 접속
2. 홈 페이지에서 제품 설명 입력
3. 시뮬레이션 라운드 수와 대상 플랫폼 선택
4. 실시간으로 시뮬레이션 진행 상황 확인
5. 구조화된 보고서 확인 및 PDF 내보내기
6. 히스토리 페이지에서 이전 시뮬레이션 조회

---

## API 레퍼런스

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| POST | `/simulate` | 새 시뮬레이션 시작 |
| GET | `/simulate-stream/{id}` | 실시간 진행 SSE 스트림 |
| GET | `/results/{id}` | 완료된 결과 조회 |
| GET | `/history` | 전체 시뮬레이션 목록 |
| GET | `/export/{id}` | PDF 보고서 다운로드 |
| POST | `/simulate/{id}/cancel` | 실행 중인 시뮬레이션 취소 |
| POST | `/simulate/{id}/resume` | 일시 정지된 시뮬레이션 재개 |
| DELETE | `/simulate/{id}` | 시뮬레이션 삭제 |
| GET | `/simulate/{id}/status` | 시뮬레이션 상태 확인 |
