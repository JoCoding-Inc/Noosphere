# Persona Diversity & Simulation Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 소셜 시뮬레이션 페르소나의 역할/MBTI 다양성을 높이고, 동일 플랫폼 내 이름 중복을 제거하며, 라운드 간 동일 에이전트 반복 등장을 억제한다.

**Architecture:** 세 가지 독립적 수정으로 구성. Fix 1은 프롬프트 텍스트만 변경, Fix 2는 social_runner.py의 수집 단계에서 사후 중복 제거, Fix 3은 PlatformState에 발언 이력을 추가하고 선택 가중치를 조정.

**Tech Stack:** Python asyncio, dataclasses, unittest.mock, pytest-asyncio

---

## File Map

| 파일 | 변경 유형 | 역할 |
|------|-----------|------|
| `backend/simulation/persona_generator.py` | Modify | Fix 1: 프롬프트 재작성 + fallback 개선 |
| `backend/simulation/social_runner.py` | Modify | Fix 2: 이름 중복 제거 로직 추가 |
| `backend/simulation/models.py` | Modify | Fix 3: PlatformState.recent_speakers 추가 |
| `backend/simulation/social_rounds.py` | Modify | Fix 3: select_active_agents cooldown, platform_round 기록 |
| `tests/test_persona_generator.py` | Modify | Fix 1 테스트 추가 |
| `tests/test_social_runner.py` | Modify | Fix 2 테스트 추가 |
| `tests/test_social_rounds.py` | Modify | Fix 3 테스트 추가 |

---

## Task 1: Fix 1 — Persona Role & MBTI Diversity (프롬프트 재작성)

**Files:**
- Modify: `backend/simulation/persona_generator.py`
- Test: `tests/test_persona_generator.py`

---

- [ ] **Step 1: 테스트 먼저 작성 — MBTI 다양성 지시 포함 여부**

`tests/test_persona_generator.py` 끝에 추가:

```python
@pytest.mark.asyncio
async def test_generate_persona_prompt_includes_mbti_diversity_instruction():
    """_SYSTEM_TMPL should instruct LLM not to default to INTJ."""
    from backend.simulation.persona_generator import _SYSTEM_TMPL
    formatted = _SYSTEM_TMPL.format(platform_context="test context")
    assert "INTJ" in formatted, "MBTI diversity instruction should mention INTJ to avoid it"
    assert "Do NOT" in formatted or "do not" in formatted or "Avoid" in formatted


@pytest.mark.asyncio
async def test_hackernews_audience_includes_non_engineer_archetypes():
    """HN platform audience should list diverse archetypes beyond software engineers."""
    from backend.simulation.persona_generator import _PLATFORM_AUDIENCE
    hn = _PLATFORM_AUDIENCE["hackernews"]
    assert "indie hacker" in hn.lower() or "indie" in hn.lower()
    assert "founder" in hn.lower()
    assert "marketer" in hn.lower() or "marketing" in hn.lower()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_persona_generator.py::test_generate_persona_prompt_includes_mbti_diversity_instruction tests/test_persona_generator.py::test_hackernews_audience_includes_non_engineer_archetypes -v
```

Expected: FAIL (현재 프롬프트에 해당 텍스트 없음)

- [ ] **Step 3: `_PLATFORM_AUDIENCE` 전면 재작성**

`backend/simulation/persona_generator.py`에서 `_PLATFORM_AUDIENCE` dict를 아래로 교체:

