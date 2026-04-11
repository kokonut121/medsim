"""
Patient Intake Embedder
=======================
Converts a patient intake record into a dense vector for storage in IRIS
and retrieval during crisis simulations via cosine similarity search.

Primary path: OpenAI text-embedding-3-small (1536 dims).
Fallback (no API key / OpenAI unavailable): deterministic keyword-hash
vector (128 dims) over medical terms — low fidelity but always available.
"""
from __future__ import annotations

import hashlib
import logging
import math

logger = logging.getLogger(__name__)

_EMBED_DIM = 1536
_FALLBACK_DIM = 128

# Keyword vocabulary for the fallback hasher — common trauma/emergency terms.
_VOCAB = [
    "stab", "wound", "chest", "abdomen", "head", "neck", "leg", "arm",
    "blunt", "trauma", "burn", "fracture", "cardiac", "arrest", "overdose",
    "fall", "crush", "gunshot", "laceration", "hemorrhage", "airway",
    "breathing", "circulation", "shock", "triage", "immediate", "delayed",
    "minor", "expectant", "critical", "severe", "moderate", "mild",
    "pediatric", "adult", "elderly", "male", "female",
    "intubation", "iv", "fluid", "blood", "oxygen", "cpr", "defibrillation",
    "surgery", "icu", "emergency", "ambulance", "mass", "casualty",
]


def _intake_text(chief_complaint: str, mechanism: str, severity: str) -> str:
    return (
        f"Emergency patient intake. "
        f"Chief complaint: {chief_complaint}. "
        f"Mechanism: {mechanism or 'unspecified'}. "
        f"Triage severity: {severity}."
    )


def _fallback_embed(text: str) -> list[float]:
    """128-dim keyword-presence vector, L2-normalised."""
    text_lower = text.lower()
    vec = [0.0] * _FALLBACK_DIM
    for i, kw in enumerate(_VOCAB):
        if kw in text_lower:
            vec[i % _FALLBACK_DIM] += 1.0
    # Add character-level hash buckets for coverage of unknown terms
    for word in text_lower.split():
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % _FALLBACK_DIM] += 0.5
    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def embed_intake(
    chief_complaint: str,
    mechanism: str,
    severity: str,
) -> list[float]:
    """Return an embedding vector for the intake text.

    Tries OpenAI first; falls back to the keyword hasher if the key is
    absent or the call fails.
    """
    text = _intake_text(chief_complaint, mechanism, severity)
    try:
        from backend.config import get_settings
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("no openai key")

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    except Exception as exc:
        logger.debug("OpenAI embedding unavailable (%s), using fallback", exc)
        return _fallback_embed(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (Python fallback)."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)
