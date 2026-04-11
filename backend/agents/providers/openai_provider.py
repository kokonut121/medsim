"""OpenAI LLM provider — gpt-4o-mini by default."""
from __future__ import annotations

import json

from openai import AsyncOpenAI

from backend.config import get_settings


class OpenAIProvider:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model
        self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
        max_tokens: int = 1000,
    ) -> dict | list:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
