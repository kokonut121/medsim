from __future__ import annotations

import httpx


GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode_facility(address: str, api_key: str) -> dict:
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required for facility geocoding")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(GEOCODE_URL, params={"address": address, "key": api_key})
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results", [])
    if not results:
        raise RuntimeError(f"Unable to geocode facility address: {address}")

    primary = results[0]
    geometry = primary.get("geometry", {}).get("location", {})
    return {
        "address": primary.get("formatted_address", address),
        "lat": geometry.get("lat"),
        "lng": geometry.get("lng"),
        "google_place_id": primary.get("place_id", ""),
    }
