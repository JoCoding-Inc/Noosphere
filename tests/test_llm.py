import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_check_provider_key_openai_missing():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {}, clear=True):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                check_provider_key("openai")


def test_check_provider_key_openai_present():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        check_provider_key("openai")  # should not raise


def test_check_provider_key_unknown_provider():
    from backend.llm import check_provider_key
    with pytest.raises(ValueError, match="Unknown provider"):
        check_provider_key("unknown")


async def test_complete_openai_text():
    """complete() returns LLMResponse with content for a text response."""
    from backend.llm import complete, LLMResponse

    mock_message = MagicMock()
    mock_message.content = "Hello world"
    mock_message.tool_calls = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=50,
        )
    assert isinstance(result, LLMResponse)
    assert result.content == "Hello world"
    assert result.tool_args is None


async def test_complete_openai_tool_call():
    """complete() returns tool_args when a tool call is present."""
    from backend.llm import complete

    mock_function = MagicMock()
    mock_function.name = "create_persona"
    mock_function.arguments = '{"name": "Alice", "role": "engineer"}'

    mock_tool_call = MagicMock()
    mock_tool_call.function = mock_function

    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = [mock_tool_call]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    tool = {"type": "function", "function": {"name": "create_persona", "description": "...", "parameters": {"type": "object", "properties": {}}}}

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "gen persona"}],
            tier="mid",
            provider="openai",
            max_tokens=256,
            tools=[tool],
            tool_choice="create_persona",
        )
    assert result.tool_name == "create_persona"
    assert result.tool_args == {"name": "Alice", "role": "engineer"}


async def test_complete_openai_tool_required_raises():
    """complete() raises LLMToolRequired when forced tool is not returned."""
    from backend.llm import complete, LLMToolRequired

    mock_message = MagicMock()
    mock_message.content = "I can't do that"
    mock_message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=mock_message)]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    tool = {"type": "function", "function": {"name": "create_persona", "description": "", "parameters": {}}}

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        with pytest.raises(LLMToolRequired):
            await complete(
                messages=[{"role": "user", "content": "gen persona"}],
                tier="mid",
                provider="openai",
                max_tokens=256,
                tools=[tool],
                tool_choice="create_persona",
            )


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
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
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
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=50,
        )
    assert result.tokens_used is None


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

    async def fake_acquire_api_slot(*args, **kwargs):
        call_order.append("api_slot_acquire")

    with patch("backend.llm._get_openai_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", side_effect=fake_acquire_api_slot), \
         patch("backend.llm.acquire_tpm_slot", side_effect=fake_acquire_tpm), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="openai",
            max_tokens=200,
        )
    assert call_order == ["tpm_acquire", "api_slot_acquire", "api_call"]


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
