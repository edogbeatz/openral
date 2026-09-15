"""HAL adapter for the Unitree Go2 quadruped (MuJoCo digital twin).

Wraps the upstream DeepMind ``mujoco_menagerie`` Go2 MJCF
(``unitree_go2/go2.xml``, vendored via ``robot_descriptions``) as an
``openral_hal.HAL`` Protocol implementation, following the same
``MujocoArmHAL`` pattern as ``openral_hal.H1MujocoHAL`` /
``openral_hal.G1MujocoHAL``.

This HAL is a **digital-twin contract validator**, not a useful
quadruped sim: the Go2 has a floating base and no locomotion controller,
so it falls over under gravity. Closed-loop tests and the ``go2_bench``
deploy scene run with ``gravity_enabled=False``. The suite validates the
12-DoF joint-position action layout, lifecycle wiring
(``connect → read_state → send_action → estop``), joint indexing,
``RobotDescription`` round-trip, and the spliced front RGB camera
(CLAUDE.md §1.11). Walking, balance, and a real-HW ``unitree_sdk2``
adapter are follow-ups — same posture as H1 (no S0 cerebellum) and G1
before ADR-0089.

Joint inventory: the menagerie MJCF has 13 joints (12 actuated + 1
floating base, not exposed on ``RobotDescription`` — implicit world
state, not Skill-commanded) and 12 torque ``<motor>`` actuators in a
fixed order (FL, FR, RL, RR x hip / thigh / calf). qpos addresses for
the actuated joints are ``7..18``; actuator indices are ``0..11``,
aligned 1:1 with that joint order.

The menagerie Go2 uses torque actuators (``motor``, ``ctrlrange``
±23.7 N·m hip/thigh and ±45.43 N·m calf), so this HAL runs a software
PD position loop every ``mj_step`` — the same H1 / ``unitree_sdk2``
pattern — so the public action contract stays "position targets in
radians". Default qpos puts the calves at 0, which is **outside** the
calf range ``[-2.7227, -0.83776]``; ``sim.keyframe_index: 0`` loads the
menagerie ``home`` stand (thigh 0.9, calf -1.8).

The Go2 *model* in menagerie is BSD-3-Clause (Unitree); the menagerie
repo and the ``mujoco`` Python package are Apache-2.0. Compatible
permissive licenses; attributed in ``robots/go2/README.md``.

Example:
    >>> from openral_hal import GO2_DESCRIPTION, Go2MujocoHAL
    >>> hal = Go2MujocoHAL(gravity_enabled=False)  # doctest: +SKIP
    >>> hal.connect()  # doctest: +SKIP
    >>> state = hal.read_state()  # doctest: +SKIP
    >>> len(state.position) == len(GO2_DESCRIPTION.joints) == 12  # doctest: +SKIP
    True
    >>> hal.disconnect()  # doctest: +SKIP
"""

from __future__ import annotations

from openral_core.exceptions import ROSConfigError
from openral_core.schemas import (
    AssetRefs,
    CameraSimPlacement,
    ControlMode,
    EmbodimentKind,
    HalEntrypoints,
    HalParameters,
    IntrinsicsPinhole,
    JointSpec,
    JointType,
    RobotCapabilities,
    RobotDescription,
    SafetyEnvelope,
    SensorModality,
    SensorSpec,
    SimDescription,
    UrdfAsset,
)

from openral_hal._mujoco_arm import MujocoArmHAL

__all__ = ["GO2_DESCRIPTION", "GO2_HOME_JOINT_TARGETS", "Go2MujocoHAL"]


# ── Canonical joint order ─────────────────────────────────────────────────────
# Matches the menagerie MJCF actuator order (FL, FR, RL, RR x hip / thigh /
# calf) after google-deepmind/mujoco_menagerie#148. Verified at import time
# by ``tests/sim/test_go2_hal_mujoco.py::TestMenagerieSchema``.

_GO2_LEGS: tuple[str, ...] = ("FL", "FR", "RL", "RR")
_GO2_JOINT_PARTS: tuple[str, ...] = ("hip", "thigh", "calf")
_GO2_JOINT_NAMES: tuple[str, ...] = tuple(
    f"{leg}_{part}_joint" for leg in _GO2_LEGS for part in _GO2_JOINT_PARTS
)

