"""Sim tests for ``openral_hal.Go2MujocoHAL`` against real MuJoCo physics.

These tests load the ``mujoco_menagerie`` Unitree Go2 MJCF (via
``robot_descriptions.go2_mj_description``) and exercise the full HAL
lifecycle — connect → read_state → send_action → estop / disconnect —
against a real ``mj_step`` loop. No mocks.

The Go2 MJCF is a floating-base quadruped: 13 joints (1 FREE + 12
hinge) and 12 torque ``<motor>`` actuators. Unlike G1, menagerie
actuator names drop the ``_joint`` suffix (``FL_hip`` drives
``FL_hip_joint``). Like H1, the HAL wraps those motors in software PD
so ``Action.joint_targets`` stay position-shaped.

Gravity is disabled in every test: there is no gait / contact
controller, so the twin falls under gravity. Calf limits exclude 0 rad;
``sim.keyframe_index: 0`` loads the menagerie ``home`` stand for free-joint
height; actuated joints snap to Hub ``default_joint_pos``
``(hip ±0.1, thigh 0.9, calf -1.8)``. Tests never command calves to 0.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

# Go2 tests only need go2.py + MujocoArmHAL. The package __init__ imports
# SO-100 / lerobot siblings; skip that when lerobot is not installed.
try:
    import lerobot  # noqa: F401
except ImportError:
    _hal_pkg = ModuleType("openral_hal")
    _hal_pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "python/hal/src/openral_hal")]
    sys.modules.setdefault("openral_hal", _hal_pkg)

try:
    import mujoco
except Exception as exc:  # mujoco's eager renderer probe can raise non-ImportError types
    _MUJOCO_ERROR: str | None = str(exc)
else:
    _MUJOCO_ERROR = None

try:
    from robot_descriptions import go2_mj_description as _go2_desc

    _ = _go2_desc.MJCF_PATH
    _MJCF_ERROR: str | None = None
except Exception as exc:
    _MJCF_ERROR = str(exc)

from openral_core import (
    Action,
    ControlMode,
    EmbodimentKind,
    JointState,
    JointType,
    ROSCapabilityMismatch,
    ROSConfigError,
    ROSRuntimeError,
)
from openral_hal.go2 import (
    GO2_DESCRIPTION,
    GO2_HOME_JOINT_TARGETS,
    GO2_HUB_DEFAULT_JOINT_POS,
    Go2MujocoHAL,
)
from openral_hal.resolver import build_hal

pytestmark = [
    pytest.mark.sim,
    pytest.mark.skipif(
        _MUJOCO_ERROR is not None,
        reason=f"mujoco unavailable: {_MUJOCO_ERROR}",
    ),
    pytest.mark.skipif(
        _MJCF_ERROR is not None,
        reason=f"Go2 MJCF unavailable: {_MJCF_ERROR}",
    ),
]


_EXPECTED_GO2_JOINT_ORDER: list[str] = [
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
]
# Menagerie actuator names drop the ``_joint`` suffix (not a 1:1 name match).
_EXPECTED_GO2_ACTUATOR_ORDER: list[str] = [
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
]


# ── Schema-level checks (cheap; do not require connect) ───────────────────────


class TestGo2Description:
    def test_canonical_description_shape(self) -> None:
        desc = GO2_DESCRIPTION
        assert desc.name == "go2"
        assert desc.embodiment_kind == EmbodimentKind.QUADRUPED.value
        assert len(desc.joints) == 12
        assert all(j.joint_type == JointType.REVOLUTE.value for j in desc.joints)
        assert desc.hal.sim == "openral_hal.go2:Go2MujocoHAL"
        assert desc.hal.real is None
        assert desc.sim is not None
        assert desc.sim.keyframe_index == 0
        assert desc.sim.floating_base is True
        assert desc.assets.mjcf == "rd:go2_mj_description"
        assert desc.sensors[0].name == "front"
        assert desc.sensors[0].sim_placement is not None
        assert desc.sensors[0].sim_placement.parent_body == "base"
        assert desc.sensors[1].name == "top"
        assert desc.sensors[1].vla_feature_key is None
        assert desc.sensors[1].sim_placement is not None
        assert desc.sensors[1].sim_placement.parent_body == "base"

    def test_joint_names_match_menagerie_order(self) -> None:
        names = [j.name for j in GO2_DESCRIPTION.joints]
        assert names == _EXPECTED_GO2_JOINT_ORDER

    def test_capabilities_advertise_joint_position(self) -> None:
        modes = GO2_DESCRIPTION.capabilities.supported_control_modes
        assert ControlMode.JOINT_POSITION.value in modes

    def test_capabilities_advertise_quadruped_traits(self) -> None:
        caps = GO2_DESCRIPTION.capabilities
        assert "quadruped" in caps.locomotion
        assert caps.can_lift_kg == 8.0
        assert caps.has_lidar is False
        assert "go2" in caps.embodiment_tags
        assert "go2" in caps.supported_vla_embodiments

    def test_safety_envelope_requires_deadman(self) -> None:
        assert GO2_DESCRIPTION.safety.deadman_required is True

    def test_home_targets_sit_inside_limits(self) -> None:
        assert GO2_HOME_JOINT_TARGETS == GO2_HUB_DEFAULT_JOINT_POS
        assert GO2_HOME_JOINT_TARGETS[0] == pytest.approx(-0.1)
        assert GO2_HOME_JOINT_TARGETS[3] == pytest.approx(0.1)
        for joint, q in zip(GO2_DESCRIPTION.joints, GO2_HOME_JOINT_TARGETS, strict=True):
            assert joint.position_limits is not None
            lo, hi = joint.position_limits
            assert lo <= q <= hi, f"{joint.name} home {q} outside [{lo}, {hi}]"

    def test_real_hal_is_not_implemented(self) -> None:
        with pytest.raises(ROSCapabilityMismatch, match="real-hardware HAL"):
            build_hal(GO2_DESCRIPTION, mode="real")


# ── Menagerie XML schema invariants (catches upstream drift) ──────────────────


class TestMenagerieSchema:
    """Guard against silent ``mujoco_menagerie`` schema drift.

    The ``Go2MujocoHAL`` indexing assumes FREE + 12 hinge in FL/FR/RL/RR
    hip/thigh/calf order. Actuator *names* drop ``_joint``; the HAL
    still drives the 12 hinges in manifest order via ``actuator_trnid``.
    """

    def test_joint_count_and_floating_base(self) -> None:
        model = mujoco.MjModel.from_xml_path(_go2_desc.MJCF_PATH)
        assert model.njnt == 13
        assert int(model.jnt_type[0]) == int(mujoco.mjtJoint.mjJNT_FREE)

    def test_actuated_joint_order_matches_description(self) -> None:
        model = mujoco.MjModel.from_xml_path(_go2_desc.MJCF_PATH)
        names = [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(1, model.njnt)
        ]
        assert names == _EXPECTED_GO2_JOINT_ORDER

    def test_actuator_count_and_driven_joints(self) -> None:
        model = mujoco.MjModel.from_xml_path(_go2_desc.MJCF_PATH)
        assert model.nu == 12
        actuator_names = [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)
        ]
        assert actuator_names == _EXPECTED_GO2_ACTUATOR_ORDER
        for i, expected_jnt in enumerate(_EXPECTED_GO2_JOINT_ORDER):
            driven = int(model.actuator_trnid[i, 0])
            jnt_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, driven)
            assert jnt_name == expected_jnt


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def hal() -> Go2MujocoHAL:
    """Fresh Go2 HAL with gravity off and enough settle steps for PD."""
    return Go2MujocoHAL(gravity_enabled=False, settle_steps=3000)


def _home_action(overrides: dict[int, float] | None = None) -> Action:
    targets = list(GO2_HOME_JOINT_TARGETS)
    if overrides:
        for idx, value in overrides.items():
            targets[idx] = value
    return Action(
        control_mode=ControlMode.JOINT_POSITION,
        horizon=1,
        joint_targets=[targets],
        stamp_ns=time.time_ns(),
    )


# ── Go2-specific lifecycle / state ────────────────────────────────────────────


class TestGo2Lifecycle:
    def test_connect_loads_mujoco_model(self, hal: Go2MujocoHAL) -> None:
        hal.connect()
        try:
            assert hal._connected is True
            assert hal._model is not None
            assert hal._data is not None
            assert hal._model.nu == 12
            assert hal._model.njnt == 13
        finally:
            hal.disconnect()

    def test_build_hal_sim_returns_go2_mujoco(self) -> None:
        try:
            built = build_hal(GO2_DESCRIPTION, mode="sim")
        except ROSConfigError as exc:
            pytest.skip(str(exc))
        assert isinstance(built, Go2MujocoHAL)


class TestReadState:
    def test_returns_jointstate_with_12_joints(self, connected_hal: Go2MujocoHAL) -> None:
        state = connected_hal.read_state()
        assert isinstance(state, JointState)
        assert len(state.name) == 12
        assert state.name == [j.name for j in GO2_DESCRIPTION.joints]
        assert len(state.position) == 12
        assert len(state.velocity) == 12
        assert state.stamp_ns > 0

    def test_initial_positions_are_home(self, connected_hal: Go2MujocoHAL) -> None:
        state = connected_hal.read_state()
        for name, q, home in zip(state.name, state.position, GO2_HOME_JOINT_TARGETS, strict=True):
            assert abs(q - home) < 1e-3, f"{name} initial {q} != home {home}"

    def test_idle_step_holds_home_stand(self, connected_hal: Go2MujocoHAL) -> None:
        """Idle ticks must PD-hold Hub stand, not apply position-as-torque.

        ``go2_bench`` never sends an action. The deploy idle stepper used to
        leave ``ctrl`` at the home *angles*, which on torque motors folds
        calves into their stops (thigh ~2 rad, calf ~-2.72).
        """
        # 2000 * 0.002 s ≈ 4 s of idle — enough to reproduce the fold.
        for _ in range(2000):
            assert connected_hal.idle_step() is True
        state = connected_hal.read_state()
        for name, q, home in zip(state.name, state.position, GO2_HOME_JOINT_TARGETS, strict=True):
            assert abs(q - home) < 5e-2, f"{name} idle-drifted to {q:.4f} (home {home})"
        xyz, _quat = connected_hal.base_pose_6dof()
        assert xyz[2] > 0.2, f"base height {xyz[2]:.3f} m — folded, not standing"

    def test_reset_to_pose_then_idle_holds_home(self, connected_hal: Go2MujocoHAL) -> None:
        connected_hal.reset_to_pose(list(GO2_HOME_JOINT_TARGETS))
        for _ in range(500):
            assert connected_hal.idle_step() is True
        state = connected_hal.read_state()
        for name, q, home in zip(state.name, state.position, GO2_HOME_JOINT_TARGETS, strict=True):
            assert abs(q - home) < 5e-2, f"{name} after reset+idle {q:.4f} (home {home})"


class TestSendAction:
    def test_rejects_wrong_joint_count(self, connected_hal: Go2MujocoHAL) -> None:
        bad = Action(
            control_mode=ControlMode.JOINT_POSITION,
            horizon=1,
            joint_targets=[[0.0] * 11],
            stamp_ns=time.time_ns(),
        )
        with pytest.raises(ROSConfigError, match="12 joints"):
            connected_hal.send_action(bad)


class TestClosedLoopMujoco:
    """Real MuJoCo physics — command around the menagerie home, not zeros."""

    def test_send_action_holds_home_pose(self, connected_hal: Go2MujocoHAL) -> None:
        connected_hal.send_action(_home_action())
        state = connected_hal.read_state()
        for i, (q, home) in enumerate(zip(state.position, GO2_HOME_JOINT_TARGETS, strict=True)):
            assert abs(q - home) < 5e-3, f"joint {state.name[i]!r} drifted to {q:.4f}"

    def test_front_left_thigh_converges(self, connected_hal: Go2MujocoHAL) -> None:
        # FL thigh home is 0.9; offset to 1.0 (inside front-thigh limits).
        connected_hal.send_action(_home_action({1: 1.0}))
        state = connected_hal.read_state()
        assert state.position[1] == pytest.approx(1.0, abs=8e-2)
        for i in (0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
            assert abs(state.position[i] - GO2_HOME_JOINT_TARGETS[i]) < 8e-2, (
                f"joint {state.name[i]!r} moved away from home"
            )


class TestFrontCamera:
    """Spliced front RGB must render a readable scene, not a flat gray slab."""

    def test_front_frame_has_textured_ground(self, connected_hal: Go2MujocoHAL) -> None:
        import numpy as np

        frames = connected_hal.read_images()
        assert "front" in frames
        img = np.asarray(frames["front"])
        assert img.shape == (480, 640, 3)
        # The old camrig floor was a finite flat-gray patch under a black void.
        # Foxglove's Image panel swallowed the void and the remaining slab
        # looked like a zoomed-in close-up. Checker + skybox must produce
        # spatial variation on the ground and a non-black sky.
        top = img[: img.shape[0] // 2]
        bot = img[img.shape[0] // 2 :].mean(axis=2)
        assert float(bot.max() - bot.min()) > 40.0  # light vs dark tiles
        assert float(top.mean()) > 20.0  # skybox, not void that Foxglove swallows

    def test_top_frame_shows_the_robot(self, connected_hal: Go2MujocoHAL) -> None:
        import numpy as np

        frames = connected_hal.read_images()
        assert "top" in frames
        img = np.asarray(frames["top"])
        assert img.shape == (480, 640, 3)
        # Third-person view: the robot occupies the centre. A sky/floor-only
        # frame is cooler and darker there than the light-gray Go2 mesh.
        center = img[200:280, 280:360]
        assert float(center.mean()) > 90.0


class TestGo2BaseProprio:
    """1-197 / 1-198 — floating-base pose/twist + Hub stand after connect()."""

    def test_base_pose_requires_connect(self, hal: Go2MujocoHAL) -> None:
        with pytest.raises(ROSRuntimeError, match="base_pose_6dof"):
            _ = hal.base_pose_6dof()
        with pytest.raises(ROSRuntimeError, match="base_twist"):
            _ = hal.base_twist

    def test_base_pose_6dof_identity_stand(self, connected_hal: Go2MujocoHAL) -> None:
        xyz, quat_xyzw = connected_hal.base_pose_6dof()
        assert len(xyz) == 3
        assert xyz[2] > 0.2  # menagerie home free-joint height
        qx, qy, qz, qw = quat_xyzw
        # Identity-ish stand: projected gravity ≈ [0, 0, -1].
        assert abs(qx) < 0.05
        assert abs(qy) < 0.05
        assert abs(qz) < 0.05
        assert qw == pytest.approx(1.0, abs=0.05)
        x, y, yaw = connected_hal.base_pose
        assert x == pytest.approx(xyz[0], abs=1e-6)
        assert y == pytest.approx(xyz[1], abs=1e-6)
        assert abs(yaw) < 0.1

    def test_base_twist_is_six_tuple_at_rest(self, connected_hal: Go2MujocoHAL) -> None:
        twist = connected_hal.base_twist
        assert len(twist) == 6
        assert all(abs(v) < 1e-3 for v in twist)

    def test_hips_match_hub_after_connect(self, connected_hal: Go2MujocoHAL) -> None:
        state = connected_hal.read_state()
        assert state.position[0] == pytest.approx(-0.1, abs=1e-3)
        assert state.position[3] == pytest.approx(0.1, abs=1e-3)
        assert tuple(state.position) == pytest.approx(GO2_HUB_DEFAULT_JOINT_POS, abs=1e-3)
