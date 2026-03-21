# Persona Diversity & Simulation Quality Improvements

**Date:** 2026-03-22
**Status:** Approved (v3 — post-review)
**Branch:** feat/tpm-rate-limiting

---

## Problem Summary

1. **Role/MBTI 수렴** — 거의 모든 페르소나가 INTJ Software Engineer로 생성됨
2. **이름 중복** — 동일 플랫폼 내에서 서로 다른 node_id 에이전트가 같은 이름을 가짐
3. **라운드 간 반복** — 동일 에이전트가 12라운드 전반에 걸쳐 반복 선택됨

---

## Scope

**수정 대상:** 4개 production 파일 + 2개 테스트 파일

- `backend/simulation/persona_generator.py`
- `backend/simulation/models.py`
- `backend/simulation/social_rounds.py`
- `backend/simulation/social_runner.py` (Fix 2 중복 제거 로직 추가)

---

## Fix 1: Persona Role & MBTI Diversity

**File:** `persona_generator.py`

### Changes

**`_PLATFORM_AUDIENCE` 전면 재작성:**

기존 HN 설명이 "software engineers, systems programmers"로 시작해 LLM이 엔지니어로 수렴. 단순히 "Do NOT default to software engineer"를 덧붙이면 프롬프트 내 모순 발생. 해결책: 역할 목록에서 엔지니어의 비중을 낮추고, 다양한 유형을 동등하게 나열하도록 전면 재작성.

```python
"hackernews": (
    "Hacker News — community of curious, technically-literate people. "
    "Pick ONE of these archetypes at random (do not default to engineer): "
    "software engineer, indie hacker (solo product builder), "
    "seed-stage VC analyst, non-technical founder, "
    "marketer at a dev-tool company, hobbyist coder (teacher / cafe owner / designer who codes on the side), "
    "product manager, academic researcher, security professional, open-source maintainer. "
    "They all share intellectual curiosity and skepticism of hype."
),
```

다른 플랫폼도 같은 방식으로 archetype 목록을 명시적으로 나열하도록 재작성.

**`_SYSTEM_TMPL` MBTI 다양성 강제:**

```python
"- Vary MBTI type across personas. Do NOT cluster on INTJ. "
"  Choose from the full 16 types; prefer less common types for variety."
```

**`_fallback_persona()` 개선:**

기존: `name="Alex Morgan"`, `mbti="INTJ"` 하드코딩 → 실패 시 동일 이름/MBTI 반복.

개선: `random` 모듈을 사용해 아래 풀에서 선택:

```python
_FALLBACK_NAMES = [
    "Alex Morgan", "Sam Rivera", "Jordan Lee", "Casey Kim",
    "Taylor Nguyen", "Morgan Chen", "Riley Patel", "Drew Santos",
    "Quinn Yamamoto", "Avery Okafor",
]
_FALLBACK_MBTIS = ["INTJ", "INTP", "ENTP", "ENFP", "ISTJ", "ESTJ", "ISTP", "INFJ"]
```

10개 이름은 성별 중립, 다문화 구성. 8개 MBTI는 I/E 4개씩, T/F 균형.

### Testing

- `test_persona_generator.py`: `_SYSTEM_TMPL` 포맷 결과에 "Do NOT cluster on INTJ" 텍스트가 포함되는지 확인하는 단위 테스트
- 실제 역할/MBTI 분포 검증은 수동 QA (LLM 출력 품질 의존)

---

## Fix 2: Name Deduplication

**Files:** `social_runner.py`

### Architecture

`round_personas()`는 스트리밍 AsyncGenerator로, 각 페르소나를 생성하는 즉시 `sim_persona` 이벤트를 yield. 따라서 이 내부에서 "모든 생성 완료 후" 중복 처리를 하면 이미 yield된 이벤트와 실제 Persona 객체 간 이름 불일치 발생.

**올바른 위치:** `social_runner.py`의 `collect_personas_for_platform()`.

이 함수는 `round_personas()`의 모든 결과를 `results` 리스트에 수집한 후 반환 (yield 없음). 그 후 호출자(메인 루프)가 `entries = await task`로 전체 결과를 받아 이벤트를 yield. 따라서:

1. `collect_personas_for_platform()` 반환 직전에 중복 이름을 처리
2. `event["persona"]["name"]`와 `persona.name` 모두 업데이트 (이 시점에는 프론트엔드에 아직 yield 안 됨)
3. 이후 메인 루프가 수정된 이름으로 이벤트 yield → 불일치 없음

### Implementation Detail

`collect_personas_for_platform()` 내부, `return results` 직전:

