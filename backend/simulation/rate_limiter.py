"""
Redis-based global rate limiter for LLM API calls.

Enforces a sliding-window RPM limit shared across ALL Celery workers,
preventing 429 errors. Supports all three providers independently.

Override via env:
  OPENAI_RPM=500          # OpenAI tier's actual limit (default 500)
  ANTHROPIC_RPM=50        # Anthropic tier's actual limit (default 50)
  GEMINI_RPM=60           # Gemini tier's actual limit (default 60)
  RPM_SAFETY=0.80         # fraction to actually use (default 0.80)
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────────────
_SAFETY = float(os.getenv("RPM_SAFETY", "0.80"))

_PROVIDER_RPM: dict[str, int] = {
    "openai":    max(1, int(int(os.getenv("OPENAI_RPM",    "500")) * _SAFETY)),
    "anthropic": max(1, int(int(os.getenv("ANTHROPIC_RPM",  "50")) * _SAFETY)),
    "gemini":    max(1, int(int(os.getenv("GEMINI_RPM",     "60")) * _SAFETY)),
}

_REDIS_KEYS: dict[str, str] = {
    "openai":    "noosphere:openai:rpm",
    "anthropic": "noosphere:anthropic:rpm",
    "gemini":    "noosphere:gemini:rpm",
}

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

# ── Redis 클라이언트 (지연 초기화) ─────────────────────────────────────────
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as _aioredis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = _aioredis.from_url(url, decode_responses=True)
    return _redis_client


# ── Lua 스크립트: 슬라이딩 윈도우 (atomic) ──────────────────────────────────
_ACQUIRE_SCRIPT = """
local key        = KEYS[1]
local now        = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit      = tonumber(ARGV[3])
local entry_id   = ARGV[4]

-- 만료된 항목 제거
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, entry_id)
    redis.call('EXPIRE', key, 70)
    return {'ok', '0'}
else
    -- 가장 오래된 항목의 timestamp 반환 → 언제 슬롯이 열리는지 계산
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if #oldest > 0 then
        return {'wait', oldest[2]}
    end
    return {'wait', tostring(now)}
end
"""


async def acquire_api_slot(provider: str = "openai") -> None:
    """
    Rate-limit gate: LLM API를 호출하기 전에 이 함수를 await.
    Redis 슬라이딩 윈도우로 전체 워커에 걸쳐 프로바이더별 RPM을 제한.
    슬롯이 없으면 열릴 때까지 정밀하게 대기.
    """
    r = _get_redis()
    redis_key = _REDIS_KEYS.get(provider, f"noosphere:{provider}:rpm")
    limit = _PROVIDER_RPM.get(provider, 40)

    while True:
        now = time.time()
        window_start = now - 60.0
        entry_id = str(uuid.uuid4())

        result = await r.eval(
            _ACQUIRE_SCRIPT,
            1,
            redis_key,
            str(now),
            str(window_start),
            str(limit),
            entry_id,
        )

        if result[0] == "ok":
            return

        # 가장 오래된 슬롯이 윈도우 밖으로 나가는 시점까지 대기
        oldest_ts = float(result[1])
        sleep_for = (oldest_ts + 60.0) - time.time() + 0.05
        await asyncio.sleep(max(0.05, sleep_for))


# ── persona_generator.py의 `async with _api_sem:` 과 호환 ─────────────────
class _RateLimitedSlot:
    """async context manager — acquire_api_slot() 을 래핑."""
    def __init__(self, provider: str = "openai"):
        self._provider = provider

    async def __aenter__(self) -> "_RateLimitedSlot":
        await acquire_api_slot(self._provider)
        return self

    async def __aexit__(self, *_) -> None:
        pass


api_sem = _RateLimitedSlot("openai")


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
    Redis 오류는 로그만 남기고 예외를 삼킨다.
    """
    if provider not in _TPM_REDIS_KEYS or not reservation_id:
        return

    redis_key = _TPM_REDIS_KEYS[provider]

    try:
        r = _get_redis()
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
