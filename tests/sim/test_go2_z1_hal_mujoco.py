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

    # Leg limits are the same hardware and must not have drifted in the copy.
    for mine, theirs in zip(composite.joints[:12], go2.joints, strict=True):
        assert mine.position_limits == theirs.position_limits
        assert mine.effort_limit == theirs.effort_limit


def test_front_is_not_sim_rendered() -> None:
    """Snout stays declared for VLA matching; HAL must not pay a second EGL camera."""
    composite = RobotDescription.from_yaml(str(_MANIFEST))
    front = next(s for s in composite.sensors if s.name == "front")
    assert front.sim_render is False


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


def test_twelve_dof_locomotion_action_holds_the_arm_at_spawn() -> None:
    """A 12-D leg-only ActionChunk must not fold the Z1 toward joint=0.

    The reference is the SPAWN pose, not the menagerie `home`: a 12-D row leaves
    the arm on the sticky hold, and on a fresh connect that hold is whatever the
    twin spawned at (`GO2_Z1_SPAWN_JOINT_TARGETS`, i.e. `ready`).
    """
    from openral_core import Action, ControlMode
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY

    _, hal = _composed_hal(gravity=False)
    hal.connect()
    try:
        action = Action(
            control_mode=ControlMode.JOINT_POSITION,
            horizon=1,
            joint_targets=[list(GO2_HOME_JOINT_TARGETS)],
        )
        hal.send_action(action)
        arm_ctrl = np.asarray(hal._data.ctrl[12:19])
        np.testing.assert_allclose(arm_ctrl, GO2_Z1_ARM_READY, atol=1e-5)
        # Hold targets remember the padded 19-D row for idle_step.
        assert len(hal._hold_targets) == 19
        np.testing.assert_allclose(hal._hold_targets[12:], GO2_Z1_ARM_READY, atol=1e-9)
    finally:
        hal.disconnect()


def test_full_width_locomotion_cannot_walk_the_arm_off_hold() -> None:
    """Hold-padded 19-D walk rows with moving legs must not retarget the Z1."""
    from openral_core import Action, ControlMode
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY, GO2_Z1_SPAWN_JOINT_TARGETS

    _, hal = _composed_hal(gravity=True)
    hal.connect()
    try:
        drifted = list(GO2_Z1_SPAWN_JOINT_TARGETS)
        drifted[12:] = [0.5, 1.5, -1.0, -1.0, 1.0, -1.5, -0.5]
        for i in range(50):
            drifted[12] = 0.5 * float(np.sin(i / 5.0))
            legs = list(GO2_HOME_JOINT_TARGETS)
            legs[0] += 0.4  # off Hub stand → locomotion, not arm_ready
            action = Action(
                control_mode=ControlMode.JOINT_POSITION,
                horizon=1,
                joint_targets=[[*legs, *drifted[12:]]],
            )
            hal.send_action(action)
            for _ in range(3):
                hal.idle_step()
        arm_q = np.asarray(hal.read_state().position[12:19])
        np.testing.assert_allclose(arm_q[:6], GO2_Z1_ARM_READY[:6], atol=5e-2)
        np.testing.assert_allclose(hal._hold_targets[12:], GO2_Z1_ARM_READY, atol=1e-9)
    finally:
        hal.disconnect()


