import pytest
import time
from unittest.mock import AsyncMock, patch
import backend.simulation.rate_limiter as _rl


@pytest.fixture(autouse=True)
def reset_redis_client():
    """각 테스트 전후로 Redis 전역 클라이언트를 초기화해 테스트 격리를 보장한다."""
    original = _rl._redis_client
    _rl._redis_client = None
    yield
    _rl._redis_client = original


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
    past_ts = str(time.time() - 59.0)
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
    """알 수 없는 provider는 즉시 빈 문자열을 반환한다."""
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
    """빈 reservation_id는 Redis를 호출하지 않는다."""
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
