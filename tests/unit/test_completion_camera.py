"""completion_camera_topic maps HAL RGB names — no ROS required.

Go2 cricket: reasoner defaulted to ``/openral/cameras/top/image`` while
``Go2MujocoHAL`` advertised ``/openral/cameras/front/image``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "openral_rskill_ros"
    / "openral_rskill_ros"
    / "completion_camera.py"
)
_spec = importlib.util.spec_from_file_location("completion_camera_under_test", _PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
completion_camera_topic = _mod.completion_camera_topic


def test_go2_front_wins() -> None:
    assert completion_camera_topic(["front"]) == "/openral/cameras/front/image"


def test_prefers_front_among_several() -> None:
    assert completion_camera_topic(["rear", "front"]) == "/openral/cameras/front/image"


def test_tabletop_keeps_first_name() -> None:
    assert completion_camera_topic(["top", "wrist_left"]) == "/openral/cameras/top/image"


def test_empty_keeps_documented_default() -> None:
    assert completion_camera_topic([]) == "/openral/cameras/top/image"
