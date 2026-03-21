# TPM Rate Limiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 각 LLM API 호출 후 실제 사용 토큰 수를 Redis 슬라이딩 윈도우에 기록하고, 분당 토큰 합계(TPM)가 한도에 근접하면 호출 전에 대기시켜 429 오류를 방지한다.

**Architecture:** `rate_limiter.py`에 RPM과 독립적인 TPM 슬라이딩 윈도우를 추가한다. 각 LLM 응답에서 실제 사용 토큰을 추출해 `LLMResponse.tokens_used`에 담고, `_complete_*` 함수에서 호출 전에 `acquire_tpm_slot`(max_tokens 기준 보수적 예약), 호출 성공 후에 `record_token_usage`(실제 토큰으로 교체)를 각각 호출한다. `record_token_usage`는 Redis 오류가 발생해도 예외를 상위로 전파하지 않고 로그만 남긴다(이미 API 응답을 받은 상태에서 사후 기록 실패로 호출 전체가 실패처럼 보이는 것을 방지). 예약 항목 TTL은 70초이므로, 재시도 최대 대기 시간(5+10+20=35초)이 60초 윈도우 이내라 예약 항목이 만료 전에 해제된다.

**Tech Stack:** Python asyncio, Redis (aioredis), Lua scripting (atomic sliding window), pytest + unittest.mock

---

## File Map

- Modify: `backend/simulation/rate_limiter.py` — TPM Lua 스크립트 2개, `acquire_tpm_slot()`, `record_token_usage()`, TPM 환경변수 설정 추가
- Modify: `backend/llm.py` — `LLMResponse.tokens_used` 필드 추가, `_extract_*` 함수에서 usage 파싱, `_complete_*` 3개에 TPM 연동
- Create: `tests/test_tpm_rate_limiter.py` — TPM acquire/record 단위 테스트 (mock Redis)
- Modify: `tests/test_llm.py` — tokens_used 추출 테스트, record_token_usage 호출 검증
- Modify: `.env.example` — TPM 환경변수 항목 추가

---

## Task 1: TPM 슬라이딩 윈도우 — rate_limiter.py

**Files:**
- Modify: `backend/simulation/rate_limiter.py`
- Create: `tests/test_tpm_rate_limiter.py`
- Modify: `.env.example`

### 설계 노트

TPM 슬라이딩 윈도우는 RPM과 구조가 다르다. RPM은 카운트만 추적하지만 TPM은 각 항목의 토큰 수를 합산해야 한다. Redis sorted set의 member를 `"{tokens}:{uuid}"` 형식으로 인코딩해서 Lua 스크립트 내에서 파싱·합산한다. `ZRANGE key 0 -1`로 전체 순회하는 `_RECORD_TPM_SCRIPT`는 O(N)이지만 윈도우 안 항목 수가 수십~수백 개 수준이므로 현재 규모에서 충분하다.

**acquire_tpm_slot**: 호출 전에 max_tokens를 예약. 현재 윈도우 합계 + 요청 토큰이 한도를 초과하면 가장 오래된 항목이 만료될 때까지 대기 후 재시도.

**record_token_usage**: 호출 후 실제 사용 토큰으로 예약 항목을 교체. Redis 오류는 로그만 남기고 예외를 삼킨다. `_redis_client`가 전역 상태이므로 테스트에서 `_get_redis`를 패치할 때 다른 테스트가 먼저 실제 연결을 초기화했다면 패치가 무력화될 수 있다 — `_redis_client = None`을 각 테스트에서 리셋하거나, 테스트 순서를 격리하면 안전하다.

TPM 기본값 (환경변수로 override 가능):
- `OPENAI_TPM=100000`
- `ANTHROPIC_TPM=40000`
- `GEMINI_TPM=250000`

RPM과 동일한 `_SAFETY` 계수(기본 0.80)를 공유한다. TPM과 RPM의 안전 계수를 독립적으로 조정하려면 별도 환경변수를 추가해야 하지만 현재는 단순함을 우선한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tpm_rate_limiter.py` 를 새로 생성한다:

```python
import pytest
import time
from unittest.mock import AsyncMock, patch