```python
_PLATFORM_AUDIENCE = {
    "hackernews": (
        "Hacker News — community of curious, technically-literate people. "
        "Pick ONE of these archetypes at random (do not default to engineer): "
        "software engineer, indie hacker (solo product builder), "
        "seed-stage VC analyst, non-technical founder, "
        "marketer at a dev-tool company, hobbyist coder (teacher / cafe owner / designer who codes on the side), "
        "product manager, academic researcher, security professional, open-source maintainer. "
        "They all share intellectual curiosity and skepticism of hype. Generate a persona typical of this community."
    ),
    "producthunt": (
        "Product Hunt — audience discovering new products. "
        "Pick ONE of these archetypes: "
        "UX/UI designer, early adopter (non-technical), product manager, growth hacker, "
        "startup founder (non-technical), indie maker, journalist covering tech, "
        "community manager, developer advocate, small business owner. "
        "They care about polish, novelty, and user experience. Generate a persona typical of this community."
    ),
    "indiehackers": (
        "Indie Hackers — bootstrapped builders. "
        "Pick ONE of these archetypes: "
        "solo founder running a micro-SaaS, freelancer productizing a service, "
        "developer with a side project, consultant building passive income, "
        "ex-corporate employee going independent, designer turned founder, "
        "non-technical founder learning to code, creator monetizing an audience. "
        "They optimize for MRR and independence over VC funding. Generate a persona typical of this community."
    ),
    "reddit_startups": (
        "Reddit r/startups — mix of early-stage builders and observers. "
        "Pick ONE of these archetypes: "
        "first-time founder, startup employee (sales / ops / marketing), angel investor, "
        "MBA student interested in entrepreneurship, product manager at a Series A, "
        "developer considering leaving their job, domain expert starting a company, "
        "journalist or blogger covering startups. "
        "Mix of optimism and hard-won scepticism. Generate a persona typical of this community."
    ),
    "linkedin": (
        "LinkedIn — professional network for enterprise and career. "
        "Pick ONE of these archetypes: "
        "VP at a mid-size company, enterprise sales director, HR leader, "
        "corporate strategy consultant, B2B marketing manager, CTO at a 200-person company, "
        "VC partner focused on Series B+, procurement officer, "
        "industry analyst, chief digital officer. "
        "They think in terms of ROI, risk, and organisational impact. Generate a persona typical of this community."
    ),
}
```

- [ ] **Step 4: `_SYSTEM_TMPL`에 MBTI 다양성 지시 추가**

`backend/simulation/persona_generator.py`에서 `_SYSTEM_TMPL` 변수를 찾아 마지막 줄에 MBTI 지시를 추가:

현재:
```python
_SYSTEM_TMPL = """\
You are generating a realistic, diverse persona for a knowledge node in the context of a specific idea being evaluated.
Given a node (title, source, abstract), the idea being analyzed, and the target platform, create a realistic person who would have a meaningful perspective on that idea ON THAT PLATFORM.

Platform context: {platform_context}

Guidelines:
- The persona does NOT have to be someone who created or published the node. They should be the kind of person who would encounter this topic on the specified platform.
- Use the platform context to determine appropriate role, seniority, and affiliation. Personas across platforms should differ significantly.
- Age must be consistent with seniority (e.g. a c_suite persona should be 38+ years old, a junior persona 22-30).
- Make the persona feel like a real individual: specific company, realistic age, coherent interests.
- Vary skepticism, commercial_focus, and innovation_openness to reflect the diversity of real users on this platform."""
```

교체 후 (마지막 bullet에 MBTI 줄 추가):
```python
_SYSTEM_TMPL = """\
You are generating a realistic, diverse persona for a knowledge node in the context of a specific idea being evaluated.
Given a node (title, source, abstract), the idea being analyzed, and the target platform, create a realistic person who would have a meaningful perspective on that idea ON THAT PLATFORM.

Platform context: {platform_context}

Guidelines:
- The persona does NOT have to be someone who created or published the node. They should be the kind of person who would encounter this topic on the specified platform.
- Use the platform context to determine appropriate role, seniority, and affiliation. Personas across platforms should differ significantly.
- Age must be consistent with seniority (e.g. a c_suite persona should be 38+ years old, a junior persona 22-30).
- Make the persona feel like a real individual: specific company, realistic age, coherent interests.
- Vary skepticism, commercial_focus, and innovation_openness to reflect the diversity of real users on this platform.
- Vary MBTI type across personas. Do NOT cluster on INTJ. Choose from the full 16 types; prefer less common types for variety."""
```

- [ ] **Step 5: `_fallback_persona()` 개선**

`backend/simulation/persona_generator.py` 파일 상단 import 영역에 `import random` 추가 (없으면).

`_fallback_persona()` 함수 바로 위에 풀 상수 추가:

