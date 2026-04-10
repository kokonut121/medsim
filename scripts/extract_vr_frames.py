"""Extract perspective views from a YouTube 360 video and ingest them into the world model pipeline.

Phase 1 (extract):
    Download the video with yt-dlp, grab the frame at t=<timestamp>s with
    ffmpeg, then reproject the equirectangular panorama into 12 rectilinear
    perspective views (8 eye-level headings + 4 pitched-down views). Writes
    JPEGs to scripts/vr_frames/<facility_id>/.

Phase 2 (ingest):
    Walk the staging dir and push each frame through the existing pipeline
    ingestion path: R2 upload -> iris_client.write_image_meta ->
    classify_image -> coverage update. Mirrors the per-image loop in
    backend/jobs/acquire_images.py:39-84.

Usage:
    python scripts/extract_vr_frames.py --facility-id fac_demo
    python scripts/extract_vr_frames.py --facility-id fac_demo --skip-ingest
    python scripts/extract_vr_frames.py --facility-id fac_demo --skip-extract

Note: IRIS is an in-memory dev stub (backend/db/iris_client.py). Running
this script in isolation populates its own process state only. If you want
the frames to be visible to a separately-running uvicorn backend, either run
this script in the same process or wire it up as a backend entrypoint.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# Make the script runnable as `python scripts/extract_vr_frames.py` from the
# project root by ensuring the repo root is on sys.path before we import any
# `backend.*` modules.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


UTC = timezone.utc

DEFAULT_URL = "https://www.youtube.com/watch?v=4--pyJLhlB0"
DEFAULT_TIMESTAMP = 25
DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "scripts" / "vr_frames"

# 8 eye-level headings match backend/pipeline/image_acquisition.py:9 (HEADINGS)
# so Marble sees the same azimuth grid it gets from Street View.
EYE_LEVEL_HEADINGS = [0, 45, 90, 135, 180, 225, 270, 315]
# 4 pitched-down views catch floor equipment / beds / ceiling edges.
PITCHED_HEADINGS = [0, 90, 180, 270]

PITCH_EYE = 0
PITCH_DOWN = -30
FOV_DEG = 90
OUTPUT_SIZE = (640, 640)  # matches Street View's size=640x640

FILENAME_RE = re.compile(
    r"^youtube-(?P<ts>\d+)s-h(?P<heading>\d{3})-p(?P<pitch>[+-]\d{2})\.jpg$"
)


# ---------- helpers ---------------------------------------------------------


def _build_view_spec() -> list[tuple[int, int]]:
    views: list[tuple[int, int]] = [(h, PITCH_EYE) for h in EYE_LEVEL_HEADINGS]
    views += [(h, PITCH_DOWN) for h in PITCHED_HEADINGS]
    return views


def _frame_filename(timestamp: int, heading: int, pitch: int) -> str:
    return f"youtube-{timestamp}s-h{heading:03d}-p{pitch:+03d}.jpg"


def _parse_frame_filename(name: str) -> tuple[int, int, int] | None:
    match = FILENAME_RE.match(name)
    if not match:
        return None
    return int(match.group("ts")), int(match.group("heading")), int(match.group("pitch"))


# ---------- Phase 1: extract ------------------------------------------------


def _require_ffmpeg() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        sys.exit(
            "error: ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`) and retry."
        )
    return binary


def _download_youtube(url: str, dest_stub: Path) -> Path:
    try:
        import yt_dlp
    except ImportError:
        sys.exit(
            "error: yt-dlp not installed. Run: pip install -r backend/requirements.txt"
        )

    options = {
        # Prefer a progressive MP4 so ffmpeg can seek cleanly on a single file.
        "format": "best[ext=mp4]/best",
        "outtmpl": str(dest_stub) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "overwrites": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return Path(filename)


def _extract_panorama(video: Path, timestamp: int, out: Path) -> None:
    ffmpeg = _require_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-ss", str(timestamp),
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed: {result.stderr.decode(errors='replace')}")


def _reproject_views(panorama_path: Path, output_dir: Path, timestamp: int) -> list[Path]:
    try:
        import numpy as np
        import py360convert
        from PIL import Image
    except ImportError:
        sys.exit(
            "error: py360convert/numpy/Pillow not installed. "
            "Run: pip install -r backend/requirements.txt"
        )

    panorama = np.array(Image.open(panorama_path).convert("RGB"))
    h, w = panorama.shape[:2]
    ratio = w / h
    print(
        f"[extract] panorama shape: {w}x{h} (ratio {ratio:.2f}). "
        f"Expect ~2.0 for equirectangular, ~1.5 for EAC."
    )
    if abs(ratio - 2.0) > 0.1:
        print(
            "[extract] WARNING: frame does not look equirectangular. "
            "Pitched views may be distorted. See plan's 'Known risks' section.",
            file=sys.stderr,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for heading, pitch in _build_view_spec():
        view = py360convert.e2p(
            panorama,
            fov_deg=FOV_DEG,
            u_deg=heading,
            v_deg=pitch,
            out_hw=OUTPUT_SIZE,
            in_rot_deg=0,
            mode="bilinear",
        )
        path = output_dir / _frame_filename(timestamp, heading, pitch)
        Image.fromarray(view.astype("uint8")).save(path, "JPEG", quality=90)
        written.append(path)
        print(f"[extract] wrote {path.relative_to(_REPO_ROOT)}")
    return written


def extract(url: str, timestamp: int, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        video_stub = tmp_dir / "source"
        print(f"[extract] downloading {url}")
        video_path = _download_youtube(url, video_stub)
        print(f"[extract] downloaded to {video_path}")
        panorama_path = tmp_dir / "panorama.jpg"
        print(f"[extract] snapping frame at t={timestamp}s")
        _extract_panorama(video_path, timestamp, panorama_path)
        print(f"[extract] reprojecting into {len(_build_view_spec())} perspective views")
        return _reproject_views(panorama_path, output_dir, timestamp)


# ---------- Phase 2: ingest -------------------------------------------------


async def ingest(facility_id: str, input_dir: Path, timestamp: int) -> None:
    # Lazy imports so Phase 1-only invocations don't need the backend env.
    from backend.db.iris_client import iris_client
    from backend.db.r2_client import r2_client
    from backend.jobs.acquire_images import _image_key
    from backend.models import ImageMeta
    from backend.pipeline.classify import classify_image
    from backend.pipeline.coverage import build_coverage_from_images

    if facility_id not in iris_client.facilities:
        sys.exit(
            f"error: facility_id {facility_id!r} not found in iris_client. "
            f"Known facilities: {list(iris_client.facilities)}"
        )

    frames = sorted(
        path for path in input_dir.glob("*.jpg") if _parse_frame_filename(path.name)
    )
    if not frames:
        sys.exit(
            f"error: no matching JPEGs in {input_dir}. "
            "Run without --skip-extract, or check --output-dir."
        )

    print(f"[ingest] pushing {len(frames)} frames into pipeline for facility {facility_id}")

    r2_enabled = r2_client.enabled
    if not r2_enabled:
        print(
            "[ingest] WARNING: R2 is not configured (r2_account_id/key/bucket empty). "
            "Frames will be registered in IRIS with file:// URLs so Phase 2 logic is "
            "still exercised, but Marble will not be able to fetch them. Set the R2 "
            "env vars in .env for real cloud ingestion."
        )

    uploaded: list[tuple[ImageMeta, bytes, int]] = []
    for path in frames:
        parsed = _parse_frame_filename(path.name)
        assert parsed is not None  # filter above guarantees this
        _, heading, pitch = parsed
        buffer = path.read_bytes()
        key = _image_key(facility_id, "supplemental_upload", path.name)

        if r2_enabled:
            r2_client.upload_bytes(key, buffer, content_type="image/jpeg")
            public_url = r2_client.public_url_for(key)
        else:
            public_url = path.resolve().as_uri()

        meta = iris_client.write_image_meta(
            ImageMeta(
                image_id=f"img_{uuid4().hex[:8]}",
                facility_id=facility_id,
                source="supplemental_upload",
                r2_key=key,
                public_url=public_url,
                heading=heading,
                content_type="image/jpeg",
                notes=f"youtube 360 frame t={timestamp}s pitch={pitch}",
                created_at=datetime.now(tz=UTC),
            )
        )
        uploaded.append((meta, buffer, heading))
        print(f"[ingest] registered {path.name} -> {meta.image_id}")

    print(f"[ingest] classifying {len(uploaded)} frames")
    classifications = await asyncio.gather(
        *[
            classify_image(buffer, "supplemental_upload", {"heading": heading, "pitch": None})
            for _, buffer, heading in uploaded
        ]
    )
    for (meta, _, _), result in zip(uploaded, classifications):
        iris_client.update_image_classification(
            meta.image_id,
            category=result["category"],
            confidence=result["confidence"],
            notes=result.get("notes") or meta.notes,
        )
        print(
            f"[ingest] classified {meta.image_id} -> "
            f"{result['category']} ({result['confidence']:.2f})"
        )

    covered, gaps = build_coverage_from_images(
        iris_client.list_images_for_facility(facility_id)
    )
    iris_client.update_coverage(facility_id, covered, gaps)
    print(
        f"[ingest] coverage updated: {len(covered)} covered areas, {len(gaps)} gap areas"
    )


# ---------- CLI -------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract VR 360 frames from YouTube and feed them into the world model pipeline.",
    )
    parser.add_argument(
        "--facility-id",
        required=True,
        help="Facility to attach extracted frames to (must exist in iris_client.facilities).",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"YouTube 360 URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--timestamp",
        type=int,
        default=DEFAULT_TIMESTAMP,
        help=f"Seconds into the video to snap the frame (default: {DEFAULT_TIMESTAMP})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Staging dir root; script writes to <output-dir>/<facility-id>/",
    )
    parser.add_argument("--skip-extract", action="store_true", help="Skip Phase 1 (extract)")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip Phase 2 (ingest)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    target_dir = args.output_dir / args.facility_id

    if args.skip_extract and args.skip_ingest:
        sys.exit("error: nothing to do (--skip-extract and --skip-ingest both set)")

    if not args.skip_extract:
        extract(args.url, args.timestamp, target_dir)
    else:
        print("[extract] skipped")

    if not args.skip_ingest:
        asyncio.run(ingest(args.facility_id, target_dir, args.timestamp))
    else:
        print("[ingest] skipped")


if __name__ == "__main__":
    main()