# ── acquire_tpm_slot ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_acquire_tpm_slot_ok():
    """TPM 여유가 있으면 즉시 reservation_id를 반환한다."""
    from backend.simulation.rate_limiter import acquire_tpm_slot

    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=["ok", "0"])

    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis):
        entry_id = await acquire_tpm_slot("openai", 1000)
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0


@pytest.mark.asyncio
async def test_acquire_tpm_slot_waits_then_ok():
    """TPM 한도 초과 시 대기 후 재시도한다."""
    from backend.simulation.rate_limiter import acquire_tpm_slot

    mock_redis = AsyncMock()
    past_ts = str(time.time() - 59.0)  # 1초 후 만료될 슬롯
    mock_redis.eval = AsyncMock(side_effect=[
        ["wait", past_ts],
        ["ok", "0"],
    ])

    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await acquire_tpm_slot("openai", 1000)
        mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_acquire_tpm_slot_unknown_provider_returns_empty():
    """알 수 없는 provider는 즉시 빈 문자열을 반환한다 (대기 없음)."""
    from backend.simulation.rate_limiter import acquire_tpm_slot

    result = await acquire_tpm_slot("unknown_provider", 1000)
    assert result == ""


# ── record_token_usage ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_token_usage_replaces_reservation():
    """record_token_usage는 Lua 스크립트를 호출해 예약 항목을 실제 토큰으로 교체한다."""
    from backend.simulation.rate_limiter import record_token_usage

    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value="ok")

    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis):
        await record_token_usage("openai", actual_tokens=800, reservation_id="test-uuid-123")
        mock_redis.eval.assert_awaited_once()
        call_args = mock_redis.eval.call_args
        # actual_tokens와 reservation_id가 Lua 스크립트 인자로 전달됐는지 확인
        args_str = str(call_args)
        assert "800" in args_str
        assert "test-uuid-123" in args_str


@pytest.mark.asyncio
async def test_record_token_usage_unknown_provider_noop():
    """알 수 없는 provider는 Redis를 호출하지 않고 조용히 반환한다."""
    from backend.simulation.rate_limiter import record_token_usage

    mock_redis = AsyncMock()
    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis):
        await record_token_usage("unknown_provider", actual_tokens=100, reservation_id="x")
        mock_redis.eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_token_usage_empty_reservation_id_noop():
    """빈 reservation_id(알 수 없는 provider에서 반환된 값)는 Redis를 호출하지 않는다."""
    from backend.simulation.rate_limiter import record_token_usage

    mock_redis = AsyncMock()
    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis):
        await record_token_usage("openai", actual_tokens=100, reservation_id="")
        mock_redis.eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_token_usage_redis_error_is_swallowed():
    """record_token_usage에서 Redis 오류가 발생해도 예외를 전파하지 않는다."""
    from backend.simulation.rate_limiter import record_token_usage

    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch("backend.simulation.rate_limiter._get_redis", return_value=mock_redis):
        # 예외 없이 반환되면 통과
        await record_token_usage("openai", actual_tokens=100, reservation_id="some-id")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_tpm_rate_limiter.py -v 2>&1 | head -30
```

기대 결과: `ImportError` 또는 `AttributeError` — `acquire_tpm_slot`, `record_token_usage` 미존재

- [ ] **Step 3: rate_limiter.py에 TPM 구현 추가**

`backend/simulation/rate_limiter.py`를 열어 기존 내용에 추가한다.

**파일 상단 `_PROVIDER_RPM` / `_REDIS_KEYS` 블록 바로 아래에 추가:**

```python
_PROVIDER_TPM: dict[str, int] = {
    "openai":    max(1, int(int(os.getenv("OPENAI_TPM",    "100000")) * _SAFETY)),
    "anthropic": max(1, int(int(os.getenv("ANTHROPIC_TPM",  "40000")) * _SAFETY)),
    "gemini":    max(1, int(int(os.getenv("GEMINI_TPM",    "250000")) * _SAFETY)),
}

_TPM_REDIS_KEYS: dict[str, str] = {
    "openai":    "noosphere:openai:tpm",
    "anthropic": "noosphere:anthropic:tpm",
    "gemini":    "noosphere:gemini:tpm",
}
```

**파일 끝에 Lua 스크립트 2개와 함수 2개를 추가:**

```python
# ── TPM 슬라이딩 윈도우 ─────────────────────────────────────────────────────
# member 형식: "{reserved_tokens}:{uuid}"  (예약) / "{actual_tokens}:rec:{uuid}"  (기록)
# score: timestamp (float)

