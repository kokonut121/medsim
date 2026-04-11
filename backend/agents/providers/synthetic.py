"""Deterministic synthetic provider — no network calls, used for tests and fallback."""
from __future__ import annotations


class SyntheticProvider:
    """Returns empty findings — lets deterministic postchecks / rule fallbacks take over."""

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
        max_tokens: int = 1000,
    ) -> dict | list:
        return {"findings": []}

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        return ""
