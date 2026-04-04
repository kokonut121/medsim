from __future__ import annotations

import asyncio

from backend.config import get_settings
from backend.db.iris_client import iris_client
from backend.pipeline.classify import classify_image
from backend.pipeline.image_acquisition import fetch_osm_building, fetch_places_photos, fetch_street_view
from backend.pipeline.scene_graph import extract_scene_graph
from backend.pipeline.world_model import generate_world_model


async def acquire_images_for_facility(facility_id: str, address: str) -> dict:
    settings = get_settings()
    facility = iris_client.facilities[facility_id]
    lat, lng = facility.lat, facility.lng
    place_id = facility.google_place_id
    street_view, places_photos, osm = await asyncio.gather(
        fetch_street_view(lat, lng, settings.google_api_key),
        fetch_places_photos(place_id, settings.google_api_key),
        fetch_osm_building(lat, lng),
    )
    all_images = street_view + places_photos
    sources = ["street_view"] * len(street_view) + ["places"] * len(places_photos)
    classified = await asyncio.gather(*[classify_image(image, source) for image, source in zip(all_images, sources)])
    scene_graph = await extract_scene_graph(classified, osm)
    world_model = await generate_world_model(all_images, scene_graph)
    saved_model = iris_client.write_world_model(facility_id, world_model)
    return {"facility_id": facility_id, "address": address, "model": saved_model}