_ACQUIRE_TPM_SCRIPT = """
local key          = KEYS[1]
local now          = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit        = tonumber(ARGV[3])
local tokens       = tonumber(ARGV[4])
local entry_id     = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

local entries = redis.call('ZRANGE', key, 0, -1)
local current = 0
for _, member in ipairs(entries) do
    local sep = string.find(member, ':')
    if sep then
        current = current + tonumber(string.sub(member, 1, sep - 1))
    end
end

if current + tokens <= limit then
    redis.call('ZADD', key, now, tostring(tokens) .. ':' .. entry_id)
    redis.call('EXPIRE', key, 70)
    return {'ok', '0'}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if #oldest > 0 then
        return {'wait', oldest[2]}
    end
    return {'wait', tostring(now)}
end
"""

_RECORD_TPM_SCRIPT = """
local key         = KEYS[1]
local now         = tonumber(ARGV[1])
local actual      = tonumber(ARGV[2])
local reserved_id = ARGV[3]

local all = redis.call('ZRANGE', key, 0, -1)
for _, member in ipairs(all) do
    if string.find(member, reserved_id, 1, true) then
        redis.call('ZREM', key, member)
        break
    end
end

if actual > 0 then
    redis.call('ZADD', key, now, tostring(actual) .. ':rec:' .. reserved_id)
    redis.call('EXPIRE', key, 70)
end
return 'ok'
"""


async def acquire_tpm_slot(provider: str = "openai", tokens: int = 1000) -> str:
    """
    TPM gate: LLM 호출 전에 await. 토큰 용량이 생길 때까지 대기.
    반환값: reservation_id (record_token_usage에 전달할 것).
    알 수 없는 provider는 즉시 빈 문자열을 반환한다.
    """
    if provider not in _TPM_REDIS_KEYS:
        return ""

    r = _get_redis()
    redis_key = _TPM_REDIS_KEYS[provider]
    limit = _PROVIDER_TPM[provider]
    reservation_id = str(uuid.uuid4())

    while True:
        now = time.time()
        window_start = now - 60.0

        result = await r.eval(
            _ACQUIRE_TPM_SCRIPT,
            1,
            redis_key,
            str(now),
            str(window_start),
            str(limit),
            str(tokens),
            reservation_id,
        )

        if result[0] == "ok":
            return reservation_id

        oldest_ts = float(result[1])
        sleep_for = (oldest_ts + 60.0) - time.time() + 0.05
        await asyncio.sleep(max(0.05, sleep_for))


async def record_token_usage(
    provider: str,
    actual_tokens: int,
    reservation_id: str,
) -> None:
    """
    LLM 호출 완료 후 실제 사용 토큰으로 예약 항목을 교체한다.
    reservation_id는 acquire_tpm_slot의 반환값.
    알 수 없는 provider나 빈 reservation_id는 무시.
    Redis 오류는 로그만 남기고 예외를 삼킨다
    (이미 API 응답을 받은 상태에서 사후 기록 실패가 호출 전체를 실패로 만들지 않도록).
    """
    if provider not in _TPM_REDIS_KEYS or not reservation_id:
        return

    r = _get_redis()
    redis_key = _TPM_REDIS_KEYS[provider]

    try:
        await r.eval(
            _RECORD_TPM_SCRIPT,
            1,
            redis_key,
            str(time.time()),
            str(actual_tokens),
            reservation_id,
        )
    except Exception as exc:
        logger.warning("record_token_usage failed for %s: %s", provider, exc)
```

`logger`가 `rate_limiter.py`에 없으면 파일 상단에 추가:
```python
logger = logging.getLogger(__name__)
```
그리고 `import logging`도 상단에 추가.

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_tpm_rate_limiter.py -v
```

기대 결과: 7개 테스트 모두 PASS

- [ ] **Step 5: .env.example에 TPM 변수 추가**

`.env.example` 파일을 열어 기존 내용 끝에 추가:

```bash
# TPM limits (tokens per minute per provider, 80% safety 적용 전 원본 한도)
OPENAI_TPM=100000
ANTHROPIC_TPM=40000
GEMINI_TPM=250000
```

