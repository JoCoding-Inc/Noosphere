# 노드 구조화 및 에이전트 사전지식 개선 계획

## 배경

현재 문서 간 연결(`_build_keyword_edges`)은 regex 기반 단어 겹침으로 동작한다.
이는 의미상 관련 없는 문서끼리 연결되거나, 실제로 관련 있어도 표현이 달라서
연결이 안 되는 문제가 있다.

또한 에이전트 사전지식(`_build_prior_knowledge`)은 클러스터 내 문서를
순서대로 top_k개 가져오는 방식으로, 실제 에이전트 특성과 관련성 없는
문서가 주입될 수 있다.

---

## 목표

1. 문서당 LLM 1회 호출로 구조화 JSON 생성 (summary + 고정 taxonomy + 자유형 필드)
2. 고정 taxonomy 기반 가중 엣지 빌딩으로 클러스터링 품질 향상
3. 페르소나에도 동일한 taxonomy 부여 → 에이전트-문서 관련성 정확히 계산

---

## 구조화 JSON 스펙 (문서당 추출)

```json
{
  "summary": "핵심 내용 500자 이내",
  "domain_type": "tech | research | consumer | business | healthcare | general (1개)",
  "tech_area": ["AI/ML | cloud | security | data | mobile | web | hardware | other (1-2개)"],
  "market": ["B2B | B2C | enterprise | developer | consumer | academic (1-2개)"],
  "problem_domain": ["automation | analytics | communication | productivity | infrastructure | security | UX | compliance (1-2개)"],
  "keywords": ["구체적 기술 용어 5-10개 (자유형)"],
  "entities": ["제품/회사/기술 고유명사 (자유형)"]
}
```

`summary`는 기존 `abstract` 필드를 교체한다. downstream 코드 수정 없이 자동 적용.

---

## 엣지 빌딩 가중치

| 필드 | 가중치 |
|------|--------|
| `entities` 겹침 | × 3 |
| `keywords` 겹침 | × 2 |
| `domain_type` 겹침 | × 1 |
| `tech_area` 겹침 | × 1 |
| `market` 겹침 | × 1 |
| `problem_domain` 겹침 | × 1 |

최소 점수 2점 이상인 쌍만 엣지 생성.

structured fields 없는 경우(구 체크포인트 등) → score 0 → 엣지 미생성. regex fallback 없음.

---

## 변경 파일 및 작업 내용

### 1. `backend/tasks.py`

**추가: `_structurize_node(item, provider) -> dict`**
- 문서 1개에 LLM 호출 (`tier="low"`)
- content는 `item.get("text") or item.get("abstract") or ""` 전체 사용 (글자수 제한 없음)
- 실패 시 `summary`는 기존 text/abstract, 나머지 필드는 빈 값으로 fallback

**추가: `_enrich_context_nodes(raw_items, provider) -> list[dict]`**
- `asyncio.Semaphore(10)`으로 동시 호출 수 제한
- 전체 문서 병렬 처리
- context_node에 `abstract`(=summary), `_domain_type`, `_tech_area`, `_market`, `_problem_domain`, `_keywords`, `_entities` 저장

**추가: `_build_structured_edges(nodes) -> list[dict]`**
- 기존 `_build_keyword_edges` 대체
- 위 가중치 기준으로 엣지 생성
- `tech_area`, `market`, `problem_domain`은 list 타입이므로 `set(list_field)` 처리

**수정: `_rank_nodes_by_relevance`**
- `_entities` + `_keywords` 있으면 우선 사용
- 없으면 기존 regex fallback 유지

**수정: 메인 흐름 (`_run()`)**
- 수동 context_nodes 구성 → `await _enrich_context_nodes(raw_items, provider)` 교체
- `publish("Structurizing documents...")` progress 이벤트 추가
- `_build_keyword_edges` → `_build_structured_edges` 교체
- 체크포인트 복원 시(`existing_checkpoint`) enrichment 스킵

---

### 2. `backend/simulation/models.py`

**수정: `Persona` 데이터클래스**
- taxonomy 필드 추가:
  - `domain_type: str = ""`
  - `tech_area: list[str] = field(default_factory=list)`
  - `market: list[str] = field(default_factory=list)`
  - `problem_domain: list[str] = field(default_factory=list)`

---

### 3. `backend/simulation/persona_generator.py`

**수정: `_PERSONA_TOOL`**
- parameters에 taxonomy 필드 4개 추가 (고정 enum 옵션 명시)

**수정: `generate_persona`**
- response에서 taxonomy 필드 파싱 후 `Persona`에 저장

**수정: `_fallback_persona`**
- 새 taxonomy 필드 기본값 추가 (빈 값)

---

### 4. `backend/simulation/social_rounds.py`

**수정: `_build_prior_knowledge(cluster_id, cluster_docs_map, persona, top_k=5)`**
- `persona` 파라미터 추가
- 랭킹 로직:
  - 페르소나의 `domain_type`, `tech_area`, `market`, `problem_domain` vs 문서의 동일 필드 → taxonomy 겹침 점수
  - 점수 높은 순으로 top_k 선택
- `abstract[:200]` 제한 제거 → `abstract` 전체 사용 (이제 summary가 들어옴)

**수정: `generate_content` 호출부 (line 249)**
- `_build_prior_knowledge(persona.node_id, cluster_docs_map)` → `_build_prior_knowledge(persona.node_id, cluster_docs_map, persona)`

---

### 5. `backend/simulation/social_runner.py`

**수정: `_restore_personas`**
- 체크포인트 복원 시 새 taxonomy 필드 (`domain_type`, `tech_area`, `market`, `problem_domain`) 복원 처리 추가

---

## 변경 없는 파일

- `backend/ontology_builder.py`: `abstract` 필드 자동 적용됨
- `backend/simulation/graph_utils.py`
- 테스트 파일: 관련 테스트 없음

---

## 고려사항

- **비용**: 문서당 `tier="low"` 1회 호출. 100문서 기준 추가 비용 발생하나 low tier로 최소화
- **`_STOPWORDS` / `_extract_keywords`**: `_rank_nodes_by_relevance` fallback용으로 유지
