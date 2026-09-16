"""Go2 + Z1 composite twin: the arm rides the dog and the dog still stands.

The composite is the first in-tree robot whose actuators are not homogeneous —
torque `<motor>` legs driven by a software PD loop alongside the Z1's position
servos — so this suite pins the split and the joint ORDER the whole stack
depends on.

Real menagerie assets, real MuJoCo, real `build_hal` (CLAUDE.md §1.11). The
MJCF is composed here the way `ManifestHALLifecycleNode` composes it from the
manifest's `scene_defaults.composition`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from openral_core import RobotDescription

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO / "robots" / "go2_z1" / "robot.yaml"

pytest.importorskip("mujoco")
pytest.importorskip("robot_descriptions")


def _composed_hal(*, gravity: bool):
    """Build the composite HAL over a freshly composed MJCF."""
    from openral_hal import build_hal
    from openral_sim.scene_composers import compose_mounted_arm_mjcf

    description = RobotDescription.from_yaml(str(_MANIFEST))
    composition = description.scene_defaults.composition
    assert composition is not None, "go2_z1 must declare its arm composition"
    xml, meshdir = compose_mounted_arm_mjcf(**composition.params)  # type: ignore[arg-type]  # reason: manifest params are the composer's kwargs
    path = meshdir.parent / "go2_z1_test_scene.xml"
    path.write_text(xml)
    hal = build_hal(
        description,
        mode="sim",
        transport={"gravity_enabled": gravity, "mjcf_path": str(path)},
    )
    return description, hal


def test_manifest_joint_order_puts_the_legs_first() -> None:
    """A 12-DoF locomotion policy must keep addressing the same 12 joints.

    The Go2's legs occupy indices 0-11 exactly as in `robots/go2`, so the
    rsl-rl velocity policy's action lands where it always did and the safety
    envelope's per-index limits still describe the joint they were written for.
    """
    composite = RobotDescription.from_yaml(str(_MANIFEST))
    go2 = RobotDescription.from_yaml(str(_REPO / "robots" / "go2" / "robot.yaml"))

    names = [j.name for j in composite.joints]
    assert names[:12] == [j.name for j in go2.joints]
    assert names[12:] == [f"joint{i}" for i in range(1, 7)] + ["jointGripper"]

    # Leg limits are the same hardware and must not have drifted in the copy.
    for mine, theirs in zip(composite.joints[:12], go2.joints, strict=True):
        assert mine.position_limits == theirs.position_limits
        assert mine.effort_limit == theirs.effort_limit


def test_hal_connects_to_the_composed_model_with_every_joint() -> None:
    """`build_hal` must yield the 19-DoF composite, not the bare 12-DoF Go2."""
    from openral_hal.go2_z1 import Go2Z1MujocoHAL

    description, hal = _composed_hal(gravity=False)
    assert isinstance(hal, Go2Z1MujocoHAL)
    hal.connect()
    try:
        state = hal.read_state()
        assert len(state.position) == len(description.joints) == 19
    finally:
        hal.disconnect()


def test_composite_stands_under_gravity_with_the_arm_aboard() -> None:
    """The carrier holds a stand while idle-stepping with the arm's mass on it."""
    _, hal = _composed_hal(gravity=True)
    hal.connect()
    try:
        spawn_z = hal.base_pose_6dof()[0][2]
        assert spawn_z > 0.20, f"spawned collapsed at {spawn_z}"
        for _ in range(1500):  # 3 s of idle PD hold
            hal.idle_step()
        settled_z = hal.base_pose_6dof()[0][2]
        assert settled_z > 0.10, f"collapsed under the arm: {spawn_z} -> {settled_z}"
    finally:
        hal.disconnect()


def test_arm_joints_take_position_targets_not_torques() -> None:
    """The Z1's servos must receive the radians target verbatim.

    The legs' PD law computes a TORQUE. Writing that into a position servo's
    ctrl would be read as a radians target of ~20 rad and slam the arm into
    its stops, so the per-joint split is the safety-relevant part of this HAL.
    """
    from openral_hal.go2_z1 import GO2_Z1_ARM_HOME

    _, hal = _composed_hal(gravity=False)
    hal.connect()
    try:
        hal.idle_step()
        # Reaching into _data is deliberate: the actuator write IS the contract.
        arm_ctrl = np.asarray(hal._data.ctrl[12:19])
        np.testing.assert_allclose(arm_ctrl, GO2_Z1_ARM_HOME, atol=1e-6)
    finally:
        hal.disconnect()