- [ ] **Step 6: 커밋**

```bash
git add backend/simulation/rate_limiter.py tests/test_tpm_rate_limiter.py .env.example
git commit -m "feat: add TPM sliding window rate limiter (acquire_tpm_slot + record_token_usage)"
```

---

## Task 2: LLMResponse에 tokens_used 추가 및 각 provider usage 파싱

**Files:**
- Modify: `backend/llm.py`
- Modify: `tests/test_llm.py`

### 설계 노트

각 provider의 응답 구조에서 실제 사용 토큰을 추출한다:
- **OpenAI**: `response.usage.total_tokens`
- **Anthropic**: `response.usage.input_tokens + response.usage.output_tokens`
- **Gemini**: `response.usage_metadata.total_token_count`

추출 실패 시(usage 필드 없음) `None`을 반환하며, `_complete_*`에서 `result.tokens_used or 0`으로 처리한다.

이 태스크에서는 `LLMResponse` 필드 추가와 파싱만 한다. `acquire_tpm_slot`/`record_token_usage` import와 호출 연동은 Task 3에서 처리한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_llm.py` 파일 끝에 다음을 추가한다:

```python
# ── tokens_used 추출 ──────────────────────────────────────────────────────────

async def test_complete_openai_returns_tokens_used():
    """OpenAI 응답에서 total_tokens를 tokens_used로 반환한다."""
    from backend.llm import complete

    mock_message = MagicMock()
    mock_message.content = "Hello"
    mock_message.tool_calls = None

    mock_usage = MagicMock()
    mock_usage.total_tokens = 42

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=50,
        )
    assert result.tokens_used == 42


async def test_complete_openai_tokens_used_none_when_usage_missing():
    """OpenAI 응답에 usage 필드가 없으면 tokens_used는 None이다."""
    from backend.llm import complete

    mock_message = MagicMock()
    mock_message.content = "Hello"
    mock_message.tool_calls = None

    mock_response = MagicMock(spec=["choices"])  # usage 속성 없음
    mock_response.choices = [MagicMock(message=mock_message)]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=50,
        )
    assert result.tokens_used is None


async def test_complete_anthropic_returns_tokens_used():
    """Anthropic 응답에서 input_tokens + output_tokens 합계를 tokens_used로 반환한다."""
    from backend.llm import complete
    import anthropic

    mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
    mock_text_block.text = "response"

    mock_usage = MagicMock()
    mock_usage.input_tokens = 30
    mock_usage.output_tokens = 20

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_anthropic_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="anthropic",
            max_tokens=50,
        )
    assert result.tokens_used == 50  # input(30) + output(20)


async def test_complete_gemini_returns_tokens_used():
    """Gemini 응답에서 usage_metadata.total_token_count를 tokens_used로 반환한다."""
    from backend.llm import complete

    mock_usage_metadata = MagicMock()
    mock_usage_metadata.total_token_count = 77

    mock_response = MagicMock()
    mock_response.text = "Gemini"
    mock_response.usage_metadata = mock_usage_metadata
    mock_part = MagicMock(spec=[])
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

    mock_aio = AsyncMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio = mock_aio

    with patch("backend.llm._get_gemini_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="gemini",
            max_tokens=50,
        )
    assert result.tokens_used == 77
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_llm.py::test_complete_openai_returns_tokens_used \
                 tests/test_llm.py::test_complete_openai_tokens_used_none_when_usage_missing \
                 tests/test_llm.py::test_complete_anthropic_returns_tokens_used \
                 tests/test_llm.py::test_complete_gemini_returns_tokens_used -v 2>&1 | head -30
```

기대 결과: `AttributeError: 'LLMResponse' object has no attribute 'tokens_used'`

- [ ] **Step 3: LLMResponse 필드 추가**

`backend/llm.py`의 `LLMResponse` dataclass를 수정한다:

```python
@dataclass
class LLMResponse:
    content: str | None        # normalized text response
    tool_name: str | None      # name of tool called, if any
    tool_args: dict | None     # parsed tool arguments (plain dict)
    tokens_used: int | None = None  # actual tokens consumed (input + output)