def test_arm_ready_then_walk_keeps_the_ready_pose() -> None:
    """Recalibrate / arm_ready 19-D must stick through locomotion + idle snaps."""
    from openral_core import Action, ControlMode
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY, GO2_Z1_SPAWN_JOINT_TARGETS

    _, hal = _composed_hal(gravity=True)
    hal.connect()
    try:
        ready = [*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY]
        hal.reset_to_pose(ready)
        np.testing.assert_allclose(hal._arm_hold_pose, GO2_Z1_ARM_READY, atol=1e-9)

        hal.send_action(
            Action(
                control_mode=ControlMode.JOINT_POSITION,
                horizon=1,
                joint_targets=[ready],
            )
        )
        np.testing.assert_allclose(
            hal.read_state().position[12:18], GO2_Z1_ARM_READY[:6], atol=5e-2
        )

        walk_legs = list(GO2_HOME_JOINT_TARGETS)
        walk_legs[1] = 1.15
        chased = list(GO2_Z1_SPAWN_JOINT_TARGETS)
        chased[12:] = [0.4, 0.2, -0.1, -0.8, 0.3, -0.2, -0.4]
        for i in range(40):
            chased[12] = 0.4 * float(np.sin(i / 3.0))
            hal.send_action(
                Action(
                    control_mode=ControlMode.JOINT_POSITION,
                    horizon=1,
                    joint_targets=[[*walk_legs, *chased[12:]]],
                )
            )
            hal.idle_step(wall_dt_s=0.02)
            hal.send_action(
                Action(
                    control_mode=ControlMode.JOINT_POSITION,
                    horizon=1,
                    joint_targets=[list(GO2_HOME_JOINT_TARGETS)],
                )
            )
            hal.idle_step()
        arm_q = np.asarray(hal.read_state().position[12:18])
        np.testing.assert_allclose(arm_q, GO2_Z1_ARM_READY[:6], atol=5e-2)
        np.testing.assert_allclose(hal._hold_targets[12:], GO2_Z1_ARM_READY, atol=1e-9)
        np.testing.assert_allclose(hal._arm_hold_pose, GO2_Z1_ARM_READY, atol=1e-9)
    finally:
        hal.disconnect()


def test_recalibrate_then_twelve_dof_walk_moves_legs_and_holds_arm() -> None:
    """After Recalibrate, 12-D walk actions must move calves/hips; arm stays ready.

    The sticky qpos snap is arm-only. Snapping all joints (or the free base)
    back to Hub stand after every ``send_action`` would leave Apply walk
    frozen in place.
    """
    from openral_core import Action, ControlMode
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY

    _, hal = _composed_hal(gravity=True)
    hal.connect()
    try:
        ready = [*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY]
        hal.reset_to_pose(ready)
        walk = list(GO2_HOME_JOINT_TARGETS)
        walk[0] = 0.45  # FL hip
        walk[1] = 1.45  # FL thigh
        walk[2] = -1.15  # FL calf
        for _ in range(40):
            hal.send_action(
                Action(
                    control_mode=ControlMode.JOINT_POSITION,
                    horizon=1,
                    joint_targets=[walk],
                )
            )
            hal.idle_step(wall_dt_s=0.02)
        q = list(hal.read_state().position)
        assert abs(q[0] - walk[0]) < 0.25, f"FL hip frozen at stand: {q[0]}"
        assert abs(q[1] - walk[1]) < 0.30, f"FL thigh frozen at stand: {q[1]}"
        assert abs(q[2] - walk[2]) < 0.30, f"FL calf frozen at stand: {q[2]}"
        assert abs(q[0] - GO2_HOME_JOINT_TARGETS[0]) > 0.20
        assert abs(q[1] - GO2_HOME_JOINT_TARGETS[1]) > 0.20
        np.testing.assert_allclose(q[12:18], GO2_Z1_ARM_READY[:6], atol=5e-2)
        xyz, _ = hal.base_pose_6dof()
        assert xyz[2] > 0.08, f"collapsed under walk snap: z={xyz[2]}"
    finally:
        hal.disconnect()


def test_arm_joints_take_position_targets_not_torques() -> None:
    """The Z1's servos must receive the radians target verbatim.

    The legs' PD law computes a TORQUE. Writing that into a position servo's
    ctrl would be read as a radians target of ~20 rad and slam the arm into
    its stops, so the per-joint split is the safety-relevant part of this HAL.
    """
    from openral_hal.go2_z1 import GO2_Z1_SPAWN_JOINT_TARGETS

    _, hal = _composed_hal(gravity=False)
    hal.connect()
    try:
        hal.idle_step()
        # Reaching into _data is deliberate: the actuator write IS the contract.
        # An idle tick holds the spawn pose, so ctrl must be those radians —
        # a torque would land here as a target of ~20 rad.
        arm_ctrl = np.asarray(hal._data.ctrl[12:19])
        np.testing.assert_allclose(arm_ctrl, GO2_Z1_SPAWN_JOINT_TARGETS[12:], atol=1e-6)
    finally:
        hal.disconnect()
