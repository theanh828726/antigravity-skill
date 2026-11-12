from __future__ import annotations

from typing import Any, Protocol

import anthropic

from ..config import Settings


class LLM(Protocol):
    async def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> Any: ...


class AnthropicLLM:
    """Gọi Claude qua Messages API. Fallback server-side bật mặc định cho các model hỗ trợ."""

    def __init__(self, s: Settings):
        self._s = s
        self._client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None)

    async def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> Any:
        kwargs: dict[str, Any] = dict(
            model=self._s.claude_model,
            max_tokens=16000,
            system=system,
            messages=messages,
            tools=tools,
            output_config={"effort": self._s.claude_effort},
            thinking={"type": "adaptive"},
        )
        if self._s.claude_use_fallbacks:
            return await self._client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        return await self._client.messages.create(**kwargs)
