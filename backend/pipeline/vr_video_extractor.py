from __future__ import annotations

"""
VR / 360-degree video frame extraction pipeline.

Accepts a local file path or an uploaded video (bytes) and extracts
a diverse set of frames suitable for World Labs Marble world-model generation.

Strategy
--------
1. Sample frames at regular intervals across the full video duration.
2. Score each candidate frame for sharpness (Laplacian variance) and
   brightness — blurry or dark frames are discarded.
3. Deduplicate visually similar consecutive frames using a perceptual
   hash (average hash on a downsampled greyscale thumbnail).
4. Return up to `max_frames` high-quality frames as JPEG bytes,
   formatted as the same dict schema used by image_acquisition.py so
   they drop straight into the acquire_images_for_facility pipeline.

For 360° / equirectangular video the extractor also splits each frame
into N horizontal crop windows (default 6) so World Labs receives
multiple perspective-like images per source frame rather than a single
wide equirectangular projection.
"""

import io
import math
import struct
from typing import Iterator

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Perceptual hash helpers
# ---------------------------------------------------------------------------

def _ahash(gray: np.ndarray, size: int = 8) -> int:
    """Average-hash: returns a 64-bit integer for a grayscale image."""
    small = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    mean = small.mean()
    bits = (small > mean).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return value


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def _is_equirectangular(width: int, height: int) -> bool:
    """
    2:1 aspect ratio is the canonical equirectangular standard, but YouTube
    360° videos are often delivered at 16:9 (1920×1080) with spherical
    metadata embedded in the container.  We therefore also accept any
    landscape video wider than 1920px as likely 360°.
    """
    ratio = width / height
    if abs(ratio - 2.0) < 0.15:
        return True
    # YouTube VR: delivered at 16:9 but > 1080p implies 360° content
    if abs(ratio - 16 / 9) < 0.05 and width >= 1920:
        return True
    return False


def _crop_windows(
    frame: np.ndarray,
    n_crops: int = 6,
) -> list[np.ndarray]:
    """
    Split an equirectangular frame into n_crops horizontal perspective-like
    windows covering 360° horizontally and ~90° vertically (centre strip).
    """
    h, w = frame.shape[:2]
    # Vertical: keep the middle 50% to avoid floor/ceiling noise
    y0 = h // 4
    y1 = 3 * h // 4
    strip = frame[y0:y1, :]

    crop_w = w // n_crops
    crops = []
    for i in range(n_crops):
        x0 = i * crop_w
        x1 = x0 + crop_w
        crops.append(strip[:, x0:x1])
    return crops


def extract_frames(
    video_source: str | bytes,
    *,
    max_frames: int = 20,
    min_sharpness: float = 80.0,
    min_brightness: float = 40.0,
    max_brightness: float = 230.0,
    dedup_threshold: int = 6,    # hamming distance — lower = stricter dedup
    target_long_edge: int = 1280,
    equirect_crops: int = 6,     # 0 = disable cropping
    force_360: bool = False,     # treat as equirectangular regardless of ratio
) -> list[dict]:
    """
    Extract representative frames from a VR/360 video.

    Parameters
    ----------
    video_source : str or bytes
        File path string OR raw video bytes.
    max_frames : int
        Maximum number of output images (after cropping).
    min_sharpness : float
        Laplacian variance threshold — blurry frames below this are skipped.
    min_brightness : float
        Mean pixel brightness lower bound (dark frames skipped).
    max_brightness : float
        Mean pixel brightness upper bound (over-exposed frames skipped).
    dedup_threshold : int
        Hamming distance for perceptual dedup — higher = keep more similar frames.
    target_long_edge : int
        Resize output images so the long edge is this many pixels.
    equirect_crops : int
        Number of horizontal crop windows for equirectangular frames (0 = skip).

    Returns
    -------
    list of dicts matching the schema from image_acquisition.py:
        {source, file_name, bytes, content_type, heading (optional)}
    """
    # ---- Open video ----
    if isinstance(video_source, bytes):
        arr = np.frombuffer(video_source, dtype=np.uint8)
        cap = cv2.VideoCapture()
        # Write to a temp path; cv2 VideoCapture doesn't read from memory directly
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_source)
            tmp_path = tmp.name
        cap = cv2.VideoCapture(tmp_path)
        _cleanup = tmp_path
    else:
        cap = cv2.VideoCapture(video_source)
        _cleanup = None

    if not cap.isOpened():
        if _cleanup:
            import os; os.unlink(_cleanup)
        raise ValueError(f"Cannot open video: {video_source if isinstance(video_source, str) else '<bytes>'}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    is_360 = force_360 or _is_equirectangular(width, height)

    # How many source frames to consider (sample uniformly)
    # We want at most max_frames final images; for 360 with crops, each source
    # frame produces equirect_crops images, so sample fewer source frames.
    effective_crops = equirect_crops if (is_360 and equirect_crops > 1) else 1
    source_target = math.ceil(max_frames / effective_crops) * 3  # 3× to allow rejects
    sample_step = max(1, total_frames // source_target)

    seen_hashes: list[int] = []
    output: list[dict] = []
    frame_index = 0

    while len(output) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, bgr = cap.read()
        if not ok:
            break
        frame_index += sample_step
        if frame_index >= total_frames:
            break

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Sharpness filter
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness < min_sharpness:
            continue

        # Brightness filter
        brightness = float(gray.mean())
        if not (min_brightness <= brightness <= max_brightness):
            continue

        # Perceptual dedup
        h = _ahash(gray)
        if any(_hamming(h, s) < dedup_threshold for s in seen_hashes):
            continue
        seen_hashes.append(h)

        # Split equirectangular into crops or keep as-is
        if is_360 and equirect_crops > 1:
            crops = _crop_windows(bgr, equirect_crops)
        else:
            crops = [bgr]

        for crop_idx, crop in enumerate(crops):
            if len(output) >= max_frames:
                break

            ch, cw = crop.shape[:2]
            if max(ch, cw) > target_long_edge:
                scale = target_long_edge / max(ch, cw)
                crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_AREA)

            # Encode to JPEG
            ok2, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok2:
                continue

            heading = None
            if is_360 and equirect_crops > 1:
                heading = round(crop_idx * (360 / equirect_crops))

            timestamp_s = frame_index / fps
            output.append({
                "source":       "vr_video",
                "file_name":    f"frame_{frame_index:06d}_crop{crop_idx}.jpg",
                "bytes":        buf.tobytes(),
                "content_type": "image/jpeg",
                "heading":      heading,
                "timestamp_s":  timestamp_s,
                "sharpness":    round(sharpness, 1),
            })

    cap.release()
    if _cleanup:
        import os
        try:
            os.unlink(_cleanup)
        except OSError:
            pass

    return output


# ---------------------------------------------------------------------------
# Convenience: extract + summarise
# ---------------------------------------------------------------------------

def extract_summary(frames: list[dict]) -> dict:
    """Return stats about an extraction result."""
    if not frames:
        return {"count": 0}
    sharpnesses = [f.get("sharpness", 0) for f in frames]
    headings    = sorted({f["heading"] for f in frames if f.get("heading") is not None})
    total_bytes = sum(len(f["bytes"]) for f in frames)
    return {
        "count":           len(frames),
        "total_bytes":     total_bytes,
        "avg_sharpness":   round(sum(sharpnesses) / len(sharpnesses), 1),
        "headings_deg":    headings,
        "is_360_detected": any(f.get("heading") is not None for f in frames),
    }
