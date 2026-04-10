"""
Tests for the VR / 360-degree video extraction pipeline.

Uses a synthetically generated video so no external files are required.
"""
from __future__ import annotations

import io
import math
import struct
import tempfile
import os

import cv2
import numpy as np
import pytest

from backend.pipeline.vr_video_extractor import (
    _ahash,
    _hamming,
    _is_equirectangular,
    _crop_windows,
    extract_frames,
    extract_summary,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic video generation
# ---------------------------------------------------------------------------

def _make_video_bytes(
    width: int = 640,
    height: int = 320,
    n_frames: int = 60,
    fps: float = 30.0,
    *,
    vary_content: bool = True,
) -> bytes:
    """
    Create an in-memory MP4 video with synthetic coloured frames.

    width=640, height=320 → 2:1 aspect ratio (equirectangular).
    Each frame has a different dominant hue so dedup keeps them.
    """
    buf = io.BytesIO()
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
    assert vw.isOpened(), "VideoWriter failed to open"

    for i in range(n_frames):
        if vary_content:
            hue = int((i / n_frames) * 180)
            hsv = np.full((height, width, 3), (hue, 200, 180), dtype=np.uint8)
            bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            # Add some texture so sharpness filter passes
            noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
            bgr = cv2.add(bgr, noise)
        else:
            bgr = np.full((height, width, 3), 128, dtype=np.uint8)
        vw.write(bgr)
    vw.release()

    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data


# ---------------------------------------------------------------------------
# Unit tests — helpers
# ---------------------------------------------------------------------------

def test_ahash_same_image():
    gray = np.zeros((64, 64), dtype=np.uint8)
    assert _ahash(gray) == _ahash(gray)


def test_hamming_identical():
    assert _hamming(0b1010, 0b1010) == 0


def test_hamming_all_different():
    assert _hamming(0xFF, 0x00) == 8


def test_is_equirectangular_true():
    assert _is_equirectangular(1280, 640)
    assert _is_equirectangular(3840, 1920)
    assert _is_equirectangular(640, 320)


def test_is_equirectangular_false():
    assert not _is_equirectangular(1920, 1080)   # 16:9
    assert not _is_equirectangular(1280, 720)    # 16:9


def test_crop_windows_count():
    frame = np.zeros((320, 640, 3), dtype=np.uint8)
    crops = _crop_windows(frame, n_crops=6)
    assert len(crops) == 6


def test_crop_windows_height():
    """Each crop should be half the original height (middle 50%)."""
    frame = np.zeros((320, 640, 3), dtype=np.uint8)
    crops = _crop_windows(frame, n_crops=4)
    for c in crops:
        assert c.shape[0] == 160  # 320 // 2


# ---------------------------------------------------------------------------
# Integration tests — extract_frames
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def equirect_video() -> bytes:
    """60-frame 640×320 (2:1) synthetic video."""
    return _make_video_bytes(width=640, height=320, n_frames=60, vary_content=True)


@pytest.fixture(scope="module")
def normal_video() -> bytes:
    """60-frame 640×480 (4:3) synthetic video — not equirectangular."""
    return _make_video_bytes(width=640, height=480, n_frames=60, vary_content=True)


def test_extract_returns_list(equirect_video):
    frames = extract_frames(equirect_video, max_frames=12, equirect_crops=4)
    assert isinstance(frames, list)
    assert len(frames) > 0


def test_extract_max_frames_respected(equirect_video):
    frames = extract_frames(equirect_video, max_frames=8, equirect_crops=2)
    assert len(frames) <= 8


def test_extract_frame_schema(equirect_video):
    frames = extract_frames(equirect_video, max_frames=6, equirect_crops=3)
    for f in frames:
        assert "source" in f
        assert "file_name" in f
        assert "bytes" in f
        assert "content_type" in f
        assert f["source"] == "vr_video"
        assert f["content_type"] == "image/jpeg"
        assert len(f["bytes"]) > 0


def test_extract_headings_set_for_360(equirect_video):
    """360° video should produce frames with heading annotations."""
    frames = extract_frames(equirect_video, max_frames=12, equirect_crops=6)
    headings = [f.get("heading") for f in frames if f.get("heading") is not None]
    assert len(headings) > 0, "Expected heading annotations for equirectangular video"


def test_extract_no_headings_for_normal(normal_video):
    """Standard (non-360) video should produce frames without headings."""
    frames = extract_frames(normal_video, max_frames=6, equirect_crops=6)
    headings = [f.get("heading") for f in frames if f.get("heading") is not None]
    assert len(headings) == 0, "Standard video should not have heading annotations"


def test_extract_crops_disabled(equirect_video):
    """equirect_crops=0 → no cropping, single frame output per sample."""
    frames = extract_frames(equirect_video, max_frames=4, equirect_crops=0)
    assert len(frames) <= 4
    headings = [f.get("heading") for f in frames if f.get("heading") is not None]
    assert len(headings) == 0


def test_extract_from_file(tmp_path):
    """extract_frames should also accept a file path string."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(_make_video_bytes(width=320, height=160, n_frames=30))
    frames = extract_frames(str(video_path), max_frames=6, equirect_crops=3)
    assert len(frames) > 0


def test_extract_jpeg_decodable(equirect_video):
    """Output bytes should be valid JPEG."""
    frames = extract_frames(equirect_video, max_frames=4, equirect_crops=2)
    for f in frames:
        arr = np.frombuffer(f["bytes"], dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        assert img is not None, f"Frame {f['file_name']} is not a valid JPEG"
        assert img.shape[2] == 3


def test_extract_invalid_bytes_raises():
    with pytest.raises((ValueError, Exception)):
        extract_frames(b"not a video at all", max_frames=5)


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

def test_extract_summary_empty():
    s = extract_summary([])
    assert s["count"] == 0


def test_extract_summary_fields(equirect_video):
    frames = extract_frames(equirect_video, max_frames=10, equirect_crops=4)
    s = extract_summary(frames)
    assert s["count"] == len(frames)
    assert s["total_bytes"] > 0
    assert s["avg_sharpness"] >= 0
    assert isinstance(s["is_360_detected"], bool)
