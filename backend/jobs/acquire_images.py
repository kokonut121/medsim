from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.config import get_settings
from backend.db.iris_client import iris_client
from backend.db.r2_client import r2_client
from backend.models import ImageMeta
from backend.pipeline.classify import classify_image
from backend.pipeline.coverage import build_coverage_from_images
from backend.pipeline.fal_generator import fill_coverage_gaps, generate_floor_plan
from backend.pipeline.image_acquisition import fetch_osm_building, fetch_places_photos, fetch_street_view
from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.world_model import generate_world_model


def _image_key(facility_id: str, source: str, file_name: str) -> str:
    return f"facilities/{facility_id}/images/{source}/{uuid4().hex[:8]}-{file_name}"


async def acquire_images_for_facility(facility_id: str, address: str, *, model_id: str | None = None) -> dict:
    settings = get_settings()
    facility = iris_client.facilities[facility_id]
    model = iris_client.models.get(model_id) if model_id else iris_client.create_or_replace_model(facility_id, status="queued")
    iris_client.update_model(model.model_id, status="acquiring", failure_reason="")

    try:
        street_view, places_photos, osm = await asyncio.gather(
            fetch_street_view(facility.lat, facility.lng, settings.google_api_key),
            fetch_places_photos(facility.google_place_id, settings.google_api_key),
            fetch_osm_building(facility.lat, facility.lng),
        )
        all_images = street_view + places_photos
        if not all_images:
            raise RuntimeError("No public imagery was returned for this facility")

        uploaded_images: list[dict] = []
        for index, image in enumerate(all_images, start=1):
            key = _image_key(facility_id, image["source"], image["file_name"])
            r2_client.upload_bytes(key, image["bytes"], content_type=image["content_type"])
            image_meta = iris_client.write_image_meta(
                ImageMeta(
                    image_id=f"img_{uuid4().hex[:8]}",
                    facility_id=facility_id,
                    source=image["source"],
                    r2_key=key,
                    public_url=r2_client.public_url_for(key),
                    heading=image.get("heading"),
                    content_type=image["content_type"],
                    created_at=facility.created_at,
                )
            )
            uploaded_images.append(
                {
                    **image,
                    "image_id": image_meta.image_id,
                    "r2_key": image_meta.r2_key,
                    "public_url": image_meta.public_url,
                    "index": index,
                }
            )

        iris_client.update_model(model.model_id, status="classifying", source_image_count=len(uploaded_images))
        classified = await asyncio.gather(
            *[
                classify_image(
                    image["bytes"],
                    image["source"],
                    {"heading": image.get("heading"), "index": image["index"]},
                )
                for image in uploaded_images
            ]
        )
        for image, result in zip(uploaded_images, classified):
            iris_client.update_image_classification(
                image["image_id"],
                category=result["category"],
                confidence=result["confidence"],
                notes=result["notes"],
            )

        covered_areas, gap_areas = build_coverage_from_images(iris_client.list_images_for_facility(facility_id))
        iris_client.update_coverage(facility_id, covered_areas, gap_areas)

        # Fill coverage gaps with fal.ai-generated interior images
        if gap_areas:
            gap_images = await fill_coverage_gaps(
                [gap.area_id for gap in gap_areas],
                facility_name=facility.name,
            )
            for image in gap_images:
                key = _image_key(facility_id, image["source"], image["file_name"])
                r2_client.upload_bytes(key, image["bytes"], content_type=image["content_type"])
                image_meta = iris_client.write_image_meta(
                    ImageMeta(
                        image_id=f"img_{uuid4().hex[:8]}",
                        facility_id=facility_id,
                        source=image["source"],
                        r2_key=key,
                        public_url=r2_client.public_url_for(key),
                        content_type=image["content_type"],
                        category=image.get("category_hint"),
                        created_at=facility.created_at,
                    )
                )
                uploaded_images.append({
                    **image,
                    "image_id": image_meta.image_id,
                    "r2_key": image_meta.r2_key,
                    "public_url": image_meta.public_url,
                    "index": len(uploaded_images) + 1,
                })
                gap_class = {"category": image.get("category_hint") or "other", "confidence": 0.7, "notes": "fal.ai generated", "source": image["source"]}
                iris_client.update_image_classification(image_meta.image_id, category=gap_class["category"], confidence=gap_class["confidence"], notes=gap_class["notes"])
                classified.append(gap_class)

            # Rebuild coverage now that gaps are filled
            covered_areas, gap_areas = build_coverage_from_images(iris_client.list_images_for_facility(facility_id))
            iris_client.update_coverage(facility_id, covered_areas, gap_areas)

        iris_client.update_model(model.model_id, status="generating")
        scene_graph = await extract_scene_graph(classified, osm)

        # Generate floor plan diagram from scene graph
        floor_plan_bytes = await generate_floor_plan(scene_graph, facility_name=facility.name)
        floor_plan_key = f"facilities/{facility_id}/floor_plan.png"
        r2_client.upload_bytes(floor_plan_key, floor_plan_bytes, content_type="image/png")
        scene_graph["floor_plan_url"] = r2_client.public_url_for(floor_plan_key)

        world_model = await generate_world_model(
            uploaded_images,
            scene_graph,
            facility_id=facility_id,
            facility_name=facility.name,
        )
        saved_model = iris_client.write_world_model(facility_id, world_model, model_id=model.model_id)
        return {"facility_id": facility_id, "address": address, "model": saved_model}
    except Exception as exc:
        iris_client.update_model(model.model_id, status="failed", failure_reason=str(exc))
        raise
