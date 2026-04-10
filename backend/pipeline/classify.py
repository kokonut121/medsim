from __future__ import annotations

from collections.abc import Mapping


CATEGORIES = [
    "building_exterior",
    "lobby_main_entrance",
    "ed_entrance_ambulance_bay",
    "corridor_hallway",
    "nursing_station",
    "patient_room",
    "medication_room_pharmacy",
    "icu_bay",
    "operating_room",
    "utility_support",
    "other",
]


PLACES_CATEGORY_SEQUENCE = [
    "lobby_main_entrance",
    "corridor_hallway",
    "patient_room",
    "nursing_station",
    "medication_room_pharmacy",
    "icu_bay",
]


def _category_from_metadata(source: str, metadata: Mapping[str, object] | None = None) -> tuple[str, float]:
    metadata = metadata or {}
    if source == "street_view":
        heading = int(metadata.get("heading", 0))
        if heading in {135, 180, 225}:
            return "ed_entrance_ambulance_bay", 0.74
        return "building_exterior", 0.8

    if source == "places":
        index = int(metadata.get("index", 1))
        category = PLACES_CATEGORY_SEQUENCE[(index - 1) % len(PLACES_CATEGORY_SEQUENCE)]
        return category, 0.71

    if source == "supplemental_upload":
        return "patient_room", 0.69

    return "other", 0.6


async def classify_image(image_bytes: bytes, source: str, metadata: Mapping[str, object] | None = None) -> dict:
    category, confidence = _category_from_metadata(source, metadata)
    if category == "other":
        fingerprint = sum(image_bytes) % len(CATEGORIES) if image_bytes else 0
        category = CATEGORIES[fingerprint]
        confidence = round(0.65 + (fingerprint / max(len(CATEGORIES) - 1, 1)) * 0.2, 2)
    return {
        "category": category,
        "confidence": min(confidence, 0.98),
        "notes": f"Heuristic classification for {source}",
        "source": source,
    }