```python
_FALLBACK_NAMES = [
    "Alex Morgan", "Sam Rivera", "Jordan Lee", "Casey Kim",
    "Taylor Nguyen", "Morgan Chen", "Riley Patel", "Drew Santos",
    "Quinn Yamamoto", "Avery Okafor",
]
_FALLBACK_MBTIS = ["INTJ", "INTP", "ENTP", "ENFP", "ISTJ", "ESTJ", "ISTP", "INFJ"]
```

`_fallback_persona()` 함수 본문을 아래로 교체:

```python
def _fallback_persona(node: dict, platform_name: str) -> Persona:
    return Persona(
        node_id=node.get("id", "unknown"),
        name=random.choice(_FALLBACK_NAMES),
        role="Software Engineer",
        age=30,
        seniority="mid",
        affiliation="individual",
        company="",
        mbti=random.choice(_FALLBACK_MBTIS),
        interests=["technology"],
        skepticism=5,
        commercial_focus=5,
        innovation_openness=5,
        source_title=node.get("title", ""),
    )
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
python -m pytest tests/test_persona_generator.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 7: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 기존 테스트 전부 PASS

- [ ] **Step 8: 커밋**

```bash
git add backend/simulation/persona_generator.py tests/test_persona_generator.py
git commit -m "feat(simulation): diversify persona archetypes and MBTI distribution

- Rewrite _PLATFORM_AUDIENCE for all 5 platforms with explicit archetype lists
- Add MBTI diversity instruction to _SYSTEM_TMPL
- Replace hardcoded fallback persona with random name/MBTI pool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Fix 2 — Name Deduplication (사후 중복 제거)

**Files:**
- Modify: `backend/simulation/social_runner.py`
- Test: `tests/test_social_runner.py`

---

- [ ] **Step 1: 테스트 먼저 작성**

`tests/test_social_runner.py` 끝에 추가:

```python
def test_name_deduplication_assigns_suffix_to_duplicates():
    """collect_personas_for_platform should suffix duplicate names within a platform."""
    from backend.simulation.models import Persona

    def make_persona(node_id, name):
        return Persona(
            node_id=node_id, name=name, role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )

    # Simulate the results list that collect_personas_for_platform builds
    p1 = make_persona("n1", "Ethan Park")
    p2 = make_persona("n2", "Ethan Park")   # duplicate
    p3 = make_persona("n3", "Daniel Cho")
    p4 = make_persona("n4", "Ethan Park")   # third duplicate

    results = [
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p1),
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p2),
        ({"type": "sim_persona", "persona": {"name": "Daniel Cho"}}, p3),
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p4),
    ]

    from backend.simulation.social_runner import _deduplicate_names
    _deduplicate_names(results)

    assert p1.name == "Ethan Park"
    assert p2.name == "Ethan Park (2)"
    assert p3.name == "Daniel Cho"
    assert p4.name == "Ethan Park (3)"

    # event names must match persona names
    assert results[0][0]["persona"]["name"] == "Ethan Park"
    assert results[1][0]["persona"]["name"] == "Ethan Park (2)"
    assert results[2][0]["persona"]["name"] == "Daniel Cho"
    assert results[3][0]["persona"]["name"] == "Ethan Park (3)"


def test_name_deduplication_handles_none_persona():
    """_deduplicate_names should safely skip entries where persona is None."""
    from backend.simulation.social_runner import _deduplicate_names

    results = [
        ({"type": "sim_persona", "persona": {"name": "Alex"}}, None),
        ({"type": "sim_persona", "persona": {"name": "Alex"}}, None),
    ]
    _deduplicate_names(results)  # should not raise
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
python -m pytest tests/test_social_runner.py::test_name_deduplication_assigns_suffix_to_duplicates tests/test_social_runner.py::test_name_deduplication_handles_none_persona -v
```

Expected: FAIL with `ImportError: cannot import name '_deduplicate_names'`

- [ ] **Step 3: `_deduplicate_names()` 헬퍼 함수 구현**

`backend/simulation/social_runner.py` 파일 상단 imports 다음, `run_simulation` 함수 전에 추가:

