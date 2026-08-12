"""Anthropic Claude API client — shared by all AI modules.

Lightweight wrapper around the Anthropic SDK. No LangChain.

Supports both:
- Global API key from .env (ANTHROPIC_API_KEY)
- Per-call API key (user-provided via API parameter)
"""

import logging
from typing import AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)

_anthropic_client = None


def _get_client(api_key: str | None = None):
    """Get or create an Anthropic client. Uses per-call key if provided."""
    import anthropic

    key = api_key or settings.ANTHROPIC_API_KEY
    if not key:
        raise ValueError("未配置 ANTHROPIC_API_KEY。请在 .env 中设置或通过 API 参数传入。")

    # Per-call key → always create a new client (avoids caching wrong key)
    if api_key:
        return anthropic.AsyncAnthropic(api_key=api_key)

    # Global key → reuse singleton
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=key)
    return _anthropic_client


async def chat_json(
    system_prompt: str,
    user_message: str,
    model: str = "claude-sonnet-5-20251001",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> str:
    """Send a prompt and get a JSON text response.

    Args:
        system_prompt: System-level instructions.
        user_message: The document content / user query.
        model: Claude model ID.
        max_tokens: Max tokens in response.
        temperature: 0.0-1.0.
        api_key: Optional per-call API key (overrides .env).

    Returns:
        Raw text response (expected to be valid JSON).
    """
    client = _get_client(api_key)

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text
    logger.info(
        "LLM call: model=%s tokens_in=%d tokens_out=%d",
        model, response.usage.input_tokens, response.usage.output_tokens,
    )
    return text


async def chat_json_stream(
    system_prompt: str,
    user_message: str,
    model: str = "claude-sonnet-5-20251001",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    api_key: str | None = None,
) -> AsyncGenerator[str, None]:
    """Send a prompt and stream the JSON response chunk by chunk."""
    client = _get_client(api_key)

    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
