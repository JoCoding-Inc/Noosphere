"""
Redis-based global rate limiter for Anthropic API calls.

Enforces a sliding-window RPM limit shared across ALL Celery workers,
preventing 429 errors from the Haiku 4.5 Tier-1 limits:
  - 50 RPM  (hard limit)
  - 50,000 ITPM (input tokens/min — binding constraint in practice)
  - 10,000 OTPM

We target 20 RPM (40% of 50). Each call averages ~1,800-2,000 input tokens
(system + tool schema + feed context), so 20 RPM × 2,000 tokens ≈ 40,000 ITPM,
leaving a safe buffer under the 50K ITPM ceiling.

Override via env:
  ANTHROPIC_HAIKU_RPM=50   # your tier's actual limit
  ANTHROPIC_RPM_SAFETY=0.40  # fraction to actually use
"""
from __future__ import annotations
import asyncio
import os
import time
import uuid

# ── 설정 ──────────────────────────────────────────────────────────────────
_TIER_RPM = int(os.getenv("ANTHROPIC_HAIKU_RPM", "50"))
_SAFETY   = float(os.getenv("ANTHROPIC_RPM_SAFETY", "0.40"))
_EFFECTIVE_RPM = max(1, int(_TIER_RPM * _SAFETY))  # default: 20

_REDIS_KEY = "noosphere:anthropic:rpm"

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


async def acquire_api_slot() -> None:
    """
    Rate-limit gate: Anthropic API를 호출하기 전에 이 함수를 await.
    Redis 슬라이딩 윈도우로 전체 워커에 걸쳐 RPM을 제한.
    슬롯이 없으면 열릴 때까지 정밀하게 대기.
    """
    r = _get_redis()
    while True:
        now = time.time()
        window_start = now - 60.0
        entry_id = str(uuid.uuid4())

        result = await r.eval(
            _ACQUIRE_SCRIPT,
            1,
            _REDIS_KEY,
            str(now),
            str(window_start),
            str(_EFFECTIVE_RPM),
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
    async def __aenter__(self) -> "_RateLimitedSlot":
        await acquire_api_slot()
        return self

    async def __aexit__(self, *_) -> None:
        pass


api_sem = _RateLimitedSlot()
