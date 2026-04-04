from __future__ import annotations


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


async def classify_image(image_bytes: bytes, source: str) -> dict:
    fingerprint = sum(image_bytes) % len(CATEGORIES) if image_bytes else 0
    category = CATEGORIES[fingerprint]
    confidence = round(0.65 + (fingerprint / max(len(CATEGORIES) - 1, 1)) * 0.3, 2)
    return {
        "category": category,
        "confidence": min(confidence, 0.98),
        "notes": f"Synthetic classification for {source}",
        "source": source,
    }