# Menagerie ``home`` keyframe actuated qpos (not the free-joint prefix).
# Calf range excludes 0 — tests must command around this stand, not zeros.
GO2_HOME_JOINT_TARGETS: tuple[float, ...] = (0.0, 0.9, -1.8) * 4


# ── Joint limits ─────────────────────────────────────────────────────────────
# Position + effort come from the official Unitree Go2 URDF
# (``unitreerobotics/unitree_ros`` ``go2_description.urdf``) and match the
# menagerie MJCF ``<default class>`` ranges / ``ctrlrange``. Rear thighs
# have a wider range than the front pair — physical URDF fact, not a typo.
# Velocity limits are halved published-spec values (hip/thigh 30.1 rad/s,
# calf 15.70 rad/s) for the safety envelope (same conservative posture as G1).

_GO2_POSITION_LIMITS: dict[str, tuple[float, float]] = {
    "FL_hip_joint": (-1.0472, 1.0472),
    "FL_thigh_joint": (-1.5708, 3.4907),
    "FL_calf_joint": (-2.7227, -0.83776),
    "FR_hip_joint": (-1.0472, 1.0472),
    "FR_thigh_joint": (-1.5708, 3.4907),
    "FR_calf_joint": (-2.7227, -0.83776),
    "RL_hip_joint": (-1.0472, 1.0472),
    "RL_thigh_joint": (-0.5236, 4.5379),
    "RL_calf_joint": (-2.7227, -0.83776),
    "RR_hip_joint": (-1.0472, 1.0472),
    "RR_thigh_joint": (-0.5236, 4.5379),
    "RR_calf_joint": (-2.7227, -0.83776),
}
_GO2_VELOCITY_LIMITS_BY_PART: dict[str, float] = {
    "hip": 15.0,
    "thigh": 15.0,
    "calf": 7.85,
}
_GO2_EFFORT_LIMITS_BY_PART: dict[str, float] = {
    "hip": 23.7,
    "thigh": 23.7,
    "calf": 45.43,
}
_GO2_AXIS_BY_PART: dict[str, tuple[float, float, float]] = {
    "hip": (1.0, 0.0, 0.0),
    "thigh": (0.0, 1.0, 0.0),
    "calf": (0.0, 1.0, 0.0),
}
# Official Unitree Go2 URDF ``<joint><origin xyz>`` — same numbers as
# ``robots/go2/robot.yaml``. Drift-guarded joints compare limits, not
# origins; keep both surfaces honest anyway.
_GO2_ORIGIN_XYZ: dict[str, tuple[float, float, float]] = {
    "FL_hip_joint": (0.1934, 0.0465, 0.0),
    "FL_thigh_joint": (0.0, 0.0955, 0.0),
    "FL_calf_joint": (0.0, 0.0, -0.213),
    "FR_hip_joint": (0.1934, -0.0465, 0.0),
    "FR_thigh_joint": (0.0, -0.0955, 0.0),
    "FR_calf_joint": (0.0, 0.0, -0.213),
    "RL_hip_joint": (-0.1934, 0.0465, 0.0),
    "RL_thigh_joint": (0.0, 0.0955, 0.0),
    "RL_calf_joint": (0.0, 0.0, -0.213),
    "RR_hip_joint": (-0.1934, -0.0465, 0.0),
    "RR_thigh_joint": (0.0, -0.0955, 0.0),
    "RR_calf_joint": (0.0, 0.0, -0.213),
}


def _go2_part(joint_name: str) -> str:
    """Return ``hip`` / ``thigh`` / ``calf`` for a canonical Go2 joint name."""
    _leg, part, _suffix = joint_name.split("_", 2)
    return part


def _go2_parent_child(joint_name: str) -> tuple[str, str]:
    """Return ``(parent_link, child_link)`` following the Unitree Go2 URDF."""
    leg, part, _suffix = joint_name.split("_", 2)
    child = f"{leg}_{part}"
    if part == "hip":
        return "base", child
    if part == "thigh":
        return f"{leg}_hip", child
    if part == "calf":
        return f"{leg}_thigh", child
    raise ROSConfigError(f"unknown Go2 joint {joint_name!r}")