```python
def _deduplicate_names(results: list[tuple[dict, "Persona | None"]]) -> None:
    """Assign '(N)' suffix to duplicate persona names within a single platform's result list.

    Mutates both the Persona object and the corresponding sim_persona event dict in-place
    so that the frontend receives consistent names.
    """
    name_counter: dict[str, int] = {}
    for event, persona in results:
        if persona is None:
            continue
        base_name = persona.name
        count = name_counter.get(base_name, 0)
        if count > 0:
            new_name = f"{base_name} ({count + 1})"
            persona.name = new_name
            if event and isinstance(event.get("persona"), dict):
                event["persona"]["name"] = new_name
        name_counter[base_name] = count + 1
```

- [ ] **Step 4: `collect_personas_for_platform()` 내부에서 `_deduplicate_names` 호출**

`backend/simulation/social_runner.py`에서 `collect_personas_for_platform()` 함수를 찾아 `return results` 직전에 호출 추가:

현재:
```python
    async def collect_personas_for_platform(platform_name: str) -> list[tuple[dict, Persona]]:
        results = []
        async for event in round_personas(
            nodes, idea_text,
            adjacency=adjacency, id_to_node=id_to_node,
            platform_name=platform_name,
            provider=provider,
            ontology=ontology,
        ):
            persona = event.pop("_persona", None)
            if persona is not None:
                results.append((event, persona))
            else:
                results.append((event, None))
        return results
```

교체 후:
```python
    async def collect_personas_for_platform(platform_name: str) -> list[tuple[dict, Persona]]:
        results = []
        async for event in round_personas(
            nodes, idea_text,
            adjacency=adjacency, id_to_node=id_to_node,
            platform_name=platform_name,
            provider=provider,
            ontology=ontology,
        ):
            persona = event.pop("_persona", None)
            if persona is not None:
                results.append((event, persona))
            else:
                results.append((event, None))
        _deduplicate_names(results)
        return results
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
python -m pytest tests/test_social_runner.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/simulation/social_runner.py tests/test_social_runner.py
git commit -m "feat(simulation): deduplicate persona names within each platform

Add _deduplicate_names() helper that assigns '(N)' suffix to duplicate
names after all personas are collected, before events are yielded to
the frontend. Ensures event names and Persona.name stay in sync.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Fix 3 — Cross-Round Cooldown (라운드 간 발언자 쿨다운)

### Task 3a: PlatformState에 recent_speakers 추가

**Files:**
- Modify: `backend/simulation/models.py`
- Test: `tests/test_social_rounds.py`

---

- [ ] **Step 1: 테스트 먼저 작성 — PlatformState 필드 존재 확인**

`tests/test_social_rounds.py` 끝에 추가:

```python
def test_platform_state_has_recent_speakers_field():
    """PlatformState must have a recent_speakers dict field defaulting to empty."""
    from backend.simulation.models import PlatformState
    state = PlatformState(platform_name="hackernews")
    assert hasattr(state, "recent_speakers")
    assert isinstance(state.recent_speakers, dict)
    assert len(state.recent_speakers) == 0
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
python -m pytest tests/test_social_rounds.py::test_platform_state_has_recent_speakers_field -v
```

Expected: FAIL with `AttributeError`

- [ ] **Step 3: `PlatformState`에 `recent_speakers` 필드 추가**

`backend/simulation/models.py`에서 `PlatformState` dataclass를 찾아 교체:

현재:
```python
@dataclasses.dataclass
class PlatformState:
    platform_name: str
    posts: list[SocialPost] = dataclasses.field(default_factory=list)
    round_num: int = 0
