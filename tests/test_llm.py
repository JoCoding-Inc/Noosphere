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
