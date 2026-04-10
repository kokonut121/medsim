from __future__ import annotations

from collections import Counter

from backend.models import CoverageArea, GapArea, ImageMeta


REQUIRED_CATEGORIES = (
    "building_exterior",
    "lobby_main_entrance",
    "corridor_hallway",
    "patient_room",
    "nursing_station",
    "medication_room_pharmacy",
)


def build_coverage_from_images(images: list[ImageMeta]) -> tuple[list[CoverageArea], list[GapArea]]:
    by_area: dict[tuple[str, str, str | None], int] = Counter(
        (image.r2_key.rsplit("/", 1)[-1], image.source, image.category) for image in images
    )
    covered_areas = [
        CoverageArea(area_id=area_id, source=source, image_count=count, category=category)
        for (area_id, source, category), count in sorted(by_area.items())
    ]
    categories_present = {image.category for image in images if image.category}
    gap_areas = [
        GapArea(area_id=category, description=f"Additional imagery needed for {category.replace('_', ' ')}")
        for category in REQUIRED_CATEGORIES
        if category not in categories_present
    ]
    return covered_areas, gap_areas
