"""Provider protocol — LLM backend abstraction for scan swarms and consensus."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
        max_tokens: int = 1000,
    ) -> dict | list:
        """Return a parsed JSON dict or list from the model."""
        ...

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        """Return raw text from the model."""
        ...
