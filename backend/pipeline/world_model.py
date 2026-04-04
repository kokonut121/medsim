from __future__ import annotations

import hashlib


async def generate_world_model(images: list[bytes], scene_graph: dict) -> dict:
    digest = hashlib.sha1(b"".join(images) or b"world-model").hexdigest()[:12]
    return {
        "world_id": f"world_{digest}",
        "splat_url": f"worlds/{digest}/scene.splat",
        "scene_manifest": scene_graph,
    }

