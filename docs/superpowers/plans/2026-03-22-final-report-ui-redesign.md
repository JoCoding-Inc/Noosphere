# Final Report & Result UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백엔드에서 `analysis_md` + `report_json`을 종합한 `final_report_md`를 생성하고, 결과 페이지 탭 구조를 Analysis → Simulation → Final Report → Details로 개편하며, Social Feed에 라운드 기반 페이지네이션을 추가한다.

**Architecture:**
- `reporter.py`에 `generate_final_report()` 함수 추가 — LLM으로 최종 보고서 생성
- DB `sim_results` 테이블에 `final_report_md` 컬럼 추가 (마이그레이션 포함)
- 프론트엔드 탭 4개로 통합: Analysis / Simulation / Final Report / Details (Social Feed + Personas 서브탭)
- Sources는 독립 탭 제거, Analysis 탭 하단 collapsible 섹션으로 이동
- 최상단에 Verdict sticky 요약 카드 추가 (탭 이동해도 항상 노출)
- PDF에 Final Report 섹션 추가

**Tech Stack:** Python/FastAPI, SQLite, React/TypeScript, Typst (PDF)

> ⚠️ **줄 번호 주의:** 계획에 명시된 줄 번호는 근사값이다. 각 단계 실행 전 반드시 해당 파일을 직접 읽어 정확한 삽입/수정 위치를 확인할 것.

---

## File Map

| 작업 | 파일 | 역할 |
|------|------|------|
| Create | `backend/tests/test_final_report.py` | generate_final_report 단위 테스트 |
| Modify | `backend/reporter.py` | generate_final_report() 추가 |
| Modify | `backend/db.py` | final_report_md 컬럼, save/get 업데이트 |
| Modify | `backend/tasks.py` | 최종 보고서 생성 단계 추가 |
| Modify | `backend/exporter.py` | PDF에 Final Report 섹션 추가 |
| Modify | `frontend/src/types.ts` | SimResults에 final_report_md 추가 |
| Modify | `frontend/src/pages/ResultPage.tsx` | 탭 구조 개편 + Verdict 헤더 |
| Create | `frontend/src/components/DetailsView.tsx` | Social Feed + Personas 서브탭 + 페이지네이션 |
| Modify | `frontend/src/components/MarkdownView.tsx` | (필요시) Sources collapsible 지원 확인 |

---

## Task 1: DB — final_report_md 컬럼 추가

**Files:**
- Modify: `backend/db.py`

현재 `sim_results` 테이블에 `final_report_md` 컬럼이 없다. `save_sim_results()`와 `get_sim_results()`도 함께 수정한다.

- [ ] **Step 1: CREATE TABLE 정의에 컬럼 추가**

`backend/db.py` 42~50번 줄 CREATE TABLE 블록에 `final_report_md TEXT NOT NULL DEFAULT ''` 추가:

```python
CREATE TABLE IF NOT EXISTS sim_results (
    sim_id TEXT PRIMARY KEY,
    posts_json TEXT NOT NULL DEFAULT '{}',
    personas_json TEXT NOT NULL DEFAULT '{}',
    report_json TEXT NOT NULL DEFAULT '{}',
    report_md TEXT NOT NULL DEFAULT '',
    analysis_md TEXT NOT NULL DEFAULT '',
    sources_json TEXT NOT NULL DEFAULT '[]',
    final_report_md TEXT NOT NULL DEFAULT ''
);
```

- [ ] **Step 2: 마이그레이션 추가**

기존 `sources_json` 마이그레이션 블록(59~62번 줄) 바로 뒤에 추가:

```python
try:
    conn.execute("ALTER TABLE sim_results ADD COLUMN final_report_md TEXT NOT NULL DEFAULT ''")
    conn.commit()
except Exception:
    pass  # 이미 있으면 무시
```

- [ ] **Step 3: `save_sim_results()` 시그니처 업데이트**

`backend/db.py` 268번 줄 `save_sim_results` 함수:

```python
def save_sim_results(
    path: str | Path,
    sim_id: str,
    posts: dict,
    personas: dict,
    report_json: dict,
    report_md: str,
    analysis_md: str = "",
    raw_items: list[dict] | None = None,
    final_report_md: str = "",          # 추가
) -> None:
    with _conn(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sim_results "
            "(sim_id, posts_json, personas_json, report_json, report_md, analysis_md, sources_json, final_report_md) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (sim_id, json.dumps(posts, ensure_ascii=False), json.dumps(personas, ensure_ascii=False),
             json.dumps(report_json, ensure_ascii=False), report_md, analysis_md,
             json.dumps(raw_items or [], ensure_ascii=False), final_report_md),
        )
```