```

- [ ] **Step 4: 중간 테스트 확인 (AttributeError → 다음 오류로 이동)**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_llm.py::test_complete_openai_returns_tokens_used -v 2>&1 | tail -10
```

기대 결과: `AssertionError` — `tokens_used`는 존재하지만 아직 None (파싱 미구현)

- [ ] **Step 5: OpenAI usage 파싱**

`_extract_openai_response` 함수를 수정한다:

```python
def _extract_openai_response(response, tool_choice: str | None) -> LLMResponse:
    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    tokens_used: int | None = None
    try:
        tokens_used = response.usage.total_tokens
    except AttributeError:
        pass
    if tool_calls:
        tc = tool_calls[0]
        return LLMResponse(
            content=message.content,
            tool_name=tc.function.name,
            tool_args=json.loads(tc.function.arguments),
            tokens_used=tokens_used,
        )
    if tool_choice is not None:
        raise LLMToolRequired(f"Expected tool call '{tool_choice}' but got none")
    return LLMResponse(content=message.content, tool_name=None, tool_args=None, tokens_used=tokens_used)
```

- [ ] **Step 6: Anthropic usage 파싱**

`_extract_anthropic_response` 함수를 수정한다:

```python
def _extract_anthropic_response(response, tool_choice: str | None) -> LLMResponse:
    tokens_used: int | None = None
    try:
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
    except AttributeError:
        pass
    tool_block = next(
        (b for b in response.content if isinstance(b, _anthropic.types.ToolUseBlock)),
        None
    )
    if tool_block is not None:
        return LLMResponse(
            content=None,
            tool_name=tool_block.name,
            tool_args=dict(tool_block.input),
            tokens_used=tokens_used,
        )
    if tool_choice is not None:
        raise LLMToolRequired(f"Expected tool call '{tool_choice}' but got none")
    text_block = next(
        (b for b in response.content if isinstance(b, _anthropic.types.TextBlock)),
        None
    )
    return LLMResponse(
        content=text_block.text if text_block else None,
        tool_name=None,
        tool_args=None,
        tokens_used=tokens_used,
    )
```

- [ ] **Step 7: Gemini usage 파싱**

`_extract_gemini_response` 함수를 수정한다:

```python
def _extract_gemini_response(response, tool_choice: str | None) -> LLMResponse:
    tokens_used: int | None = None
    try:
        tokens_used = response.usage_metadata.total_token_count
    except AttributeError:
        pass
    try:
        parts = response.candidates[0].content.parts
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc is not None and fc.name:
                return LLMResponse(
                    content=None,
                    tool_name=fc.name,
                    tool_args=dict(fc.args),
                    tokens_used=tokens_used,
                )
    except (IndexError, AttributeError):
        pass
    if tool_choice is not None:
        raise LLMToolRequired(f"Expected tool call '{tool_choice}' but got none")
    return LLMResponse(content=response.text, tool_name=None, tool_args=None, tokens_used=tokens_used)
```

- [ ] **Step 8: 전체 테스트 통과 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_llm.py -v 2>&1 | tail -20
```

기대 결과: 기존 테스트 포함 전체 PASS (새 4개 포함)

- [ ] **Step 9: 커밋**

```bash
git add backend/llm.py tests/test_llm.py
git commit -m "feat: add tokens_used to LLMResponse and parse usage from all providers"
```

---

## Task 3: _complete_* 함수에 TPM 연동

**Files:**
- Modify: `backend/llm.py`
- Modify: `tests/test_llm.py`

### 설계 노트

각 `_complete_*` 함수에서:
1. API 호출 전: `acquire_tpm_slot(provider, max_tokens)` — reservation_id 획득
2. API 호출 성공 후: `record_token_usage(provider, actual_tokens, reservation_id)` — 실제값으로 교체
3. 예외 발생 시: `record_token_usage(provider, 0, reservation_id)` — 슬롯 해제 (0으로 교체)
4. 재시도(429) 시: reservation_id를 유지하고 재사용 (재예약 불필요)

`record_token_usage`는 내부에서 예외를 삼키므로 `_complete_*` 안에서 try/except로 감쌀 필요 없다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_llm.py` 파일 끝에 다음을 추가한다:

```python
# ── TPM 연동 ──────────────────────────────────────────────────────────────────

async def test_acquire_tpm_slot_called_before_openai_request():
    """_complete_openai는 API 호출 전에 acquire_tpm_slot을 호출한다."""
    from backend.llm import complete

    call_order = []

    mock_message = MagicMock()
    mock_message.content = "ok"
    mock_message.tool_calls = None

    mock_usage = MagicMock()
    mock_usage.total_tokens = 30

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()

    async def fake_create(**kwargs):
        call_order.append("api_call")
        return mock_response

    mock_client.chat.completions.create = fake_create

    async def fake_acquire_tpm(provider, tokens):
        call_order.append("tpm_acquire")
        return "res-id"

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", side_effect=fake_acquire_tpm), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=200,
        )
    assert call_order.index("tpm_acquire") < call_order.index("api_call")


async def test_record_token_usage_called_with_actual_tokens_openai():
    """성공적인 OpenAI 호출 후 record_token_usage가 실제 토큰으로 호출된다."""
    from backend.llm import complete

    mock_message = MagicMock()
    mock_message.content = "ok"
    mock_message.tool_calls = None

    mock_usage = MagicMock()
    mock_usage.total_tokens = 100

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="reservation-abc"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock) as mock_record, \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=200,
        )
    mock_record.assert_awaited_once_with("openai", actual_tokens=100, reservation_id="reservation-abc")


async def test_record_token_usage_called_with_zero_on_exception():
    """OpenAI API 예외 발생 시 record_token_usage가 actual_tokens=0으로 호출된다."""
    from backend.llm import complete

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-xyz"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock) as mock_record, \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        with pytest.raises(RuntimeError):
            await complete(
                messages=[{"role": "user", "content": "hi"}],
                tier="low",
                provider="openai",
                max_tokens=200,
            )
    mock_record.assert_awaited_once_with("openai", actual_tokens=0, reservation_id="res-xyz")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_llm.py::test_acquire_tpm_slot_called_before_openai_request \
                 tests/test_llm.py::test_record_token_usage_called_with_actual_tokens_openai \
                 tests/test_llm.py::test_record_token_usage_called_with_zero_on_exception -v 2>&1 | head -30
```

기대 결과: `AssertionError` — `acquire_tpm_slot` 호출 없음

- [ ] **Step 3: import 추가**

`backend/llm.py` 상단 import를 수정한다:

```python
# 기존:
from backend.simulation.rate_limiter import acquire_api_slot
# 교체:
from backend.simulation.rate_limiter import acquire_api_slot, acquire_tpm_slot, record_token_usage
```

- [ ] **Step 4: _complete_openai 수정**

```python
async def _complete_openai(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> LLMResponse:
    client = _get_openai_client()
    kwargs: dict = {"model": model, "max_completion_tokens": max_tokens, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = _tool_choice_openai(tool_choice)

    reservation_id = await acquire_tpm_slot("openai", max_tokens)

    for attempt in range(4):
        await acquire_api_slot()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=timeout,
            )
            result = _extract_openai_response(response, tool_choice)
            await record_token_usage("openai", actual_tokens=result.tokens_used or 0, reservation_id=reservation_id)
            return result
        except LLMToolRequired:
            await record_token_usage("openai", actual_tokens=0, reservation_id=reservation_id)
            raise
        except openai.RateLimitError:
            if attempt == 3:
                await record_token_usage("openai", actual_tokens=0, reservation_id=reservation_id)
                raise LLMRateLimitError("OpenAI rate limit exceeded")
            wait = 5 * (2 ** attempt)
            logger.warning("OpenAI rate limit, retrying in %ds", wait)
            await asyncio.sleep(wait)
        except Exception:
            await record_token_usage("openai", actual_tokens=0, reservation_id=reservation_id)
            raise
    raise RuntimeError("Unreachable")
```

- [ ] **Step 5: _complete_anthropic 수정**

