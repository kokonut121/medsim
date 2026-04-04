from __future__ import annotations

import json


async def extract_scene_graph(classified_images: list[dict], osm_topology: dict) -> dict:
    rooms = []
    for index, image in enumerate(classified_images[:6], start=1):
        room_type = image["category"] if image["category"] != "other" else "corridor_hallway"
        rooms.append(
            {
                "room_id": f"R{100 + index}",
                "type": room_type,
                "area_sqft_estimate": 120 + index * 20,
                "equipment": [
                    {
                        "type": "hand_hygiene_dispenser" if index % 2 else "crash_cart",
                        "position": f"north wall zone {index}",
                        "accessible": index % 3 != 0,
                        "confidence": image["confidence"],
                    }
                ],
                "adjacency": [f"R{99 + index}", f"R{101 + index}"] if index > 1 else [f"R{101 + index}"],
                "sightline_to_nursing_station": index % 2 == 0,
                "image_source_quality": image["source"],
            }
        )

    return {
        "units": [
            {
                "unit_id": "unit_generated",
                "unit_type": "MedSurg",
                "rooms": rooms,
            }
        ],
        "flow_annotations": {
            "patient_flow_paths": [["ENTRY", "R101", "R102"]],
            "staff_flow_paths": [["NURSING", "R101", "R103"]],
            "clean_corridors": ["CLEAN-C1"],
            "dirty_corridors": ["DIRTY-C1"],
            "osm_context": json.dumps(osm_topology)[:300],
        },
    }