```

교체 후:
```python
@dataclasses.dataclass
class PlatformState:
    platform_name: str
    posts: list[SocialPost] = dataclasses.field(default_factory=list)
    round_num: int = 0
    recent_speakers: dict[str, int] = dataclasses.field(default_factory=dict)
    # node_id → 마지막 콘텐츠(comment/reply) 생성 round_num. vote/react는 기록 안 함.
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
python -m pytest tests/test_social_rounds.py::test_platform_state_has_recent_speakers_field -v
```

Expected: PASS

---

### Task 3b: select_active_agents()에 cooldown 가중치 적용

**Files:**
- Modify: `backend/simulation/social_rounds.py`
- Test: `tests/test_social_rounds.py`

---

- [ ] **Step 5: 테스트 먼저 작성 — cooldown 가중치 검증**

`tests/test_social_rounds.py` 끝에 추가:

```python
def test_select_active_agents_cooldown_reduces_recent_speaker_weight():
    """Agents who spoke in the previous round should have weight reduced to 0.1x."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    def make_persona(node_id):
        return Persona(
            node_id=node_id, name=f"Agent {node_id}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )

    # 10명 페르소나, 전원 동일 degree=1
    personas = [make_persona(f"n{i}") for i in range(10)]
    degree = {p.node_id: 1 for p in personas}

    # n0이 직전 라운드(round 5)에 발언
    recent_speakers = {"n0": 5}

    # 충분한 반복으로 확률 추정
    selections = []
    for _ in range(1000):
        selected = select_active_agents(
            personas, degree,
            activation_rate=0.3,
            recent_speakers=recent_speakers,
            current_round=6,
        )
        selections.append([p.node_id for p in selected])

    n0_count = sum(1 for s in selections if "n0" in s)
    other_avg = sum(
        sum(1 for s in selections if f"n{i}" in s)
        for i in range(1, 10)
    ) / 9

    # n0 선택 횟수는 다른 에이전트 평균의 20% 이하여야 함 (0.1x weight 반영)
    assert n0_count < other_avg * 0.3, (
        f"n0 should be selected much less frequently: n0={n0_count}, other_avg={other_avg:.1f}"
    )


def test_select_active_agents_cooldown_none_behaves_as_before():
    """When recent_speakers=None, behavior matches original (no cooldown)."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    personas = [
        Persona(
            node_id=f"n{i}", name=f"Agent {i}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )
        for i in range(5)
    ]
    result = select_active_agents(personas, None, activation_rate=0.5, recent_speakers=None)
    assert len(result) >= 1
    assert len(result) <= len(personas)