```python
async def _complete_anthropic(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> LLMResponse:
    client = _get_anthropic_client()

    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    user_messages = [m for m in messages if m.get("role") != "system"]
    system_str = "\n\n".join(system_parts) if system_parts else _anthropic.NOT_GIVEN

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_str,
        "messages": user_messages,
    }
    if tools:
        kwargs["tools"] = _to_anthropic_tools(tools)
        kwargs["tool_choice"] = _tool_choice_anthropic(tool_choice)

    reservation_id = await acquire_tpm_slot("anthropic", max_tokens)

    for attempt in range(4):
        await acquire_api_slot("anthropic")
        try:
            response = await asyncio.wait_for(
                client.messages.create(**kwargs),
                timeout=timeout,
            )
            result = _extract_anthropic_response(response, tool_choice)
            await record_token_usage("anthropic", actual_tokens=result.tokens_used or 0, reservation_id=reservation_id)
            return result
        except LLMToolRequired:
            await record_token_usage("anthropic", actual_tokens=0, reservation_id=reservation_id)
            raise
        except _anthropic.RateLimitError:
            if attempt == 3:
                await record_token_usage("anthropic", actual_tokens=0, reservation_id=reservation_id)
                raise LLMRateLimitError("Anthropic rate limit exceeded")
            wait = 5 * (2 ** attempt)
            logger.warning("Anthropic rate limit, retrying in %ds", wait)
            await asyncio.sleep(wait)
        except Exception:
            await record_token_usage("anthropic", actual_tokens=0, reservation_id=reservation_id)
            raise
    raise RuntimeError("Unreachable")
```

- [ ] **Step 6: _complete_gemini 수정**

```python
async def _complete_gemini(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> LLMResponse:
    client = _get_gemini_client()
    contents = _to_gemini_contents(messages)

    gemini_tools = _to_gemini_tools(tools) if tools else None
    tool_config = None
    if tools:
        mode = "ANY" if tool_choice else "AUTO"
        tool_config = _genai.types.ToolConfig(
            functionCallingConfig=_genai.types.FunctionCallingConfig(
                mode=mode,
                allowedFunctionNames=[tool_choice] if tool_choice else None,
            )
        )
    config = _genai.types.GenerateContentConfig(
        maxOutputTokens=max_tokens,
        tools=gemini_tools,
        toolConfig=tool_config,
    )

    reservation_id = await acquire_tpm_slot("gemini", max_tokens)

    for attempt in range(4):
        await acquire_api_slot("gemini")
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout,
            )
            result = _extract_gemini_response(response, tool_choice)
            await record_token_usage("gemini", actual_tokens=result.tokens_used or 0, reservation_id=reservation_id)
            return result
        except LLMToolRequired:
            await record_token_usage("gemini", actual_tokens=0, reservation_id=reservation_id)
            raise
        except _google_exceptions.ResourceExhausted:
            if attempt == 3:
                await record_token_usage("gemini", actual_tokens=0, reservation_id=reservation_id)
                raise LLMRateLimitError("Gemini rate limit exceeded")
            wait = 5 * (2 ** attempt)
            logger.warning("Gemini rate limit, retrying in %ds", wait)
            await asyncio.sleep(wait)
        except Exception:
            await record_token_usage("gemini", actual_tokens=0, reservation_id=reservation_id)
            raise
    raise RuntimeError("Unreachable")
```

- [ ] **Step 7: 전체 테스트 통과 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_llm.py tests/test_tpm_rate_limiter.py -v 2>&1 | tail -30
```

기대 결과: 전체 PASS

- [ ] **Step 8: 기존 테스트 회귀 확인**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/ -v --ignore=tests/test_db.py 2>&1 | tail -30
```

기대 결과: 기존 테스트 모두 PASS (test_db.py는 DB 연결이 필요해서 제외)

- [ ] **Step 9: 커밋**

```bash
git add backend/llm.py tests/test_llm.py
git commit -m "feat: integrate TPM rate limiting into all LLM provider calls"
```

---

## 완료 기준

- `tests/test_tpm_rate_limiter.py` 7개 테스트 PASS
- `tests/test_llm.py` 기존 테스트 포함 전체 PASS
- `LLMResponse.tokens_used`가 세 provider 모두에서 정확히 채워짐 (usage 없으면 None)
- `_complete_openai/anthropic/gemini` 각각 호출 전 `acquire_tpm_slot`, 호출 후 `record_token_usage` 실행
- 예외/실패 시 `actual_tokens=0`으로 슬롯 해제되어 TPM 윈도우 낭비 없음
- `.env.example`에 TPM 환경변수 3개 문서화
