from __future__ import annotations
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

import anthropic as _anthropic
import openai
from backend.simulation.rate_limiter import acquire_api_slot

logger = logging.getLogger(__name__)

LLMTier = Literal["high", "mid", "low"]

_MODELS: dict[str, dict[str, str]] = {
    "openai":    {"high": "gpt-5.4",          "mid": "gpt-5.4-mini",       "low": "gpt-5.4-nano"},
    "anthropic": {"high": "claude-opus-4-6",   "mid": "claude-sonnet-4-6",  "low": "claude-haiku-4-5-20251001"},
    "gemini":    {"high": "gemini-2.5-pro",    "mid": "gemini-2.0-flash",   "low": "gemini-2.0-flash-lite"},
}

_API_KEY_NAMES: dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini":    "GEMINI_API_KEY",
}


@dataclass
class LLMResponse:
    content: str | None        # normalized text response
    tool_name: str | None      # name of tool called, if any
    tool_args: dict | None     # parsed tool arguments (plain dict)


class LLMToolRequired(Exception):
    """Raised when tool_choice named a specific tool but provider returned no tool call."""


class LLMRateLimitError(Exception):
    """Wraps each provider's rate limit exception."""


def check_provider_key(provider: str) -> None:
    """Raises ValueError if the required API key env var is not set."""
    key_name = _API_KEY_NAMES.get(provider)
    if key_name is None:
        raise ValueError(f"Unknown provider: {provider!r}")
    if not os.environ.get(key_name):
        raise ValueError(f"{key_name} not set")


async def complete(
    messages: list[dict],
    tier: LLMTier,
    provider: str,
    max_tokens: int,
    timeout: float = 120.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
) -> LLMResponse:
    """Route LLM call to the appropriate provider."""
    check_provider_key(provider)
    model = _MODELS[provider][tier]

    if provider == "openai":
        return await _complete_openai(messages, model, max_tokens, timeout, tools, tool_choice)
    if provider == "anthropic":
        return await _complete_anthropic(messages, model, max_tokens, timeout, tools, tool_choice)
    if provider == "gemini":
        return await _complete_gemini(messages, model, max_tokens, timeout, tools, tool_choice)
    raise ValueError(f"Unknown provider: {provider!r}")


_openai_client: openai.AsyncOpenAI | None = None


def _get_openai_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        _openai_client = openai.AsyncOpenAI(api_key=api_key, timeout=60.0)
    return _openai_client


def _tool_choice_openai(tool_choice: str | None) -> str | dict:
    if tool_choice is None:
        return "auto"
    return {"type": "function", "function": {"name": tool_choice}}


def _extract_openai_response(response, tool_choice: str | None) -> LLMResponse:
    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        tc = tool_calls[0]
        return LLMResponse(
            content=message.content,
            tool_name=tc.function.name,
            tool_args=json.loads(tc.function.arguments),
        )
    if tool_choice is not None:
        raise LLMToolRequired(f"Expected tool call '{tool_choice}' but got none")
    return LLMResponse(content=message.content, tool_name=None, tool_args=None)


async def _complete_openai(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> LLMResponse:
    client = _get_openai_client()
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = _tool_choice_openai(tool_choice)

    for attempt in range(4):
        await acquire_api_slot()
        try:
            response = await client.chat.completions.create(**kwargs)
            return _extract_openai_response(response, tool_choice)
        except LLMToolRequired:
            raise
        except openai.RateLimitError:
            if attempt == 3:
                raise LLMRateLimitError("OpenAI rate limit exceeded")
            wait = 5 * (2 ** attempt)
            logger.warning("OpenAI rate limit, retrying in %ds", wait)
            await asyncio.sleep(wait)
    raise RuntimeError("Unreachable")


_anthropic_client: _anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> _anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        _anthropic_client = _anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0)
    return _anthropic_client


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-format tools to Anthropic format."""
    result = []
    for t in tools:
        fn = t["function"]
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn["parameters"],
        })
    return result


def _tool_choice_anthropic(tool_choice: str | None) -> dict:
    if tool_choice is None:
        return {"type": "auto"}
    return {"type": "tool", "name": tool_choice}


def _extract_anthropic_response(response, tool_choice: str | None) -> LLMResponse:
    tool_block = next(
        (b for b in response.content if isinstance(b, _anthropic.types.ToolUseBlock)),
        None
    )
    if tool_block is not None:
        return LLMResponse(
            content=None,
            tool_name=tool_block.name,
            tool_args=dict(tool_block.input),
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
    )


async def _complete_anthropic(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
) -> LLMResponse:
    client = _get_anthropic_client()

    # Extract system messages; Anthropic uses a separate `system` param
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

    for attempt in range(4):
        try:
            response = await client.messages.create(**kwargs)
            return _extract_anthropic_response(response, tool_choice)
        except LLMToolRequired:
            raise
        except _anthropic.RateLimitError:
            if attempt == 3:
                raise LLMRateLimitError("Anthropic rate limit exceeded")
            wait = 5 * (2 ** attempt)
            logger.warning("Anthropic rate limit, retrying in %ds", wait)
            await asyncio.sleep(wait)
    raise RuntimeError("Unreachable")


async def _complete_gemini(messages, model, max_tokens, timeout, tools, tool_choice):
    raise NotImplementedError("Gemini provider not yet implemented")
