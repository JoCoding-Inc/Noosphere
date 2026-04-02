from __future__ import annotations
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

import openai
from backend.simulation.rate_limiter import acquire_api_slot, acquire_tpm_slot, record_token_usage

logger = logging.getLogger(__name__)

LLMTier = Literal["high", "mid", "low"]

_MODELS: dict[str, dict[str, str]] = {
    "openai": {"high": "gpt-5.4", "mid": "gpt-5.4-mini", "low": "gpt-5.4-nano"},
}

# Maximum output tokens per model
_MODEL_MAX_TOKENS: dict[str, int] = {
    "gpt-5.4":      32768,
    "gpt-5.4-mini": 16384,
    "gpt-5.4-nano":  8192,
}

_API_KEY_NAMES: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
}


@dataclass
class LLMResponse:
    content: str | None        # normalized text response
    tool_name: str | None      # name of tool called, if any
    tool_args: dict | None     # parsed tool arguments (plain dict)
    tokens_used: int | None = None  # actual tokens consumed (input + output)


class LLMToolRequired(Exception):
    """Raised when tool_choice named a specific tool but provider returned no tool call."""


class LLMRateLimitError(Exception):
    """Wraps each provider's rate limit exception."""


def check_provider_key(provider: str = "openai") -> None:
    """Raises ValueError if the required API key env var is not set."""
    key_name = _API_KEY_NAMES.get(provider)
    if key_name is None:
        raise ValueError(f"Unknown provider: {provider!r}")
    if not os.environ.get(key_name):
        raise ValueError(f"{key_name} not set")


async def complete(
    messages: list[dict],
    tier: LLMTier,
    provider: str = "openai",
    max_tokens: int = 8192,
    timeout: float = 120.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    response_format: dict | None = None,
) -> LLMResponse:
    """Call OpenAI."""
    check_provider_key("openai")
    model = _MODELS["openai"][tier]
    model_max = _MODEL_MAX_TOKENS.get(model)
    if model_max is not None:
        max_tokens = min(max_tokens, model_max)
    return await _complete_openai(messages, model, max_tokens, timeout, tools, tool_choice, response_format)


_openai_client: openai.AsyncOpenAI | None = None


def _get_openai_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        _openai_client = openai.AsyncOpenAI(api_key=api_key, timeout=None)
    return _openai_client


def _tool_choice_openai(tool_choice: str | None) -> str | dict:
    if tool_choice is None:
        return "auto"
    return {"type": "function", "function": {"name": tool_choice}}


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
        try:
            tool_args = json.loads(tc.function.arguments)
        except (json.JSONDecodeError, ValueError):
            tool_args = {}
        return LLMResponse(
            content=message.content,
            tool_name=tc.function.name,
            tool_args=tool_args,
            tokens_used=tokens_used,
        )
    if tool_choice is not None:
        raise LLMToolRequired(f"Expected tool call '{tool_choice}' but got none")
    return LLMResponse(content=message.content, tool_name=None, tool_args=None, tokens_used=tokens_used)


async def _complete_openai(
    messages: list[dict],
    model: str,
    max_tokens: int,
    timeout: float,
    tools: list[dict] | None,
    tool_choice: str | None,
    response_format: dict | None = None,
) -> LLMResponse:
    client = _get_openai_client()
    kwargs: dict = {"model": model, "max_completion_tokens": max_tokens, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = _tool_choice_openai(tool_choice)
    if response_format:
        kwargs["response_format"] = response_format

    reservation_id = await acquire_tpm_slot("openai", max_tokens)

    conn_attempts = 0  # track timeout/connection retries separately
    for attempt in range(4):
        await acquire_api_slot("openai")
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
        except (asyncio.TimeoutError, openai.APIConnectionError) as exc:
            conn_attempts += 1
            if conn_attempts >= 2:
                await record_token_usage("openai", actual_tokens=0, reservation_id=reservation_id)
                raise
            backoff = 5 * conn_attempts  # 5s first, 10s second
            logger.warning("OpenAI %s, retrying in %ds (attempt %d/2)",
                           type(exc).__name__, backoff, conn_attempts)
            await asyncio.sleep(backoff)
        except Exception:
            await record_token_usage("openai", actual_tokens=0, reservation_id=reservation_id)
            raise
    raise RuntimeError("Unreachable")
