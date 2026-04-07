<div align="center">

<img src="../assets/banner.svg" alt="Noosphere" width="100%"/>

</div>

<div align="center">

[English](../README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · **[中文（简体）](./README.zh-CN.md)** · [中文（繁體）](./README.zh-TW.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Deutsch](./README.de.md) · [Português](./README.pt.md)

</div>

---

> **AI 驱动的产品验证模拟器** — 在发布前模拟真实社区对你产品创意的反应。

Noosphere 在 Hacker News、Product Hunt、Reddit、LinkedIn、IndieHackers 等平台上生成多样化的角色，并通过 LLM 进行多轮讨论，提炼批评意见、情感倾向与改进建议。

---

## 目录

- [概述](#概述)
- [主要功能](#主要功能)
- [技术栈](#技术栈)
- [前置条件](#前置条件)
- [环境变量](#环境变量)
- [安装](#安装)
- [运行方式](#运行方式)
- [API 参考](#api-参考)

---

## 概述

描述你的产品，Noosphere 会在多个社交平台上生成数百个 AI 角色（开发者、投资人、怀疑者、早期用户等）并进行逼真的讨论。模拟结果以结构化报告呈现，包含：

- 按平台划分的情感分析
- 汇聚重复主题的批评聚类
- 基于社区反馈的改进建议
- 由 Typst 生成的 PDF 导出

---

## 主要功能

- 多平台模拟：Hacker News、Product Hunt、Reddit Startups、LinkedIn、IndieHackers
- OpenAI GPT 集成
- 基于 Server-Sent Events (SSE) 的实时流式传输
- 基于检查点的可恢复模拟
- 从输入文本提取知识图谱 / 本体
- PDF 报告导出
- 完整的模拟历史记录
- 移动端响应式 UI
- 基于 Docker 的部署

---

## 技术栈

**后端**
- Python 3.11+, FastAPI, uvicorn
- Celery + Redis（异步任务队列）
- SQLite（数据持久化）
- OpenAI SDK
- Typst（PDF 生成）

**前端**
- React 18, TypeScript, Vite
- React Router DOM, react-force-graph-2d, react-markdown

**基础设施**
- Docker + Docker Compose
- Redis 7

---

## 前置条件

- Docker & Docker Compose（推荐），**或** Python 3.11+ 与 Node.js 20+
- Redis（不使用 Docker 本地运行时）
- 需要 OpenAI API 密钥

---

## 环境变量

复制模板并填入密钥：

```bash
cp .env.example .env
```

### LLM API 密钥（必填）

**`OPENAI_API_KEY`**
OpenAI API 密钥。
- 注册：https://platform.openai.com
- 前往 **API keys** → **Create new secret key** 创建

---

### 数据源 API 密钥（可选 — 丰富模拟上下文）

**`SERPER_API_KEY`**
通过 Serper.dev 的 Google Search API，支持网页搜索以获取真实上下文。
- 注册：https://serper.dev
- 免费版：每月 2,500 次查询
- 在 **Dashboard** 中查看并复制 API 密钥

**`PRODUCT_HUNT_API_KEY`**
用于获取热门产品和社区数据的 Product Hunt API。
- 申请：https://api.producthunt.com/v2/docs
- **Developer Settings** → 创建应用 → 复制 API Token

**`SEMANTIC_SCHOLAR_API_KEY`**
用于获取研究论文上下文的 Semantic Scholar Academic API。
- 申请访问：https://www.semanticscholar.org/product/api
- 提供免费版；无密钥也可运行，但有密钥后速率限制更宽松。

**`GITHUB_TOKEN`**
用于获取仓库数据的 GitHub Personal Access Token。
- 生成：https://github.com/settings/tokens
- **Generate new token (classic)** → 选择 `public_repo` 权限 → 生成

---

### 基础设施

**`REDIS_URL`**
Redis 连接 URL（Celery Broker）。
默认：`redis://localhost:6379/0`
Docker Compose 时改为：`redis://redis:6379/0`

**`DB_PATH`** — SQLite 数据库文件路径。默认：`noosphere.db`
**`SOURCES_DB_PATH`** — 数据源/缓存数据库路径。默认：`noosphere_sources.db`

---

### 任务设置

**`MAX_JOBS`** — 最大并发模拟任务数。默认：`5`
**`SIM_QUEUE_TIMEOUT_SECONDS`** — 队列中模拟任务的超时时间。默认：`900`（15 分钟）
**`SIM_HEARTBEAT_TIMEOUT_SECONDS`** — 检测卡死模拟的心跳间隔。默认：`90`

---

### 速率限制

**`OPENAI_RPM`** — OpenAI 每分钟请求数。默认：`500`
**`OPENAI_RPM_SAFETY`** — 安全余量系数 (0–1)。默认：`0.80`
**`OPENAI_TPM`** — OpenAI 每分钟 Token 数。默认：`100000`

请在 OpenAI 控制台确认实际限额后进行调整。

---

### 前端

**`VITE_API_URL`** *（在 `frontend/.env` 中设置）*
后端 API 基础 URL。默认：`http://localhost:8000`

---

## 安装

### 方式 A：Docker Compose（推荐）

```bash
git clone https://github.com/JoCoding-Inc/Noosphere.git
cd Noosphere
cp .env.example .env
# 在 .env 中填入 API 密钥

docker-compose up --build
```

服务地址：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- Redis：localhost:6379

### 方式 B：本地开发

**后端**

```bash
pip install -e ".[dev]"

redis-server

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 另开终端
celery -A backend.celery_app worker --loglevel=info --concurrency=2
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

---

## 运行方式

1. 在浏览器中打开 http://localhost:5173
2. 在首页输入产品描述
3. 选择模拟轮次数、目标平台和 LLM 提供商
4. 实时查看模拟进度
5. 查看结构化报告并导出 PDF
6. 在历史页面查看过去的模拟记录

---

## API 参考

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/simulate` | 启动新模拟 |
| GET | `/simulate-stream/{sim_id}` | 实时进度 SSE 流 |
| GET | `/results/{sim_id}` | 获取完成的结果 |
| GET | `/history` | 列出所有模拟 |
| GET | `/export/{sim_id}` | 下载 PDF 报告 |
| POST | `/simulate/{sim_id}/cancel` | 取消运行中的模拟 |
| POST | `/simulate/{sim_id}/resume` | 恢复暂停的模拟 |
| DELETE | `/simulate/{sim_id}` | 删除模拟 |
| GET | `/simulate/{sim_id}/status` | 查看模拟状态 |
