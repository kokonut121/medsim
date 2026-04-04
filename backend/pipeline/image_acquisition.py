from __future__ import annotations

import httpx


STREET_VIEW_BASE = "https://maps.googleapis.com/maps/api/streetview"
HEADINGS = [0, 45, 90, 135, 180, 225, 270, 315]


async def fetch_street_view(lat: float, lng: float, api_key: str) -> list[bytes]:
    images: list[bytes] = []
    if not api_key:
        return [f"synthetic-street-view-{heading}".encode() for heading in HEADINGS]
    async with httpx.AsyncClient() as client:
        for heading in HEADINGS:
            response = await client.get(
                STREET_VIEW_BASE,
                params={
                    "location": f"{lat},{lng}",
                    "heading": heading,
                    "fov": 90,
                    "pitch": 0,
                    "size": "640x640",
                    "key": api_key,
                },
            )
            if response.status_code == 200:
                images.append(response.content)
    return images


async def fetch_places_photos(place_id: str, api_key: str, max_photos: int = 40) -> list[bytes]:
    if not api_key:
        return [f"synthetic-places-photo-{index}".encode() for index in range(min(6, max_photos))]
    async with httpx.AsyncClient() as client:
        details = await client.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "photos", "key": api_key},
        )
        photo_refs = [photo["photo_reference"] for photo in details.json()["result"].get("photos", [])][:max_photos]
        images: list[bytes] = []
        for reference in photo_refs:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/place/photo",
                params={"photo_reference": reference, "maxwidth": 1600, "key": api_key},
            )
            if response.status_code == 200:
                images.append(response.content)
        return images


async def fetch_osm_building(lat: float, lng: float) -> dict:
    query = f"""
    [out:json];
    (
      way["building"](around:100,{lat},{lng});
      relation["building"](around:100,{lat},{lng});
    );
    out body geom;
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {
                "elements": [
                    {
                        "type": "way",
                        "id": "synthetic-building",
                        "tags": {"building": "hospital", "building:levels": "5"},
                        "geometry": [
                            {"lat": lat, "lon": lng},
                            {"lat": lat + 0.001, "lon": lng},
                            {"lat": lat + 0.001, "lon": lng + 0.001},
                            {"lat": lat, "lon": lng + 0.001},
                        ],
                    }
                ]
            }

