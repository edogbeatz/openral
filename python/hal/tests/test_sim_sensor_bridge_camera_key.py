"""SimSensorBridge resolves camera obs-key via vla_feature_key suffix.

Also covers the dual-keying fallback (issue #88): a frame dict may be keyed by
the VLA slot (``camera1`` — SimAttachedHAL) or by the sensor name (``front`` —
the MujocoArmHAL bare/composed twin), and the bridge must resolve both.
"""

from __future__ import annotations

import inspect

import numpy as np
from openral_core import RobotDescription
from openral_hal.sim_sensor_bridge import (
    SimSensorBridge,
    _frame_for_camera,
    _obs_key_for_sensor,
    _publisher_has_subscribers,
    _rgb8_payload,
    _rgb_image_frame_id,
)


def test_franka_sensors_map_to_vla_feature_key_suffix() -> None:
    desc = RobotDescription.from_yaml("robots/franka_panda/robot.yaml")
    by_name = {s.name: s for s in desc.sensors if s.modality == "rgb"}
    assert _obs_key_for_sensor(by_name["top"]) == "camera1"
    assert _obs_key_for_sensor(by_name["wrist"]) == "camera2"


def test_so101_sensors_map_name_to_vla_slot() -> None:
    # so101's sensor names (top / wrist) differ from their VLA slots
    # (camera1 / camera2) — the mismatch that hid issue #88's frame lookup.
    desc = RobotDescription.from_yaml("robots/so101_follower/robot.yaml")
    by_name = {s.name: s for s in desc.sensors if s.modality == "rgb"}
    assert _obs_key_for_sensor(by_name["top"]) == "camera1"
    assert _obs_key_for_sensor(by_name["wrist"]) == "camera2"


def test_frame_lookup_prefers_vla_slot_key() -> None:
    # SimAttachedHAL keying: frames live under the VLA slot.
    cam1 = np.zeros((4, 4, 3), dtype=np.uint8)
    images = {"camera1": cam1, "camera2": np.ones((4, 4, 3), dtype=np.uint8)}
    assert _frame_for_camera(images, "camera1", "front") is cam1


def test_frame_lookup_falls_back_to_sensor_name() -> None:
    # MujocoArmHAL keying: composed/bare twin keys frames by sensor name, while
    # the bridge's obs_key is the VLA slot. The fallback must still resolve.
    front = np.zeros((4, 4, 3), dtype=np.uint8)
    images = {"front": front, "wrist": np.ones((4, 4, 3), dtype=np.uint8)}
    assert _frame_for_camera(images, "camera1", "front") is front


def test_frame_lookup_returns_none_when_absent() -> None:
    images = {"other": np.zeros((2, 2, 3), dtype=np.uint8)}
    assert _frame_for_camera(images, "camera1", "front") is None


def test_go2_image_and_camera_info_share_manifest_frame() -> None:
    """Image and CameraInfo must share the manifest TF frame, not the sensor name.

    Go2's sensor is ``front`` on topic ``/openral/cameras/front/image`` while
    its TF frame is ``front_camera``. Stamping the Image with ``front`` made
    Foxglove refuse the attached CameraInfo (``front_camera``) and left the
    Image panel black.
    """
    desc = RobotDescription.from_yaml("robots/go2/robot.yaml")
    front = next(s for s in desc.sensors if s.name == "front" and s.modality == "rgb")
    assert front.name == "front"
    assert front.frame_id == "front_camera"
    assert _rgb_image_frame_id(front) == "front_camera"
    assert _rgb_image_frame_id(front) == front.frame_id


def test_franka_top_image_uses_manifest_frame() -> None:
    """Franka's overhead camera is named ``top`` but lives in ``world``."""
    desc = RobotDescription.from_yaml("robots/franka_panda/robot.yaml")
    top = next(s for s in desc.sensors if s.name == "top" and s.modality == "rgb")
    assert top.name == "top"
    assert top.frame_id == "world"
    assert _rgb_image_frame_id(top) == "world"


def test_rgb8_payload_is_the_pixel_bytes() -> None:
    """Contiguous uint8 RGB becomes Image.data without a dtype copy."""
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    frame[0, 0] = (1, 2, 3)
    payload = _rgb8_payload(frame)
    assert payload[:3] == bytes((1, 2, 3))
    assert len(payload) == 12


def test_rgb8_payload_accepts_a_flipped_view() -> None:
    """A non-contiguous view (dashboard flip) still yields packed bytes."""
    frame = np.arange(2 * 2 * 3, dtype=np.uint8).reshape(2, 2, 3)
    payload = _rgb8_payload(frame[::-1, ::-1])
    assert len(payload) == 12
    # Last pixel of the original is first after a 180° flip.
    assert payload[:3] == bytes(frame[-1, -1])


class _Pub:
    def __init__(self, n: int) -> None:
        self._n = n

    def get_subscription_count(self) -> int:
        return self._n


def test_publisher_without_subscribers_is_skipped() -> None:
    assert _publisher_has_subscribers(_Pub(0)) is False
    assert _publisher_has_subscribers(_Pub(1)) is True


def test_publisher_count_fail_open_keeps_vla_fed() -> None:
    """A test double / missing API must not drop the raw Image."""
    assert _publisher_has_subscribers(object()) is True


def test_compressed_publish_is_native_jpeg_sibling() -> None:
    """Foxglove Image panels consume HAL JPEG, not a second image_transport encode."""
    src = inspect.getsource(SimSensorBridge._publish_compressed)
    assert "/openral/cameras/{name}/image/compressed" in src
    assert 'msg.format = "jpeg"' in src
    loop = inspect.getsource(SimSensorBridge._publish_images)
    assert "self._publish_compressed(name, stamp, msg.header.frame_id, thumb)" in loop
    assert "_publisher_has_subscribers(pub)" in loop
    assert "rotate_180=self._dashboard_flip_180" in loop
    assert "arr[::-1, ::-1]" not in loop