def test_select_active_agents_cooldown_fallback_small_pool():
    """When all agents have cooldown and pool is small, at least 1 agent is returned."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    personas = [
        Persona(
            node_id=f"n{i}", name=f"Agent {i}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )
        for i in range(3)
    ]
    # 전원 직전 라운드 발언자
    recent_speakers = {"n0": 5, "n1": 5, "n2": 5}
    result = select_active_agents(
        personas, None, activation_rate=1.0,
        recent_speakers=recent_speakers, current_round=6,
    )
    assert len(result) >= 1
```

- [ ] **Step 6: 테스트 실행 — 실패 확인**

```bash
python -m pytest tests/test_social_rounds.py::test_select_active_agents_cooldown_reduces_recent_speaker_weight tests/test_social_rounds.py::test_select_active_agents_cooldown_none_behaves_as_before tests/test_social_rounds.py::test_select_active_agents_cooldown_fallback_small_pool -v
```

Expected: FAIL (파라미터 없음)

- [ ] **Step 7: `select_active_agents()` 시그니처 및 로직 수정**

`backend/simulation/social_rounds.py`에서 `select_active_agents()` 함수 전체를 교체:

현재:
```python
def select_active_agents(
    personas: list[Persona],
    degree: dict[str, int] | None,
    activation_rate: float = 0.25,
) -> list[Persona]:
    """Degree-weighted random selection. Always returns at least 1 agent."""
    k = max(1, round(len(personas) * activation_rate))
    if degree is None or all(degree.get(p.node_id, 0) == 0 for p in personas):
        return random.sample(personas, min(k, len(personas)))
    weights = [max(1, degree.get(p.node_id, 0)) for p in personas]
    selected: list[Persona] = []
    pool = list(zip(personas, weights))
    while len(selected) < k and pool:
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cumulative = 0.0
        for i, (persona, w) in enumerate(pool):
            cumulative += w
            if r <= cumulative:
                selected.append(persona)
                pool.pop(i)
                break
    return selected
```

교체 후:
```python
def select_active_agents(
    personas: list[Persona],
    degree: dict[str, int] | None,
    activation_rate: float = 0.25,
    recent_speakers: dict[str, int] | None = None,
    current_round: int = 0,
) -> list[Persona]:
    """Degree-weighted random selection with cross-round cooldown.

    recent_speakers: node_id → last round they produced content (comment/reply).
    Agents who spoke in the previous round get weight * 0.1.
    Agents who spoke two rounds ago get weight * 0.5.
    Always returns at least 1 agent even if all are on cooldown.
    """
    k = max(1, round(len(personas) * activation_rate))

    def _base_weight(p: Persona) -> float:
        base = float(max(1, degree.get(p.node_id, 0)) if degree else 1.0)
        if recent_speakers is None:
            return base
        last = recent_speakers.get(p.node_id, -99)
        if last == current_round - 1:
            return base * 0.1
        if last == current_round - 2:
            return base * 0.5
        return base

    # uniform fallback when degree is None and no cooldown
    if degree is None and recent_speakers is None:
        return random.sample(personas, min(k, len(personas)))

    weights = [_base_weight(p) for p in personas]
    selected: list[Persona] = []
    pool = list(zip(personas, weights))
    while len(selected) < k and pool:
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cumulative = 0.0
        for i, (persona, w) in enumerate(pool):
            cumulative += w
            if r <= cumulative:
                selected.append(persona)
                pool.pop(i)
                break
    return selected
```

- [ ] **Step 8: 테스트 실행 — 통과 확인**

```bash
python -m pytest tests/test_social_rounds.py::test_select_active_agents_cooldown_reduces_recent_speaker_weight tests/test_social_rounds.py::test_select_active_agents_cooldown_none_behaves_as_before tests/test_social_rounds.py::test_select_active_agents_cooldown_fallback_small_pool -v
```

Expected: 모든 테스트 PASS

---

### Task 3c: platform_round()에서 발언자 기록 및 cooldown 파라미터 전달

**Files:**
- Modify: `backend/simulation/social_rounds.py`
- Test: (기존 테스트 회귀 확인)

---

- [ ] **Step 9: `platform_round()` 시그니처에서 `select_active_agents()` 호출 수정**

`backend/simulation/social_rounds.py`에서 `platform_round()` 함수 내부 `select_active_agents()` 호출 라인을 찾아 교체:

현재:
```python
    active = select_active_agents(personas, degree, activation_rate)
```

교체 후:
```python
    active = select_active_agents(
        personas, degree, activation_rate,
        recent_speakers=state.recent_speakers,
        current_round=round_num,
    )
```

- [ ] **Step 10: `platform_round()` 내 콘텐츠 생성 완료 후 발언자 기록**

같은 함수 내 `if platform.requires_content(action.action_type):` 블록에서 `post`를 `state.posts.append(post)` 하는 라인 바로 다음에 발언자 기록 추가:

현재:
```python
            state.posts.append(post)
            if action.target_post_id:
                round_stats["new_comments"] += 1
            else:
                round_stats["new_posts"] += 1
            yield {"type": "sim_platform_post", ...}
```

교체 후 (state.posts.append 다음 줄에 한 줄 추가):
```python
            state.posts.append(post)
            state.recent_speakers[persona.node_id] = round_num  # cooldown 기록
            if action.target_post_id:
                round_stats["new_comments"] += 1
            else:
                round_stats["new_posts"] += 1
            yield {"type": "sim_platform_post", ...}
```

- [ ] **Step 11: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 모든 테스트 PASS

- [ ] **Step 12: 커밋**

```bash
git add backend/simulation/models.py backend/simulation/social_rounds.py tests/test_social_rounds.py
git commit -m "feat(simulation): add cross-round cooldown to reduce agent repetition

- Add PlatformState.recent_speakers: dict[str, int] to track last active round
- Extend select_active_agents() with cooldown weights (0.1x prev round, 0.5x 2 rounds ago)
- platform_round() records speakers after content generation (comment/reply only)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 최종 확인

- [ ] **전체 테스트 최종 실행**

```bash
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASS (기존 9개 + 신규 8개)
