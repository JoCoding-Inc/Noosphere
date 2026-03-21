import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_check_provider_key_openai_missing():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {}, clear=True):
        # Remove OPENAI_API_KEY if set
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                check_provider_key("openai")


def test_check_provider_key_openai_present():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        check_provider_key("openai")  # should not raise


def test_check_provider_key_anthropic_missing():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {}, clear=True):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                check_provider_key("anthropic")


def test_check_provider_key_gemini_missing():
    from backend.llm import check_provider_key
    with patch.dict(os.environ, {}, clear=True):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                check_provider_key("gemini")


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


async def test_complete_anthropic_text():
    """complete() returns content for Anthropic text response."""
    from backend.llm import complete
    import anthropic

    mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
    mock_text_block.text = "Anthropic says hi"

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_anthropic_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="anthropic",
            max_tokens=50,
        )
    assert result.content == "Anthropic says hi"
    assert result.tool_args is None


async def test_complete_anthropic_tool_call():
    """complete() extracts tool_args from Anthropic ToolUseBlock."""
    from backend.llm import complete
    import anthropic

    mock_tool_block = MagicMock(spec=anthropic.types.ToolUseBlock)
    mock_tool_block.name = "create_persona"
    mock_tool_block.input = {"name": "Bob", "role": "designer"}

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    tool = {"type": "function", "function": {"name": "create_persona", "description": "", "parameters": {"type": "object", "properties": {}}}}

    with patch("backend.llm._get_anthropic_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "gen persona"}],
            tier="mid",
            provider="anthropic",
            max_tokens=256,
            tools=[tool],
            tool_choice="create_persona",
        )
    assert result.tool_name == "create_persona"
    assert result.tool_args == {"name": "Bob", "role": "designer"}


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


async def test_complete_gemini_text():
    """complete() returns content for Gemini text response."""
    from backend.llm import complete

    mock_response = MagicMock()
    mock_response.text = "Gemini says hi"
    # Part with no function_call attribute
    mock_part = MagicMock(spec=[])  # no function_call attribute
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

    mock_aio = AsyncMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio = mock_aio

    with patch("backend.llm._get_gemini_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="gemini",
            max_tokens=50,
        )
    assert result.content == "Gemini says hi"
    assert result.tool_args is None


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
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
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
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="gemini",
            max_tokens=50,
        )
    assert result.tokens_used == 77


async def test_complete_anthropic_tokens_used_none_when_usage_missing():
    """Anthropic 응답에 usage 필드가 없으면 tokens_used는 None이다."""
    from backend.llm import complete
    import anthropic

    mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
    mock_text_block.text = "response"

    mock_response = MagicMock(spec=["content"])  # usage 속성 없음
    mock_response.content = [mock_text_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("backend.llm._get_anthropic_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="anthropic",
            max_tokens=50,
        )
    assert result.tokens_used is None


async def test_complete_gemini_tokens_used_none_when_usage_missing():
    """Gemini 응답에 usage_metadata 필드가 없으면 tokens_used는 None이다."""
    from backend.llm import complete

    mock_response = MagicMock(spec=["text", "candidates"])  # usage_metadata 속성 없음
    mock_response.text = "Gemini"
    mock_part = MagicMock(spec=[])
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

    mock_aio = AsyncMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio = mock_aio

    with patch("backend.llm._get_gemini_client", return_value=mock_client), \
         patch("backend.llm.acquire_api_slot", new_callable=AsyncMock), \
         patch("backend.llm.acquire_tpm_slot", new_callable=AsyncMock, return_value="res-id"), \
         patch("backend.llm.record_token_usage", new_callable=AsyncMock), \
         patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}):
        result = await complete(
            messages=[{"role": "user", "content": "hi"}],
            tier="low",
            provider="gemini",
            max_tokens=50,
        )
    assert result.tokens_used is None


def test_deep_strip_schema_keys():
    """_deep_strip_schema_keys removes additionalProperties/$schema and normalizes nullable unions."""
    from backend.llm import _deep_strip_schema_keys
    schema = {
        "type": "object",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "additionalProperties": False,
        "properties": {
            "nested": {
                "type": "object",
                "additionalProperties": True,
                "$schema": "ignored",
                "properties": {}
            },
            "nullable_field": {
                "type": ["string", "null"],
            },
        },
        "anyOf": [
            {"type": "string", "additionalProperties": False, "$schema": "x"},
            {"type": "number"},
        ],
    }
    result = _deep_strip_schema_keys(schema)
    assert "$schema" not in result
    assert "additionalProperties" not in result
    assert "$schema" not in result["properties"]["nested"]
    assert "additionalProperties" not in result["properties"]["nested"]
    assert result["type"] == "object"
    # anyOf list items are also stripped
    assert "additionalProperties" not in result["anyOf"][0]
    assert "$schema" not in result["anyOf"][0]
    # nullable union is flattened
    nullable_result = result["properties"]["nullable_field"]
    assert nullable_result["type"] == "string"
    assert nullable_result["nullable"] is True


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
