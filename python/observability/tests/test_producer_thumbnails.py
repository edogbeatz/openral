"""Tests for ``openral_observability.producer.encode_frame_thumbnail``.

Feeds real ``openral_core.SensorFrame`` instances with various
encodings into the helper and asserts a valid JPEG byte string comes
back (or ``None`` for the encodings the dashboard can't render). No
mocks per CLAUDE.md §1.11; the helper goes through real Pillow.
"""

from __future__ import annotations

import io

from openral_core.schemas import FrameEncoding, SensorFrame
from openral_observability.producer import encode_frame_thumbnail


def _make_frame(encoding: FrameEncoding, *, w: int = 64, h: int = 48, data: bytes) -> SensorFrame:
    return SensorFrame(
        sensor_id="cam_top",
        stamp_monotonic_ns=0,
        stamp_wall_ns=0,
        encoding=encoding,
        width=w,
        height=h,
        channels=1 if encoding in {FrameEncoding.MONO8, FrameEncoding.DEPTH16} else 3,
        data=data,
    )


def _is_jpeg(b: bytes) -> bool:
    return b.startswith(b"\xff\xd8\xff")


def test_rgb8_frame_encodes_to_jpeg() -> None:
    w, h = 64, 48
    pixels = bytearray()
    for i in range(w * h):
        pixels.extend((i % 256, (i * 3) % 256, (i * 7) % 256))
    frame = _make_frame(FrameEncoding.RGB8, w=w, h=h, data=bytes(pixels))
    out = encode_frame_thumbnail(frame)
    assert out is not None
    assert _is_jpeg(out)
    assert len(out) < 10_000  # thumbnail is small


def test_bgr8_frame_swaps_channels_and_encodes() -> None:
    w, h = 64, 48
    pixels = bytearray()
    for i in range(w * h):
        pixels.extend((i % 256, (i * 3) % 256, (i * 7) % 256))
    frame = _make_frame(FrameEncoding.BGR8, w=w, h=h, data=bytes(pixels))
    out = encode_frame_thumbnail(frame)
    assert out is not None and _is_jpeg(out)


def test_mono8_frame_encodes_as_rgb_jpeg() -> None:
    w, h = 64, 48
    data = bytes(i % 256 for i in range(w * h))
    frame = _make_frame(FrameEncoding.MONO8, w=w, h=h, data=data)
    out = encode_frame_thumbnail(frame)
    assert out is not None and _is_jpeg(out)


def test_jpeg_input_passes_through_pipeline() -> None:
    # Build a real JPEG via PIL and feed it as encoding=jpeg. The source is
    # larger than the 480x360 cap so the thumbnail is genuinely downscaled.
    from PIL import Image

    img = Image.new("RGB", (1280, 960), color=(120, 200, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    frame = _make_frame(FrameEncoding.JPEG, w=1280, h=960, data=buf.getvalue())
    out = encode_frame_thumbnail(frame)
    assert out is not None and _is_jpeg(out)
    # Downscaled to the 480x360 cap.
    decoded = Image.open(io.BytesIO(out))
    assert (decoded.width, decoded.height) == (480, 360)


def test_depth16_returns_none() -> None:
    frame = _make_frame(FrameEncoding.DEPTH16, w=64, h=48, data=b"\x00" * (64 * 48 * 2))
    assert encode_frame_thumbnail(frame) is None


def test_missing_data_returns_none() -> None:
    frame = SensorFrame(
        sensor_id="cam_top",
        stamp_monotonic_ns=0,
        stamp_wall_ns=0,
        encoding=FrameEncoding.RGB8,
        width=64,
        height=48,
        channels=3,
        topic="/camera/image_raw",
    )
    assert encode_frame_thumbnail(frame) is None


def test_thumbnail_is_actually_a_thumbnail() -> None:
    """The target must sit BELOW the common camera size, or it is a no-op.

    ``PIL.Image.thumbnail`` only ever shrinks. The previous 640x480 @ q90
    target was therefore a no-op on the 640x480 bench cameras: every frame
    went to the dashboard at full resolution and near-lossless quality, at
    camera rate (WorldState's ``_on_image`` encodes on every callback),
    costing ~8 MB/s of base64 over OTLP and a full JPEG encode under the
    GIL in the deploy process. This is a dashboard card, not a policy
    input — no VLA reads it.
    """
    from openral_observability import producer

    assert producer._THUMB_MAX_WIDTH == 480
    assert producer._THUMB_MAX_HEIGHT == 360
    assert producer._THUMB_JPEG_QUALITY == 80
    # The guard that actually matters: strictly smaller than the 640x480
    # cameras this repo's deploy scenes bind, so the resize is real.
    assert producer._THUMB_MAX_WIDTH < 640
    assert producer._THUMB_MAX_HEIGHT < 480


def test_large_source_is_capped() -> None:
    from PIL import Image

    # 1280x960 RGB source -> fits within the 480x360 cap, aspect preserved.
    w, h = 1280, 960
    frame = _make_frame(FrameEncoding.RGB8, w=w, h=h, data=bytes([128, 64, 32] * (w * h)))
    out = encode_frame_thumbnail(frame)
    assert out is not None
    decoded = Image.open(io.BytesIO(out))
    assert decoded.width <= 480 and decoded.height <= 360
    assert (decoded.width, decoded.height) == (480, 360)


def test_go2_sized_source_is_capped_not_passed_through() -> None:
    """640x480 is the common deploy camera; the cap must still shrink it.

    ``PIL.Image.thumbnail`` is a no-op at-or-below the target. A 640x480
    cap on a 640x480 camera was the original bandwidth trap.
    """
    from PIL import Image

    w, h = 640, 480
    frame = _make_frame(FrameEncoding.RGB8, w=w, h=h, data=bytes([40, 80, 120] * (w * h)))
    out = encode_frame_thumbnail(frame)
    assert out is not None
    decoded = Image.open(io.BytesIO(out))
    assert (decoded.width, decoded.height) == (480, 360)


def test_sub_cap_source_is_not_upscaled() -> None:
    from PIL import Image

    # 160x120 source stays native; thumbnail() only ever shrinks.
    w, h = 160, 120
    frame = _make_frame(FrameEncoding.RGB8, w=w, h=h, data=bytes([10, 20, 30] * (w * h)))
    out = encode_frame_thumbnail(frame)
    assert out is not None
    decoded = Image.open(io.BytesIO(out))
    assert (decoded.width, decoded.height) == (160, 120)
