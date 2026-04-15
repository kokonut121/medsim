#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.iris_client import iris_client  # noqa: E402
from backend.pipeline.video_ingest import ingest_video_file  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-ingest a local walkthrough video into MedSim and persist the analysis in IRIS.",
    )
    parser.add_argument("facility_id", help="Facility id, for example fac_demo")
    parser.add_argument("video_path", help="Absolute or relative path to the local walkthrough video")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=48,
        help="Maximum number of extracted frames after any 360-degree crops",
    )
    parser.add_argument(
        "--equirect-crops",
        type=int,
        default=0,
        help="Perspective crop windows per frame for equirectangular video (0 disables cropping)",
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Refresh the current model's scene graph and findings inputs without generating a new World Labs world",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="Explicit model id to refresh in analysis-only mode. Defaults to the unit's latest model.",
    )
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    video_path = Path(args.video_path).expanduser().resolve()

    if args.facility_id not in iris_client.facilities:
        raise SystemExit(f"Unknown facility: {args.facility_id}")
    if not video_path.exists() or not video_path.is_file():
        raise SystemExit(f"Video file not found: {video_path}")

    unit = iris_client.get_unit_for_facility(args.facility_id)

    if args.analysis_only:
        if args.model_id:
            model = iris_client.models.get(args.model_id)
            if model is None:
                raise SystemExit(f"Model not found: {args.model_id}")
            if model.unit_id != unit.unit_id:
                raise SystemExit(f"Model {args.model_id} does not belong to unit {unit.unit_id}")
        else:
            model = iris_client.get_model(unit.unit_id)
        target_model = iris_client.update_model(model.model_id, status="queued", failure_reason="")
    else:
        target_model = iris_client.create_or_replace_model(args.facility_id, status="queued")

    result = await ingest_video_file(
        args.facility_id,
        target_model.model_id,
        str(video_path),
        max_frames=args.max_frames,
        equirect_crops=args.equirect_crops,
        regenerate_world_model=not args.analysis_only,
    )

    print(f"facility_id={args.facility_id}")
    print(f"unit_id={result.unit_id}")
    print(f"model_id={result.model_id}")
    print(f"status={result.status}")
    print(f"source_image_count={result.source_image_count}")
    print(f"caption={result.caption or ''}")
    print(f"world_marble_url={result.world_marble_url or ''}")
    print(f"scene_graph_rooms={len((result.scene_graph_json.get('units') or [{}])[0].get('rooms', []))}")
    print(f"spatial_bundle_rooms={len((result.spatial_bundle_json or {}).get('rooms', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