def _go2_joint_specs() -> list[JointSpec]:
    specs: list[JointSpec] = []
    for name in _GO2_JOINT_NAMES:
        part = _go2_part(name)
        parent, child = _go2_parent_child(name)
        specs.append(
            JointSpec(
                name=name,
                joint_type=JointType.REVOLUTE,
                parent_link=parent,
                child_link=child,
                axis_xyz=_GO2_AXIS_BY_PART[part],
                origin_xyz=_GO2_ORIGIN_XYZ[name],
                position_limits=_GO2_POSITION_LIMITS[name],
                velocity_limit=_GO2_VELOCITY_LIMITS_BY_PART[part],
                effort_limit=_GO2_EFFORT_LIMITS_BY_PART[part],
                has_torque_sensor=True,
                actuator_kind="bldc",
            )
        )
    return specs


# Official Unitree Go2 URDF ``front_camera_joint`` origin on ``base``.
# The menagerie MJCF ships no ``<camera>``; the generic HAL camera rig
# splices this onto ``base``. Intrinsics are NOMINAL (same 640x480 /
# fx=fy=343 pinhole G1 uses for its spliced head cam) — not a calibrated
# Go2 lens. Run a checkerboard before this feeds SLAM / object-lift.
_GO2_FRONT_CAMERA_POS: tuple[float, float, float] = (0.32715, -0.00003, 0.04297)
_GO2_FRONT_CAMERA_TARGET: tuple[float, float, float] = (1.32715, -0.00003, 0.0)


GO2_DESCRIPTION = RobotDescription(
    name="go2",
    embodiment_kind=EmbodimentKind.QUADRUPED,
    base_frame="base",
    joints=_go2_joint_specs(),
    end_effectors=[],
    sensors=[
        SensorSpec(
            name="front",
            modality=SensorModality.RGB,
            frame_id="front_camera",
            parent_frame="base",
            rate_hz=15.0,
            intrinsics=IntrinsicsPinhole(
                width=640, height=480, fx=343.0, fy=343.0, cx=320.0, cy=240.0
            ),
            encoding="rgb8",
            vla_feature_key="observation.images.front",
            sim_placement=CameraSimPlacement(
                parent_body="base",
                pos=_GO2_FRONT_CAMERA_POS,
                target=_GO2_FRONT_CAMERA_TARGET,
            ),
        )
    ],
    capabilities=RobotCapabilities(
        locomotion=["quadruped"],
        can_lift_kg=8.0,  # Unitree Go2 published payload (standard, not Edu)
        has_dexterous_hands=False,
        has_force_control=True,
        has_vision=True,
        has_lidar=False,  # hardware radar exists; not wired this spike
        bimanual=False,
        supported_control_modes=[ControlMode.JOINT_POSITION],
        supported_vla_embodiments=["go2"],
        embodiment_tags=["go2", "unitree_go2", "quadruped"],
    ),
    safety=SafetyEnvelope(
        max_ee_speed_m_s=1.5,
        max_joint_speed_factor=0.5,
        max_force_n=100.0,
        max_torque_nm=45.43,  # calf peak from the official URDF
        deadman_required=True,
    ),
    sdk_kind="open",
    hal=HalEntrypoints(
        sim="openral_hal.go2:Go2MujocoHAL",
        real=None,
        # Consumed by ``build_hal`` (not a ROS param). Gravity off is
        # required: there is no gait, so the floating-base twin falls.
        parameters=HalParameters(defaults={"gravity_enabled": False}),
    ),
    assets=AssetRefs(
        urdf=UrdfAsset(ref="rd:go2_description"),
        mjcf="rd:go2_mj_description",
    ),
    sim=SimDescription(
        floating_base=True,
        keyframe_index=0,  # menagerie ``home`` stand; calves cannot rest at 0
    ),
)


# ── PD gains for the position loop ───────────────────────────────────────────
# Same sizing rule as H1: 1 rad of error saturates near ``ctrlrange``,
# kv = 0.05 * kp. Contract-validation gains with gravity off — not a
# locomotion controller.
_GO2_KP_BY_PART: dict[str, float] = {
    "hip": 23.7,
    "thigh": 23.7,
    "calf": 45.43,
}
_GO2_KV_BY_PART: dict[str, float] = {part: 0.05 * kp for part, kp in _GO2_KP_BY_PART.items()}


