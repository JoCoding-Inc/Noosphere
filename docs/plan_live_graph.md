# 라이브 Knowledge Graph 및 레이아웃 너비 확장 계획

## 배경

현재 흐름:
1. 소스 전체 수집 → `_enrich_context_nodes` 일괄 실행 → `sim_graph` 이벤트 1회 발행
2. 프론트: `sim_graph` 수신 후 2컬럼 전환, 그래프 한 번에 표시

목표 흐름:
1. 소스 수집 시작 즉시 2컬럼 (왼쪽 그래프, 오른쪽 소스 타임라인)
2. 각 문서 구조화 완료 시마다 `sim_graph_node` + `sim_graph_edges` 이벤트 발행
3. 프론트: 노드 하나씩 그래프에 추가되며 실시간으로 그려짐
4. 전체 너비 확장

---

## 변경 파일 및 작업 내용

### 1. `backend/tasks.py`

#### 1-1. `_enrich_context_nodes` 시그니처 변경

기존: `async def _enrich_context_nodes(raw_items, provider) -> list[dict]`

변경: publish 콜백을 받아 각 노드 완료 시마다 이벤트를 발행하도록 수정

```python
async def _enrich_context_nodes(
    raw_items: list[dict],
    provider: str,
    on_node_done: Callable[[dict, list[dict]], None] | None = None,
) -> list[dict]:
```

내부 로직:
- `asyncio.Semaphore(10)` 유지
- 각 `_structurize_node` 완료 시 `on_node_done(new_node, already_enriched_nodes)` 호출
- `already_enriched_nodes`는 이미 완료된 노드 목록 (thread-safe list로 관리)

#### 1-2. `_run()` 메인 흐름 수정

`on_node_done` 콜백에서:

```python
def on_node_done(node: dict, existing_nodes: list[dict]) -> None:
    # 새 노드 이벤트
    publish({
        "type": "sim_graph_node",
        "node": {
            "id": node["id"],
            "title": node.get("title", ""),
            "source": node.get("source", ""),
            "url": node.get("url", ""),
        },
    })
    # 기존 노드들과의 새 엣지 계산 후 발행
    new_edges = _calc_edges_for_node(node, existing_nodes)
    if new_edges:
        publish({"type": "sim_graph_edges", "edges": new_edges})
```

#### 1-3. `_calc_edges_for_node` 함수 추가

`_build_structured_edges`의 로직을 단일 노드 기준으로 분리한 헬퍼.
새 노드 1개와 기존 노드 목록 간의 엣지만 계산.

#### 1-4. `sim_graph` 이벤트 제거

기존 일괄 `publish({"type": "sim_graph", ...})` 제거.

#### 1-5. 체크포인트 복원 경로 처리

복원 시 `context_nodes`가 이미 있으므로 LLM 재호출 없이
저장된 노드를 순서대로 `sim_graph_node` + `sim_graph_edges` emit:

```python
if existing_checkpoint:
    enriched_so_far = []
    for node in context_nodes:
        publish({"type": "sim_graph_node", "node": {...}})
        new_edges = _calc_edges_for_node(node, enriched_so_far)
        if new_edges:
            publish({"type": "sim_graph_edges", "edges": new_edges})
        enriched_so_far.append(node)
```

---

### 2. `frontend/src/types.ts`

새 이벤트 타입 추가:

```typescript
export interface ContextGraphNode {
  id: string
  title: string
  source: string
  url: string
}

export interface ContextGraphEdge {
  source: string
  target: string
  weight: number
  label: string
}
```

(이미 존재하면 스킵)

---

### 3. `frontend/src/hooks/useSimulation.ts`

#### 3-1. SimEvent union 변경

제거:
```typescript
| { type: 'sim_graph'; data: ContextGraphData }
```

추가:
```typescript
| { type: 'sim_graph_node'; node: ContextGraphNode }
| { type: 'sim_graph_edges'; edges: ContextGraphEdge[] }
```

#### 3-2. `graphData` 초기화 시점 변경

기존: `graphData: null` → `sim_graph` 수신 시 설정

변경:
- `sim_source_item` 첫 수신 시 (또는 `isSourcing` true 시) 빈 그래프로 초기화
- `sim_graph_node`: 노드 추가
- `sim_graph_edges`: 엣지 추가

```typescript
} else if (event.type === 'sim_graph_node') {
  next.graphData = {
    nodes: [...(prev.graphData?.nodes ?? []), event.node],
    edges: prev.graphData?.edges ?? [],
  }
} else if (event.type === 'sim_graph_edges') {
  next.graphData = {
    nodes: prev.graphData?.nodes ?? [],
    edges: [...(prev.graphData?.edges ?? []), ...event.edges],
  }
}
```

---

### 4. `frontend/src/pages/SimulatePage.tsx`

#### 4-1. 2컬럼 전환 조건 변경

기존: `sim.graphData` 존재 시 2컬럼

변경: `sim.isSourcing || sim.graphData` 조건으로 수정
→ 소스 수집 시작 즉시 2컬럼 레이아웃 표시

#### 4-2. 너비 확장

| 항목 | 현재 | 변경 |
|------|------|------|
| 2컬럼 maxWidth | 1280 | 1600 |
| 1컬럼 maxWidth | 720 | 900 |
| 그래프 패널 width | 420 | 520 |
| ContextGraph width prop | 420 | 520 |

#### 4-3. 그래프 패널 위치

기존: 시뮬레이션 피드 옆에 표시

변경:
- 소싱 단계: 왼쪽 그래프 + 오른쪽 소스 타임라인
- 시뮬레이션 단계: 왼쪽 그래프 (완성된 상태 유지) + 오른쪽 시뮬 피드

---

### 5. `frontend/src/pages/ResultPage.tsx`

너비 확장:
- maxWidth: 900 → 1280

---

### 6. `frontend/src/pages/HomePage.tsx`

너비 확장:
- maxWidth: 760 → 900

---

### 7. `frontend/src/components/LandingDemoWindow.tsx`

데모 시퀀스 수정:
- 소스 수집 시작 즉시 빈 그래프 패널 표시 (`graphData: { nodes: [], edges: [] }`)
- 소스 하나씩 추가될 때마다 노드도 하나씩 추가 (MOCK_GRAPH_DATA 노드를 순서대로)
- 새 노드 추가 시 엣지도 누적

---

## 변경 없는 파일

- `backend/simulation/` 전체
- `backend/ontology_builder.py`
- `frontend/src/components/OntologyGraph.tsx` (ContextGraph 컴포넌트 그대로)

---

## 구현 순서

1. `backend/tasks.py` — `_calc_edges_for_node`, `_enrich_context_nodes` 수정, 이벤트 변경
2. `frontend/src/hooks/useSimulation.ts` — 새 이벤트 처리
3. `frontend/src/pages/SimulatePage.tsx` — 레이아웃 조건 + 너비 변경
4. `frontend/src/pages/ResultPage.tsx`, `HomePage.tsx` — 너비 변경
5. `frontend/src/components/LandingDemoWindow.tsx` — 데모 시퀀스 수정