```python
# 동일 플랫폼 내 이름 중복 제거
name_counter: dict[str, int] = {}
for event, persona in results:
    if persona is None:
        continue
    base_name = persona.name
    count = name_counter.get(base_name, 0)
    if count > 0:
        new_name = f"{base_name} ({count + 1})"
        persona.name = new_name
        if event and "persona" in event:
            event["persona"]["name"] = new_name
    name_counter[base_name] = count + 1
```

fallback 페르소나(`_fallback_persona()`)도 동일 흐름을 거치므로 별도 처리 불필요.

### Scope

- 동일 플랫폼 내 중복만 제거 (cross-platform 중복은 허용 범위 외)
- suffix 형식: `"Name (N)"` where N ≥ 2

### Acceptance Criteria

- 동일 플랫폼 내 동일 이름의 페르소나가 존재하지 않음
- 프론트엔드에 yield되는 `sim_persona` 이벤트의 이름과 실제 `Persona.name`이 일치함
- 기존 `round_personas()` 인터페이스 불변

### Testing

- `test_social_runner.py` (또는 `test_social_rounds.py`): 동일 이름을 반환하는 mock persona 여러 개를 주입했을 때 suffix가 올바르게 부여되고, event와 persona 객체 모두 동일한 이름을 가지는지 검증

---

## Fix 3: Cross-Round Cooldown

**Files:** `models.py`, `social_rounds.py`

### Changes

**`PlatformState` 필드 추가:**

```python
@dataclasses.dataclass
class PlatformState:
    platform_name: str
    posts: list[SocialPost] = dataclasses.field(default_factory=list)
    round_num: int = 0
    recent_speakers: dict[str, int] = dataclasses.field(default_factory=dict)
    # node_id → 마지막 콘텐츠 생성(comment/reply)한 round_num
    # vote/react 액션은 기록하지 않음
```

`recent_speakers`는 `social_runner.py`의 `sim_report` 직렬화에서 자동 제외됨 (`PlatformState` 자체를 `dataclasses.asdict()`하지 않고 `state.posts`만 수동 직렬화하기 때문).

**`select_active_agents()` 변경:**

```python
def select_active_agents(
    personas: list[Persona],
    degree: dict[str, int] | None,
    activation_rate: float = 0.25,
    recent_speakers: dict[str, int] | None = None,  # NEW, 기본 None
    current_round: int = 0,                          # NEW, 기본 0
) -> list[Persona]:
```

`recent_speakers=None`이면 기존 동작 유지. 있으면 base_weight 조정:

```
last_round = recent_speakers.get(persona.node_id, -99)
if last_round == current_round - 1:  weight *= 0.1
elif last_round == current_round - 2: weight *= 0.5
else:                                  weight *= 1.0
```

**호출 흐름 명확화:**

`select_active_agents()`는 `platform_round()` 진입 시 **1회만 호출** (반복문 밖, line 319 기준). 동일 라운드 내 `recent_speakers` 업데이트는 다음 라운드의 선택에만 영향을 미치며, 현재 라운드 내 에이전트 순서에는 영향 없음.

**`platform_round()` 변경:**

- `select_active_agents()` 호출 시 `recent_speakers=state.recent_speakers, current_round=round_num` 전달
- `for persona in active` 루프 내, 콘텐츠(comment/reply) 생성 완료 직후 `yield` 전:
  ```python
  state.recent_speakers[persona.node_id] = round_num
  ```
- vote/react 액션 분기에서는 `recent_speakers` 미기록

**폴백:**

기존 `select_active_agents()`의 `while len(selected) < k and pool:` 루프가 pool 고갈 시 자동으로 종료하여 k 미만의 에이전트를 반환. 이 동작을 그대로 유지 — 별도 하드 임계값 없음.

### Acceptance Criteria

- 직전 라운드 발언자의 base_weight가 0.1배로 감소하여 재선택 확률이 크게 낮아짐
- 풀이 k보다 작아도 시뮬레이션 중단 없음 (기존 폴백 동작)
- `recent_speakers=None` 기본값 → 기존 테스트/호출 코드 무변경
- `sim_report` 이벤트에 `recent_speakers` 미포함

### Testing

- `select_active_agents()`에 `recent_speakers`, `current_round` 전달 시 직전 발언자 가중치가 0.1배임을 단위 테스트로 검증 (결정론적: degree 고정, 충분히 큰 샘플)
- 풀 전원이 직전 발언자인 극단 케이스에서 에이전트가 최소 1명 반환되는지 검증

---

## Risk & Rollback

- Fix 1 (프롬프트 재작성), Fix 2 (수집 후 처리), Fix 3 (가중치 조정) 완전히 독립적 → 개별 롤백 가능
- 모든 신규 파라미터 기본값 유지 → 하위 호환
- Fix 2: LLM 호출 추가 없음 → 성능 영향 없음
- Fix 3: `select_active_agents()` 기본값 None → 기존 테스트 수정 불필요
