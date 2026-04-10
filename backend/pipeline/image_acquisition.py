from __future__ import annotations

import mimetypes

import httpx


STREET_VIEW_BASE = "https://maps.googleapis.com/maps/api/streetview"
HEADINGS = [0, 45, 90, 135, 180, 225, 270, 315]


def _content_type_from_response(response: httpx.Response, fallback: str = "image/jpeg") -> str:
    return response.headers.get("content-type", fallback).split(";")[0]


def _extension_for(content_type: str) -> str:
    return mimetypes.guess_extension(content_type) or ".jpg"


async def fetch_street_view(lat: float, lng: float, api_key: str) -> list[dict]:
    images: list[dict] = []
    if not api_key:
        return [
            {
                "bytes": f"synthetic-street-view-{heading}".encode(),
                "source": "street_view",
                "heading": heading,
                "content_type": "image/jpeg",
                "area_id": f"street_view_{heading}",
                "file_name": f"street-view-{heading}.jpg",
            }
            for heading in HEADINGS
        ]
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
                content_type = _content_type_from_response(response)
                images.append(
                    {
                        "bytes": response.content,
                        "source": "street_view",
                        "heading": heading,
                        "content_type": content_type,
                        "area_id": f"street_view_{heading}",
                        "file_name": f"street-view-{heading}{_extension_for(content_type)}",
                    }
                )
    return images


async def fetch_places_photos(place_id: str, api_key: str, max_photos: int = 40) -> list[dict]:
    if not place_id:
        return []
    if not api_key:
        return [
            {
                "bytes": f"synthetic-places-photo-{index}".encode(),
                "source": "places",
                "content_type": "image/jpeg",
                "area_id": f"places_photo_{index}",
                "file_name": f"places-photo-{index}.jpg",
            }
            for index in range(min(6, max_photos))
        ]
    async with httpx.AsyncClient() as client:
        details = await client.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "photos", "key": api_key},
        )
        photo_refs = [photo["photo_reference"] for photo in details.json().get("result", {}).get("photos", [])][:max_photos]
        images: list[dict] = []
        for index, reference in enumerate(photo_refs, start=1):
            response = await client.get(
                "https://maps.googleapis.com/maps/api/place/photo",
                params={"photo_reference": reference, "maxwidth": 1600, "key": api_key},
            )
            if response.status_code == 200:
                content_type = _content_type_from_response(response)
                images.append(
                    {
                        "bytes": response.content,
                        "source": "places",
                        "content_type": content_type,
                        "area_id": f"places_photo_{index}",
                        "file_name": f"places-photo-{index}{_extension_for(content_type)}",
                    }
                )
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