def _go2_pd_gains() -> dict[str, tuple[float, float]]:
    """Per-joint ``(kp, kv)`` gains keyed by the canonical joint name."""
    return {
        name: (_GO2_KP_BY_PART[_go2_part(name)], _GO2_KV_BY_PART[_go2_part(name)])
        for name in _GO2_JOINT_NAMES
    }


class Go2MujocoHAL(MujocoArmHAL):
    """HAL adapter for the Unitree Go2 quadruped (MuJoCo digital twin).

    Drives the 12 actuated joints of the menagerie ``unitree_go2`` MJCF
    through a software PD loop over torque ``<motor>`` actuators. Exposes
    a 12-D ``openral_core.Action`` matching ``GO2_DESCRIPTION`` (FL, FR,
    RL, RR x hip / thigh / calf).

    .. warning::

       This HAL does **not** provide balance or a gait. Without a
       locomotion controller the robot falls under gravity. Closed-loop
       tests and ``scenes/deploy/go2_bench.yaml`` run with
       ``gravity_enabled=False``. Use this HAL to validate the action
       contract / joint indexing / lifecycle / camera splice, **not**
       to roll out a walking policy.

    Args:
        mjcf_path: Optional override for the MJCF file path. When
            ``None``, the file is fetched lazily from
            ``robot_descriptions``
            (``mujoco_menagerie/unitree_go2/go2.xml``).
        settle_steps: Number of MuJoCo physics steps performed in
            ``send_action``. Defaults to ``1``; raise it in tests
            that assert the body has converged at the commanded pose.
        gravity_enabled: When ``False``, gravity is zeroed at
            ``connect()`` time — required for contract-validation
            tests because the floating base falls otherwise.
        staleness_limit_s: Maximum age of a cached state.

    Example:
        >>> from openral_hal import Go2MujocoHAL  # doctest: +SKIP
        >>> hal = Go2MujocoHAL(gravity_enabled=False)  # doctest: +SKIP
        >>> hal.connect()  # doctest: +SKIP
        >>> state = hal.read_state()  # doctest: +SKIP
        >>> len(state.position)  # 12 actuated joints  # doctest: +SKIP
        12
        >>> hal.disconnect()  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        mjcf_path: str | None = None,
        settle_steps: int = 1,
        gravity_enabled: bool = True,
        staleness_limit_s: float = 0.5,
    ) -> None:
        """Initialise the Go2 HAL; no MuJoCo state is created until ``connect()``."""
        self._init_from_description(
            GO2_DESCRIPTION,
            mjcf_path=mjcf_path,
            settle_steps=settle_steps,
            gravity_enabled=gravity_enabled,
            staleness_limit_s=staleness_limit_s,
        )
        self._pd_gains: dict[str, tuple[float, float]] = _go2_pd_gains()

    def _per_step_update(self, targets: list[float]) -> None:
        """Run a software PD position loop every ``mj_step``.

        Overrides the base no-op because the Go2 MJCF uses ``motor``
        actuators (torque-controlled), exactly like H1. Recompute
        ``tau = kp * (target - q) - kv * dq`` clamped to ``ctrlrange``
        so ``Action.joint_targets`` stays "position targets in radians".
        """
        assert self._data is not None
        assert self._model is not None
        for name, target in zip(self._joint_names, targets, strict=True):
            act_idx = self._actuator_index.get(name)
            if act_idx is None:
                continue
            kp, kv = self._pd_gains[name]
            qpos_idx = self._joint_qpos_addr[name]
            qvel_idx = self._joint_qvel_addr[name]
            q = float(self._data.qpos[qpos_idx])
            dq = float(self._data.qvel[qvel_idx])
            tau = kp * (float(target) - q) - kv * dq
            low, high = self._model.actuator_ctrlrange[act_idx]
            self._data.ctrl[act_idx] = max(float(low), min(float(high), tau))

    def _apply_arm_targets(self, targets: list[float]) -> None:
        """No-op for Go2; the per-step PD loop drives the actuators instead."""
        del targets
