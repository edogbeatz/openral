"""MujocoArmHAL attachment heartbeat — empty set keeps the kernel gate fresh."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openral_core import RobotDescription
from openral_core.exceptions import ROSConfigError

from openral_hal._mujoco_attached import resolve_attached_mujoco_bodies

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "robots" / "go2_z1" / "robot.yaml"

pytest.importorskip("mujoco")
pytest.importorskip("robot_descriptions")


def test_resolve_empty_without_handles() -> None:
    by_id, bodies = resolve_attached_mujoco_bodies([], handles=None)
    assert by_id == {}
    assert bodies == frozenset()


def test_resolve_nonempty_without_handles_fails() -> None:
    stub = MagicMock()
    stub.object_id = "box"
    with pytest.raises(ROSConfigError, match="MuJoCo handles"):
        resolve_attached_mujoco_bodies([stub], handles=None)  # type: ignore[list-item]


def test_go2_z1_hal_exposes_attachment_heartbeat_api() -> None:
    """Bridge only starts /openral/attachment_state when these methods exist."""
    from openral_hal import build_hal
    from openral_sim.scene_composers import compose_mounted_arm_mjcf

    description = RobotDescription.from_yaml(str(_MANIFEST))
    composition = description.scene_defaults.composition
    assert composition is not None
    xml, meshdir = compose_mounted_arm_mjcf(**composition.params)  # type: ignore[arg-type]
    path = meshdir.parent / "go2_z1_attach_test_scene.xml"
    path.write_text(xml)
    hal = build_hal(
        description,
        mode="sim",
        transport={"gravity_enabled": False, "mjcf_path": str(path)},
    )
    assert callable(getattr(hal, "update_attached_objects", None))
    assert callable(getattr(hal, "read_attached_objects", None))
    assert callable(getattr(hal, "read_attached_body_ids", None))
    hal.connect()
    try:
        hal.update_attached_objects([])
        assert hal.read_attached_objects() == []
        assert hal.read_attached_body_ids() == frozenset()
    finally:
        hal.disconnect()