- [ ] **Step 4: 서버 재시작 후 수동 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -c "from backend.db import init_db; init_db('test_migration.db'); import sqlite3; c=sqlite3.connect('test_migration.db'); print([d[1] for d in c.execute('PRAGMA table_info(sim_results)')]); c.close(); import os; os.remove('test_migration.db')"
```

Expected: 출력에 `final_report_md` 포함됨

- [ ] **Step 5: Commit**

```bash
git add backend/db.py
git commit -m "feat: add final_report_md column to sim_results"
```

---

## Task 2: Backend — generate_final_report() 구현

**Files:**
- Modify: `backend/reporter.py`
- Create: `backend/tests/test_final_report.py`

- [ ] **Step 1: 테스트 파일 작성 (failing)**

`backend/tests/test_final_report.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.reporter import generate_final_report
from backend.llm import LLMResponse

MOCK_ANALYSIS = "## Summary\nThis is a competitive market.\n## Existing Solutions\n- Competitor A\n"
MOCK_REPORT_JSON = {
    "verdict": "mixed",
    "evidence_count": 20,
    "segments": [
        {"name": "early_adopter", "sentiment": "positive", "summary": "Excited about the idea", "key_quotes": ["Love it!"]}
    ],
    "criticism_clusters": [
        {"theme": "Pricing concern", "count": 5, "examples": ["Too expensive"]}
    ],
    "improvements": [
        {"suggestion": "Add free tier", "frequency": 8}
    ],
}

