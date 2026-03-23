# Noosphere

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · [中文（简体）](./README.zh-CN.md) · **[中文（繁體）](./README.zh-TW.md)** · [Español](./README.es.md) · [Français](./README.fr.md) · [Deutsch](./README.de.md) · [Português](./README.pt.md)

</div>

---

> **AI 驅動的產品驗證模擬器** — 在發布前模擬真實社群對你產品創意的反應。

Noosphere 在 Hacker News、Product Hunt、Reddit、LinkedIn、IndieHackers 等平台上生成多樣化的角色，並透過 LLM 進行多輪討論，提煉批評意見、情感傾向與改進建議。

---

## 目錄

- [概述](#概述)
- [主要功能](#主要功能)
- [技術棧](#技術棧)
- [前置條件](#前置條件)
- [環境變數](#環境變數)
- [安裝](#安裝)
- [執行方式](#執行方式)
- [API 參考](#api-參考)

---

## 概述

描述你的產品，Noosphere 會在多個社交平台上生成數百個 AI 角色（開發者、投資人、懷疑者、早期用戶等）並進行逼真的討論。模擬結果以結構化報告呈現，包含：

- 按平台劃分的情感分析
- 匯聚重複主題的批評聚類
- 基於社群回饋的改進建議
- 由 Typst 生成的 PDF 匯出

---

## 主要功能

- 多平台模擬：Hacker News、Product Hunt、Reddit Startups、LinkedIn、IndieHackers
- 多 LLM 支援：Anthropic Claude、OpenAI GPT、Google Gemini
- 基於 Server-Sent Events (SSE) 的即時串流
- 基於檢查點的可恢復模擬
- 從輸入文字提取知識圖譜 / 本體
- PDF 報告匯出
- 完整的模擬歷史記錄
- 基於 Docker 的部署

---

## 技術棧

**後端**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis（非同步任務佇列）
- SQLite（資料持久化）
- Anthropic、OpenAI、Google Generative AI SDK
- Typst（PDF 生成）

**前端**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**基礎設施**
- Docker + Docker Compose
- Redis 7

---

## 前置條件

- Docker & Docker Compose（推薦），**或** Python 3.11+ 與 Node.js 20+
- Redis（不使用 Docker 本地執行時）
- 至少一個 LLM API 金鑰：Anthropic、OpenAI 或 Google Gemini

---

## 環境變數

複製範本並填入金鑰：

```bash
cp .env.example .env
```

### LLM API 金鑰（至少需要一個）

**`ANTHROPIC_API_KEY`**
Anthropic 的 Claude API 金鑰。
- 註冊：https://console.anthropic.com
- 前往 **API Keys** → **Create Key** 建立
- 用作角色生成和討論輪次的主要 LLM 提供商。

**`OPENAI_API_KEY`**
OpenAI API 金鑰。
- 註冊：https://platform.openai.com
- 前往 **API keys** → **Create new secret key** 建立
- 用作備用/回退 LLM 提供商。

**`GEMINI_API_KEY`**
Google Gemini API 金鑰。
- 取得金鑰：https://aistudio.google.com/app/apikey
- 用作備用/回退 LLM 提供商。

---

### 資料來源 API 金鑰（選用 — 豐富模擬上下文）

**`SERPER_API_KEY`**
透過 Serper.dev 的 Google Search API，支援網頁搜尋以獲取真實上下文。
- 註冊：https://serper.dev
- 免費版：每月 2,500 次查詢
- 在 **Dashboard** 中查看並複製 API 金鑰

**`PRODUCT_HUNT_API_KEY`**
用於獲取熱門產品和社群資料的 Product Hunt API。
- 申請：https://api.producthunt.com/v2/docs
- **Developer Settings** → 建立應用程式 → 複製 API Token

**`SEMANTIC_SCHOLAR_API_KEY`**
用於獲取研究論文上下文的 Semantic Scholar Academic API。
- 申請存取：https://www.semanticscholar.org/product/api
- 提供免費版；無金鑰也可執行，但有金鑰後速率限制更寬鬆。

**`GITHUB_TOKEN`**
用於獲取儲存庫資料的 GitHub Personal Access Token。
- 產生：https://github.com/settings/tokens
- **Generate new token (classic)** → 選擇 `public_repo` 權限 → 產生

---

### 基礎設施

**`REDIS_URL`**
Redis 連線 URL（Celery Broker）。
預設：`redis://localhost:6379/0`
Docker Compose 時改為：`redis://redis:6379/0`

**`DB_PATH`** — SQLite 資料庫路徑。預設：`noosphere.db`
**`SOURCES_DB_PATH`** — 來源快取資料庫路徑。預設：`noosphere_sources.db`

---

### 工作設定

**`MAX_JOBS`** — 最大並發模擬數。預設：`5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — 佇列超時時間。預設：`900`（15 分鐘）
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — 心跳偵測間隔。預設：`90`

---

### 速率限制

**`OPENAI_RPM`** — OpenAI 每分鐘請求數。預設：`500`
**`OPENAI_RPM_SAFETY`** — 安全余量係數 (0–1)。預設：`0.80`
**`OPENAI_TPM`** — OpenAI 每分鐘 Token 數。預設：`100000`
**`ANTHROPIC_TPM`** — Anthropic 每分鐘 Token 數。預設：`40000`
**`GEMINI_TPM`** — Gemini 每分鐘 Token 數。預設：`250000`

請依據各提供商控制台中的實際上限進行調整。

---

### 前端

**`VITE_API_URL`** *（在 `frontend/.env` 中設定）*
後端 API 基礎 URL。預設：`http://localhost:8000`

---

## 安裝

### 方式 A：Docker Compose（推薦）

```bash
git clone https://github.com/your-username/noosphere.git
cd noosphere
cp .env.example .env
# 在 .env 中填入 API 金鑰

docker-compose up --build
```

服務位址：
- 前端：http://localhost:5173
- 後端 API：http://localhost:8000
- Redis：localhost:6379

### 方式 B：本地開發

**後端**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 另開終端機
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

---

## 執行方式

1. 開啟瀏覽器前往 http://localhost:5173
2. 在首頁輸入產品描述
3. 選擇模擬輪次數與目標平台
4. 即時查看模擬進度
5. 查看結構化報告並匯出 PDF
6. 在歷史頁面查看過去的模擬記錄

---

## API 參考

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/simulate` | 啟動新模擬 |
| GET | `/simulate-stream/{id}` | 即時進度 SSE 串流 |
| GET | `/results/{id}` | 取得完成的結果 |
| GET | `/history` | 列出所有模擬 |
| GET | `/export/{id}` | 下載 PDF 報告 |
| POST | `/simulate/{id}/cancel` | 取消執行中的模擬 |
| POST | `/simulate/{id}/resume` | 恢復暫停的模擬 |
| DELETE | `/simulate/{id}` | 刪除模擬 |
| GET | `/simulate/{id}/status` | 查看模擬狀態 |