@pytest.mark.asyncio
async def test_generate_final_report_returns_markdown():
    mock_response = LLMResponse(content="# Final Report\n\n## Executive Summary\nThis is promising.", tool_name=None, tool_args=None)
    with patch("backend.reporter.llm.complete", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_final_report(
            analysis_md=MOCK_ANALYSIS,
            report_json=MOCK_REPORT_JSON,
            input_text="AI productivity tool",
            language="English",
            provider="openai",
        )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_final_report_empty_inputs():
    """빈 데이터가 들어와도 fallback 문자열 반환"""
    result = await generate_final_report(
        analysis_md="",
        report_json={},
        input_text="",
        language="English",
        provider="openai",
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_final_report_korean():
    mock_response = LLMResponse(content="# 최종 보고서\n\n## 종합 결론\n유망한 아이디어입니다.", tool_name=None, tool_args=None)
    with patch("backend.reporter.llm.complete", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_final_report(
            analysis_md=MOCK_ANALYSIS,
            report_json=MOCK_REPORT_JSON,
            input_text="AI 생산성 도구",
            language="Korean",
            provider="openai",
        )
    assert "최종" in result or len(result) > 0
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest backend/tests/test_final_report.py -v 2>&1 | head -30
```

Expected: `ImportError` 또는 `AttributeError: module 'backend.reporter' has no attribute 'generate_final_report'`

- [ ] **Step 3: `generate_final_report()` 구현**

`backend/reporter.py` 맨 아래에 추가:

```python
_FINAL_REPORT_SYSTEM = """\
You are a senior product analyst. You are given two inputs:
1. A competitive landscape analysis (from real-world sources)
2. A simulation report (from AI agent reactions to the idea)

Synthesize these into a final executive report with clear, actionable conclusions."""


def _fmt_report_json(report: dict) -> str:
    if not report:
        return "_No simulation data_"
    verdict = report.get("verdict", "unknown")
    evidence = report.get("evidence_count", 0)
    lines = [f"**Verdict:** {verdict} (based on {evidence} interactions)"]
    for seg in report.get("segments", []):
        lines.append(f"- Segment '{seg.get('name','')}': {seg.get('sentiment','')} — {seg.get('summary','')}")
    lines.append("\n**Top Criticisms:**")
    for c in report.get("criticism_clusters", [])[:3]:
        lines.append(f"- {c.get('theme','')} ({c.get('count',0)} mentions)")
    lines.append("\n**Top Improvements:**")
    for imp in report.get("improvements", [])[:3]:
        lines.append(f"- {imp.get('suggestion','')} (×{imp.get('frequency',1)})")
    return "\n".join(lines)


async def generate_final_report(
    analysis_md: str,
    report_json: dict,
    input_text: str,
    language: str = "English",
    provider: str = "openai",
) -> str:
    """
    analysis_md(소스 분석)와 report_json(시뮬레이션 결과)를 종합한
    최종 경영진 보고서를 생성합니다.
    """
    if not analysis_md and not report_json:
        return f"## Final Report\n\n_No data available to generate final report._"

    sim_summary = _fmt_report_json(report_json)

    prompt = f"""Idea: {input_text[:400]}

---
## 1. Competitive Landscape Analysis
{analysis_md[:3000]}

---
## 2. Simulation Results Summary
{sim_summary}

---
Write the final report in this exact structure:
## Executive Summary
## Key Findings
## Risk Assessment
## Strategic Recommendations
## Conclusion

Be direct and actionable. Respond entirely in {language}."""

    response = await llm.complete(
        messages=[
            {"role": "system", "content": _FINAL_REPORT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tier="high",
        provider=provider,
        max_tokens=8192,
    )
    return response.content or f"## Final Report\n\n_Generation failed._"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest backend/tests/test_final_report.py -v
```

Expected: 3개 모두 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/reporter.py backend/tests/test_final_report.py
git commit -m "feat: add generate_final_report() synthesizing analysis + simulation"
```

---

## Task 3: Backend tasks.py — 최종 보고서 생성 단계 통합

**Files:**
- Modify: `backend/tasks.py`

시뮬레이션 파이프라인에서 `report_md` 생성 직후 `generate_final_report()`를 호출하고, `save_sim_results()`에 `final_report_md`를 전달한다.

- [ ] **Step 1: import 추가 및 변수 초기화**

`tasks.py` 상단 `_run()` 함수 내 기존 import 줄 (약 43번 줄):

```python
# 기존
from backend.reporter import generate_analysis_report
# 변경
from backend.reporter import generate_analysis_report, generate_final_report
```

그리고 변수 초기화 블록 (`final_report_md` 추가):

```python
analysis_md = ""
posts_by_platform: dict = {}
personas_by_platform: dict = {}
report_json: dict = {}
report_md: str = ""
final_report_md: str = ""    # 추가
```

- [ ] **Step 2: 최종 보고서 생성 단계 추가**

`tasks.py` 에서 `async for` 루프 종료 직후, `save_sim_results()` 호출 직전에 삽입.
(파일을 먼저 읽어 정확한 삽입 위치를 확인할 것 — 줄 번호는 근사값임):

```python
# tasks.py — save_sim_results() 호출 직전 삽입
publish({"type": "sim_progress", "message": "Generating final report..."})
try:
    final_report_md = await generate_final_report(
        analysis_md=analysis_md,
        report_json=report_json,
        input_text=config["input_text"],
        language=config["language"],
        provider=provider,
    )
    publish({"type": "sim_final_report", "data": {"markdown": final_report_md}})
except Exception as _e:
    logger.warning("Final report generation failed: %s", _e)
    final_report_md = "## Final Report\n\n_Generation failed._"

save_sim_results(
    DB_PATH,
    sim_id,
    posts_by_platform,
    personas_by_platform,
    report_json,
    report_md,
    analysis_md=analysis_md,
    raw_items=raw_items,
    final_report_md=final_report_md,   # 추가
)
```

- [ ] **Step 3: 기존 통합 테스트 통과 확인**

```bash
python -m pytest backend/tests/ -v -k "not integration" 2>&1 | tail -20
```

Expected: 기존 테스트 PASSED, 새 import 오류 없음

- [ ] **Step 4: Commit**

```bash
git add backend/tasks.py
git commit -m "feat: integrate final report generation into simulation pipeline"
```

---

## Task 4: Backend exporter.py — PDF에 Final Report 섹션 추가

**Files:**
- Modify: `backend/exporter.py`

`_build_typst()` 함수에 `final_report_md` 파라미터를 추가하고, PDF 목차 순서를 분석 → 시뮬레이션 → 최종결과 → (부록) 순으로 업데이트한다.

- [ ] **Step 1: `_build_typst()` 시그니처에 final_report_md 추가**

`exporter.py` 297~304번 줄:

```python
def _build_typst(
    domain: str,
    idea_text: str,
    analysis_md: str | None,
    report_md: str,
    language: str = "English",
    sim_params: dict | None = None,
    final_report_md: str | None = None,   # 추가
) -> str:
```

- [ ] **Step 2: final_report 섹션 변수 추가**

함수 내부 `sim_body` 정의 바로 아래에:

```python
final_body = _md_to_typst(final_report_md) if final_report_md else labels.get("no_final_report", "_No final report_")
```

- [ ] **Step 3: Typst 템플릿에 Final Report 섹션 삽입**

`exporter.py` 448~452번 줄 시뮬레이션 섹션 끝 부분 `"""` 닫기 전에 추가:

```typst
#pagebreak()

// ── 최종 보고서 ──────────────────────────────────────────
= {labels["section_final_report"]}

{final_body}
```

- [ ] **Step 4: `_LANG_SETTINGS`에 `section_final_report` / `no_final_report` 레이블 추가**

8개 언어 레이블 딕셔너리 각각에 두 키를 추가한다 (`exporter.py` 150~293번 줄):

```python
# Korean
"section_final_report": "최종 보고서",
"no_final_report": "_최종 보고서 없음_",

# Japanese
"section_final_report": "最終レポート",
"no_final_report": "_最終レポートなし_",

# Chinese
"section_final_report": "最终报告",
"no_final_report": "_无最终报告_",

# Spanish
"section_final_report": "Informe Final",
"no_final_report": "_Sin informe final_",

# French
"section_final_report": "Rapport Final",
"no_final_report": "_Aucun rapport final_",

# German
"section_final_report": "Abschlussbericht",
"no_final_report": "_Kein Abschlussbericht_",

# Portuguese
"section_final_report": "Relatório Final",
"no_final_report": "_Sem relatório final_",

# English
"section_final_report": "Final Report",
"no_final_report": "_No final report_",
```

Step 2 의 `final_body` 변수도 `.get()` 대신 일관된 직접 접근으로 수정:

```python
final_body = _md_to_typst(final_report_md) if final_report_md else labels["no_final_report"]
```

- [ ] **Step 5: `build_pdf()` 함수에 파라미터 전달**

`exporter.py` 455~471번 줄 `build_pdf()`:

```python
async def build_pdf(
    report_md: str,
    input_text: str,
    sim_id: str,
    domain: str = "",
    language: str = "English",
    analysis_md: str | None = None,
    sim_params: dict | None = None,
    final_report_md: str | None = None,   # 추가
) -> bytes:
    typ_content = _build_typst(
        domain=domain or input_text[:60],
        idea_text=input_text,
        analysis_md=analysis_md,
        report_md=report_md,
        language=language,
        sim_params=sim_params,
        final_report_md=final_report_md,  # 추가
    )
```

- [ ] **Step 6: `main.py` export 엔드포인트에 final_report_md 전달**

`main.py` 222~230번 줄 `build_pdf()` 호출:

```python
pdf_bytes = await build_pdf(
    report_md=results["report_md"],
    input_text=sim["input_text"] if sim else "",
    sim_id=sim_id,
    domain=sim["domain"] if sim else "",
    language=sim["language"] if sim else "English",
    analysis_md=results.get("analysis_md"),
    sim_params=sim_params,
    final_report_md=results.get("final_report_md"),  # 추가
)
```

- [ ] **Step 7: Commit**

```bash
git add backend/exporter.py backend/main.py
git commit -m "feat: add Final Report section to PDF export"
```

---

## Task 5: Frontend types.ts — SimResults 타입 업데이트

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: `SimResults` 인터페이스에 필드 추가**

`types.ts` 80~88번 줄:

```typescript
export interface SimResults {
  sim_id: string
  posts_json: Partial<Record<Platform, SocialPost[]>>
  personas_json: Partial<Record<Platform, Persona[]>>
  report_json: ReportJSON
  report_md: string
  analysis_md: string
  sources_json: SourceItem[]
  final_report_md: string   // 추가
}
```

- [ ] **Step 2: TypeScript 빌드 오류 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add final_report_md to SimResults type"
```

---

## Task 6: Frontend — DetailsView 컴포넌트 생성

**Files:**
- Create: `frontend/src/components/DetailsView.tsx`

Social Feed와 Personas를 하나의 컴포넌트로 합치고, Social Feed에 라운드(round_num) 기반 페이지네이션을 추가한다.

- [ ] **Step 1: DetailsView 컴포넌트 작성**

`frontend/src/components/DetailsView.tsx`:

```tsx
import { useState } from 'react'
import type { Platform, SocialPost, Persona } from '../types'
import { PlatformSimFeed } from './PlatformSimFeed'
import { PersonaCardView } from './PersonaCardView'

type DetailTab = 'feed' | 'personas'

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  personas: Partial<Record<Platform, Persona[]>>
}

export function DetailsView({ posts, personas }: Props) {
  const [tab, setTab] = useState<DetailTab>('feed')

  // 전체 포스트에서 존재하는 라운드 목록 추출
  const allPosts = Object.values(posts).flat() as SocialPost[]
  const rounds = [...new Set(allPosts.map(p => p.round_num))].sort((a, b) => a - b)
  const [activeRound, setActiveRound] = useState<number | null>(rounds[0] ?? null)

  // 선택한 라운드 포스트만 필터링
  const filteredPosts: Partial<Record<Platform, SocialPost[]>> = activeRound === null
    ? posts
    : Object.fromEntries(
        Object.entries(posts).map(([platform, platformPosts]) => [
          platform,
          (platformPosts ?? []).filter(p => p.round_num === activeRound),
        ])
      ) as Partial<Record<Platform, SocialPost[]>>

  const tabs: { id: DetailTab; label: string }[] = [
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
  ]

  return (
    <div>
      {/* 서브탭 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #e2e8f0' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', fontSize: 13, cursor: 'pointer', border: 'none',
              background: 'none', fontWeight: tab === t.id ? 600 : 400,
              borderBottom: tab === t.id ? '2px solid #475569' : '2px solid transparent',
              color: tab === t.id ? '#1e293b' : '#94a3b8',
              transition: 'color 0.15s, border-color 0.15s',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 라운드 페이지네이션 — Social Feed에서만 표시 */}
      {tab === 'feed' && rounds.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>Round</span>
          {rounds.map(r => (
            <button key={r} onClick={() => setActiveRound(r)}
              style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none',
                background: activeRound === r ? '#1e293b' : '#f1f5f9',
                color: activeRound === r ? '#fff' : '#64748b',
                fontWeight: activeRound === r ? 700 : 400,
                fontSize: 13, cursor: 'pointer',
                transition: 'all 0.15s',
              }}>
              {r}
            </button>
          ))}
          <button onClick={() => setActiveRound(null)}
            style={{
              padding: '4px 10px', borderRadius: 6, border: '1px solid #e2e8f0',
              background: activeRound === null ? '#1e293b' : '#fff',
              color: activeRound === null ? '#fff' : '#64748b',
              fontSize: 12, cursor: 'pointer',
            }}>
            All
          </button>
        </div>
      )}

      <div key={tab} className="tab-content">
        {tab === 'feed' && <PlatformSimFeed postsByPlatform={filteredPosts} />}
        {tab === 'personas' && <PersonaCardView personas={personas} />}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript 오류 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DetailsView.tsx
git commit -m "feat: add DetailsView with Social Feed/Personas sub-tabs and round pagination"
```

---

## Task 7: Frontend ResultPage.tsx — 탭 구조 개편 및 Verdict 헤더 추가

**Files:**
- Modify: `frontend/src/pages/ResultPage.tsx`

탭 순서를 Analysis → Simulation → Final Report → Details로 개편하고, 탭 위에 Verdict 요약 카드를 고정한다. Sources는 Analysis 탭 하단에 collapsible로 이동한다.

- [ ] **Step 1: ResultPage.tsx 전체 교체**

`frontend/src/pages/ResultPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { ReportView } from '../components/ReportView'
import { DetailsView } from '../components/DetailsView'
import { MarkdownView } from '../components/MarkdownView'
import { SourcesView } from '../components/SourcesView'
import { getResults } from '../api'
import type { SimResults } from '../types'

type Tab = 'analysis' | 'simulation' | 'final' | 'details'

const VERDICT_CONFIG = {
  positive: { color: '#22c55e', label: 'Positive', emoji: '✅' },
  mixed:    { color: '#f59e0b', label: 'Mixed',    emoji: '⚖️' },
  skeptical:{ color: '#f97316', label: 'Skeptical',emoji: '🤔' },
  negative: { color: '#ef4444', label: 'Negative', emoji: '❌' },
}

export function ResultPage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<SimResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('analysis')
  const [sourcesOpen, setSourcesOpen] = useState(false)

  useEffect(() => {
    if (!simId) return
    getResults(simId)
      .then(setResults)
      .catch(e => setError(e instanceof Error ? e.message : 'Unknown error'))
      .finally(() => setLoading(false))
  }, [simId])

  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

  const tabs: { id: Tab; label: string }[] = [
    { id: 'analysis',   label: 'Analysis' },
    { id: 'simulation', label: 'Simulation' },
    { id: 'final',      label: 'Final Report' },
    { id: 'details',    label: 'Details' },
  ]

  const verdict = results?.report_json?.verdict
  const v = verdict ? (VERDICT_CONFIG[verdict] || VERDICT_CONFIG.mixed) : null

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <button onClick={() => navigate('/')}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14 }}>
            ← New simulation
          </button>
        </div>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#64748b', fontSize: 14 }}>
            <span className="spinner" style={{ borderColor: 'rgba(100,116,139,0.3)', borderTopColor: '#64748b' }} />
            Loading results...
          </div>
        )}
        {error && <p style={{ color: '#ef4444' }}>{error}</p>}

        {results && (
          <>
            {/* Verdict 요약 카드 — 항상 노출 */}
            {v && (
              <div style={{
                padding: '12px 18px', borderRadius: 10, marginBottom: 20,
                border: `1px solid ${v.color}30`, background: `${v.color}08`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 20 }}>{v.emoji}</span>
                  <span style={{ fontSize: 16, fontWeight: 700, color: v.color }}>{v.label}</span>
                  <span style={{ fontSize: 13, color: '#94a3b8' }}>
                    · {results.report_json?.evidence_count ?? 0} interactions simulated
                  </span>
                </div>
                <a
                  href={`${API_BASE}/export/${simId}`}
                  download
                  style={{
                    display: 'inline-block', padding: '6px 14px', background: '#1e293b',
                    color: '#fff', borderRadius: 7, textDecoration: 'none', fontSize: 12,
                    fontWeight: 600,
                  }}>
                  ↓ PDF
                </a>
              </div>
            )}

            {/* 탭 네비게이션 */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
              {tabs.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  style={{
                    padding: '10px 20px', fontSize: 14, cursor: 'pointer', border: 'none',
                    background: 'none', fontWeight: tab === t.id ? 600 : 400,
                    borderBottom: tab === t.id ? '2px solid #1e293b' : '2px solid transparent',
                    color: tab === t.id ? '#1e293b' : '#64748b',
                    transition: 'color 0.15s, border-color 0.15s',
                  }}>
                  {t.label}
                </button>
              ))}
            </div>

            <div key={tab} className="tab-content">
              {tab === 'analysis' && (
                <div>
                  <MarkdownView content={results.analysis_md} />
                  {/* Sources collapsible */}
                  <div style={{ marginTop: 32 }}>
                    <button
                      onClick={() => setSourcesOpen(o => !o)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        background: 'none', border: '1px solid #e2e8f0', borderRadius: 7,
                        padding: '7px 14px', fontSize: 13, color: '#64748b', cursor: 'pointer',
                      }}>
                      {sourcesOpen ? '▾' : '▸'} Sources ({results.sources_json?.length ?? 0})
                    </button>
                    {sourcesOpen && (
                      <div style={{ marginTop: 12 }}>
                        <SourcesView sources={results.sources_json ?? []} />
                      </div>
                    )}
                  </div>
                </div>
              )}
              {tab === 'simulation' && (
                <ReportView report={results.report_json} simId={simId!} />
              )}
              {tab === 'final' && (
                <MarkdownView content={results.final_report_md || '_Final report not yet available._'} />
              )}
              {tab === 'details' && (
                <DetailsView
                  posts={results.posts_json}
                  personas={results.personas_json}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 오류 없음

- [ ] **Step 3: 개발 서버에서 시각적 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npm run dev
```

브라우저에서 기존 결과 URL 열어 확인:
- Verdict 카드가 탭 위에 고정 노출되는지
- Analysis 탭 하단 Sources 토글 동작하는지
- Final Report 탭에서 `_Final report not yet available._` 표시 (기존 데이터는 없으므로)
- Details 탭에서 Social Feed / Personas 서브탭 전환 동작하는지
- 라운드가 여러 개인 경우 라운드 페이지네이션 버튼 노출되는지

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ResultPage.tsx
git commit -m "feat: redesign result page tabs with verdict header and Final Report tab"
```

---

## 최종 검증 체크리스트

- [ ] 새 시뮬레이션 실행 시 `final_report_md`가 DB에 저장되는지 확인
- [ ] `/results/{sim_id}` API 응답에 `final_report_md` 필드 포함 확인
- [ ] PDF 다운로드 시 "Final Report" 섹션이 목차와 본문에 포함되는지 확인
- [ ] 기존 시뮬레이션 결과 (final_report_md 없는 구버전)에서 "not yet available" 안내 문구 표시 확인
- [ ] 라운드가 1개인 경우 페이지네이션 버튼 미표시 확인
