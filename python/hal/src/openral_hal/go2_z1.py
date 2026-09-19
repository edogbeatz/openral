"""HAL adapter for the Unitree Go2 carrying a Unitree Z1 arm (MuJoCo twin).

The composite `robots/go2_z1/robot.yaml` drives, and this is the one place
that knows its actuators are **not** homogeneous:

* the Go2's 12 leg joints are torque ``<motor>`` actuators, so a position
  target only becomes motion through the software PD loop
  :class:`openral_hal.go2.Go2MujocoHAL` already runs;
* the Z1's 7 joints are position servos (``biastype="affine"``), which hold
  a commanded target on their own. Running the leg PD law over them would
  write a torque into a position field — the servo would read it as a
  radians target of ~20 rad and slam the arm into its stops.

The Z1 hold is **sticky**: Recalibrate / ``arm_ready`` (Hub-stand legs +
19-D arm) updates it; locomotion (12-D, or 19-D with moving legs) keeps
snapping **arm joints only** so gait cannot wave the Z1 and walk's
hold-pad cannot chase proprio. Legs and the free base follow the 12-D
rsl-rl command. Idle ticks snap the arm too — ``send_action`` alone is
one physics step and the wall-time idle stepper would otherwise leave
the servos soft.

Sim-only, inherited from the Go2: there is no ``unitree_sdk2`` adapter, and
Unitree pairs the Z1 with the larger B1 rather than a Go2 in the real world.

Example:
    >>> hal = Go2Z1MujocoHAL(gravity_enabled=False)  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from openral_core import Action, RobotDescription

from openral_hal._mujoco_arm import _IDLE_STEP_CAP, MujocoArmHAL
from openral_hal.go2 import GO2_HOME_JOINT_TARGETS, Go2MujocoHAL, _go2_pd_gains

#: Max |leg - Hub stand| (rad) to treat a 19-D row as an arm command
#: (``arm_ready`` / Recalibrate). Walk's rsl-rl output leaves this band.
_HUB_STAND_LEG_TOL_RAD: Final[float] = 0.15

#: Width of the base free joint's ``qpos`` block (xyz + wxyz). An arm joint
#: whose address falls inside it is not an arm joint — it is the floating base,
#: and writing a servo target there would teleport the dog.
_FREE_JOINT_QPOS_WIDTH: Final[int] = 7

__all__ = [
    "GO2_Z1_ARM_FOLD",
    "GO2_Z1_ARM_HOME",
    "GO2_Z1_ARM_JOINT_NAMES",
    "GO2_Z1_ARM_READY",
    "GO2_Z1_HOME_JOINT_TARGETS",
    "GO2_Z1_LEG_JOINT_NAMES",
    "GO2_Z1_SPAWN_JOINT_TARGETS",
    "Go2Z1MujocoHAL",
]

#: The Go2's 12 leg joints — the subset driven by the software torque PD loop.
GO2_Z1_LEG_JOINT_NAMES: Final[tuple[str, ...]] = tuple(
    f"{leg}_{part}_joint" for leg in ("FL", "FR", "RL", "RR") for part in ("hip", "thigh", "calf")
)

#: The Z1's 6 arm joints + jaw, in composed-MJCF order. Position servos.
GO2_Z1_ARM_JOINT_NAMES: Final[tuple[str, ...]] = (
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "jointGripper",
)

#: Menagerie ``z1_gripper.xml`` ``home`` keyframe, jaw closed.
GO2_Z1_ARM_HOME: Final[tuple[float, ...]] = (0.0, 0.785, -0.261, -0.523, 0.0, 0.0, 0.0)

#: Folded servo zeros — the pose an unseeded Z1 drifts to (legal, but limp).
GO2_Z1_ARM_FOLD: Final[tuple[float, ...]] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

#: Reach-ready: shoulder up, elbow bent, gripper forward of the snout.
#: Distinct from :data:`GO2_Z1_ARM_HOME` so a future arm skill is visible.
GO2_Z1_ARM_READY: Final[tuple[float, ...]] = (0.0, 1.2, -1.0, -0.4, 0.0, 0.0, 0.0)

#: Full 19-DoF vector of Hub stand + the menagerie arm ``home`` keyframe. This is
#: the literal upstream home, **not** what this twin spawns at — see
#: :data:`GO2_Z1_SPAWN_JOINT_TARGETS`.
GO2_Z1_HOME_JOINT_TARGETS: Final[tuple[float, ...]] = (
    *GO2_HOME_JOINT_TARGETS,
    *GO2_Z1_ARM_HOME,
)

#: Full 19-DoF **spawn** pose: Hub stand for the legs, ``ready`` for the arm.
#:
#: The arm spawns at ``ready`` rather than the menagerie ``home`` because
#: ``home`` does not survive a walk at honest arm mass. A 12-D locomotion row
#: leaves the arm on whatever the sticky hold is, and on a fresh connect that
#: hold is the spawn pose — so with ``arm_mass_scale: 1.0`` and no prior
#: Recalibrate, ``rskill-rsl_rl_onnx-go2-velocity_flat`` tipped the composite in
#: ~0.7 s on 8 of 8 randomised rollouts from ``home`` while surviving 8 of 8
#: from ``ready``. Measured by ``tools/go2_z1_mass_balance.py walk``; the batteries
#: and the two rejected explanations (centre-of-mass offset, pitch inertia —
#: neither predicts survival) are in
#: ``docs/reference/go2-z1-mass-balance.md``.
#:
#: This makes the default agree with the operating procedure the live demo
#: already required by hand: Recalibrate (which parks at ``ready``) *before*
#: applying a gait. ``arm_mass_scale: 0.01`` masks the difference entirely —
#: every named pose survives at that scale — so the manifest's current
#: locomotion default hides this rather than fixing it.
GO2_Z1_SPAWN_JOINT_TARGETS: Final[tuple[float, ...]] = (
    *GO2_HOME_JOINT_TARGETS,
    *GO2_Z1_ARM_READY,
)


class Go2Z1MujocoHAL(Go2MujocoHAL):
    """Go2 + Z1 composite twin: torque-PD legs, sticky qpos-snapped arm.

    Exposes a 19-D ``openral_core.Action`` in ``robots/go2_z1/robot.yaml``
    joint order — the 12 Go2 legs first, byte-identical to ``robots/go2``,
    then the Z1's 6 arm joints, then the jaw. A 12-DoF locomotion policy's
    action therefore still lands on the joints it was trained for.

    The arm hold starts at :data:`GO2_Z1_SPAWN_JOINT_TARGETS`. A 19-D row whose legs are still Hub
    stand (Recalibrate, ``rskill-zero-go2_z1-arm_ready-fp32``) writes the
    arm slots into the hold. 12-D locomotion and hold-padded 19-D walk
    rows pin the arm to that hold and qpos-snap **arm joints only**
    every physics step (including idle). Legs and the free base follow
    the locomotion command so rsl-rl walk can translate. The Z1 stays
    at the last Recalibrate / ready pose instead of waving or chasing
    proprio.

    .. warning::

       Simulation only. ``hal.real`` is null for this robot.
    """

    def __init__(
        self,
        *,
        description: RobotDescription | None = None,
        mjcf_path: str | None = None,
        settle_steps: int = 1,
        gravity_enabled: bool = True,
        staleness_limit_s: float = 0.5,
    ) -> None:
        """Initialise from the COMPOSITE manifest; no MuJoCo state until ``connect()``.

        Unlike the 12-DoF Go2 twin, this HAL cannot carry its own description
        constant: the joint list, actuator indices and gripper wiring all come
        from ``robots/go2_z1/robot.yaml``, and `build_hal` threads it in.
        ``mjcf_path`` is the composed model the lifecycle node builds from the
        manifest's ``scene_defaults.composition`` — without it the bare
        ``go2.xml`` loads and there is no arm to drive.
        """
        from openral_hal.go2 import (  # noqa: PLC0415  # reason: avoids a circular import at module load
            GO2_DESCRIPTION,
        )

        self._init_from_description(
            description if description is not None else GO2_DESCRIPTION,
            mjcf_path=mjcf_path,
            settle_steps=settle_steps,
            gravity_enabled=gravity_enabled,
            staleness_limit_s=staleness_limit_s,
        )
        self._pd_gains: dict[str, tuple[float, float]] = _go2_pd_gains()
        self._leg_joints: frozenset[str] = frozenset(GO2_Z1_LEG_JOINT_NAMES)
        self._hold_targets = list(self._home_targets())
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        self._arm_hold_pose: list[float] = list(self._home_targets()[n_legs:])

    def _home_targets(self) -> tuple[float, ...]:
        """Spawn pose sized to whatever joint list the manifest declared."""
        n = len(self._joint_names)
        if n == len(GO2_Z1_SPAWN_JOINT_TARGETS):
            return GO2_Z1_SPAWN_JOINT_TARGETS
        # A manifest with a different arm still gets the legs' Hub stand; the
        # remaining joints spawn at 0, which every position servo accepts.
        return (*GO2_HOME_JOINT_TARGETS, *((0.0,) * (n - len(GO2_HOME_JOINT_TARGETS))))

    def _arm_hold(self) -> list[float]:
        """Sticky arm+jaw targets — last Recalibrate / arm_ready pose."""
        return list(self._arm_hold_pose)

    @property
    def arm_hold_pose(self) -> tuple[float, ...]:
        """The sticky 7-D Z1 hold a 12-D locomotion row will keep enforcing.

        Read-only view of the state that decides what the arm does during a
        gait. Worth being able to observe from outside: whether a walk started
        from the spawn pose or from a Recalibrate is invisible in a 12-D action
        stream, and that distinction is what
        `tools/go2_z1_mass_balance.py walk` and the composite's spawn
        regression test compare.
        """
        return tuple(self._arm_hold_pose)

    def _row_is_leg_only(self, action: Action) -> bool:
        """True when every waypoint is the 12-D Go2 locomotion width."""
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        rows = action.joint_targets
        if not rows:
            return False
        return all(len(row) == n_legs for row in rows)

    def _legs_are_hub_stand(self, legs: Sequence[float]) -> bool:
        """True when ``legs`` matches Hub stand (arm-command / Recalibrate path)."""
        home = GO2_HOME_JOINT_TARGETS
        if len(legs) != len(home):
            return False
        return all(
            abs(float(value) - float(ref)) <= _HUB_STAND_LEG_TOL_RAD
            for value, ref in zip(legs, home, strict=True)
        )

    def _maybe_capture_arm_command(self, row: Sequence[float]) -> None:
        """Update the sticky hold from a 19-D Hub-stand arm command."""
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        n = len(self._joint_names)
        if len(row) != n or n <= n_legs:
            return
        if not self._legs_are_hub_stand(row[:n_legs]):
            return
        self._arm_hold_pose = [float(v) for v in row[n_legs:]]

    def _expand_leg_only_targets(self, row: list[float]) -> list[float]:
        """Hold-pad a leg row to full DoF; pin the arm to the sticky hold."""
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        n = len(self._joint_names)
        arm = self._arm_hold()
        if len(row) == n_legs and n > n_legs:
            return [*[float(v) for v in row], *arm]
        if len(row) == n and n > n_legs:
            return [*[float(v) for v in row[:n_legs]], *arm]
        return [float(v) for v in row]

    def _with_held_arm(self, action: Action) -> Action:
        """Pin every waypoint's arm slots to the sticky arm hold."""
        if not action.joint_targets:
            return action
        rows = [self._expand_leg_only_targets(list(row)) for row in action.joint_targets]
        return action.model_copy(update={"joint_targets": rows, "horizon": len(rows)})

    def send_action(self, action: Action) -> None:
        """Drive the legs; keep the arm at the sticky Recalibrate / ready hold."""
        if action.joint_targets and not self._row_is_leg_only(action):
            self._maybe_capture_arm_command(action.joint_targets[-1])
        arm = self._arm_hold()
        expanded = self._with_held_arm(action)
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        updated = self._last_arm_targets(expanded)
        self._hold_targets = [*updated[:n_legs], *arm]
        MujocoArmHAL.send_action(self, expanded)
        self._snap_arm_hold(arm)

    def _snap_arm_hold(self, arm: list[float]) -> None:
        """Teleport Z1 joints to ``arm`` and zero their velocities.

        Legs and the free base are never written here — a full-qpos snap
        after every ``send_action`` / idle ``mj_step`` would freeze Hub
        stand and cancel rsl-rl walk.
        """
        if self._data is None or self._model is None:
            return
        import mujoco as mj  # noqa: PLC0415  # reason: optional sim-only dep

        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        for name, target in zip(self._joint_names[n_legs:], arm, strict=True):
            if name in self._leg_joints:
                continue
            qpos_addr = self._joint_qpos_addr.get(name)
            if qpos_addr is None or qpos_addr < _FREE_JOINT_QPOS_WIDTH:
                continue
            self._data.qpos[qpos_addr] = float(target)
            qvel_addr = self._joint_qvel_addr.get(name)
            if qvel_addr is not None:
                self._data.qvel[qvel_addr] = 0.0
        mj.mj_forward(self._model, self._data)

    def reset_to_pose(self, pose: list[float], *, origin: bool = False) -> None:
        """Snap legs; 19-D updates the arm hold, 12-D keeps it; upright base."""
        del origin  # always recentre — same contract as Go2MujocoHAL
        self._maybe_capture_arm_command(pose)
        expanded = self._expand_leg_only_targets(list(pose))
        MujocoArmHAL.reset_to_pose(self, expanded)
        self._hold_targets = list(expanded)
        self._pd_gains = _go2_pd_gains()
        self._per_step_update(self._hold_targets)
        self._snap_arm_hold(self._arm_hold())
        self._snap_base_upright(origin=True)

    def idle_step(self, wall_dt_s: float | None = None) -> bool:
        """PD-hold the legs and qpos-snap the Z1 every idle physics step."""
        if not self._connected or self._data is None or self._model is None:
            return False
        import time  # noqa: PLC0415  # reason: match Go2 idle_step; keep import off connect

        import mujoco as mj  # noqa: PLC0415  # reason: optional sim-only dep

        steps = 1
        if wall_dt_s is not None and wall_dt_s > 0:
            timestep = float(self._model.opt.timestep)
            if timestep > 0:
                steps = max(1, min(_IDLE_STEP_CAP, round(wall_dt_s / timestep)))
        arm = self._arm_hold()
        for _ in range(steps):
            self._per_step_update(self._hold_targets)
            mj.mj_step(self._model, self._data)
            self._snap_arm_hold(arm)
        self._last_state_time = time.monotonic()
        return True

    def _snap_actuated_home(self) -> None:
        """Snap all 19 joints to the composite spawn pose, then hold it.

        Overrides the Go2's 12-joint snap, which would raise on the ``zip(...,
        strict=True)`` against this robot's longer joint list.
        """
        assert self._model is not None
        assert self._data is not None
        home = self._home_targets()
        n_legs = len(GO2_Z1_LEG_JOINT_NAMES)
        for name, target in zip(self._joint_names, home, strict=True):
            qpos_addr = self._joint_qpos_addr.get(name)
            if qpos_addr is not None:
                self._data.qpos[qpos_addr] = float(target)
        self._hold_targets = list(home)
        self._arm_hold_pose = list(home[n_legs:])

        import mujoco as mj  # noqa: PLC0415  # reason: optional sim-only dep

        mj.mj_forward(self._model, self._data)
        self._per_step_update(self._hold_targets)
        self._snap_arm_hold(self._arm_hold_pose)

    def _per_step_update(self, targets: list[float]) -> None:
        """Torque PD for the legs; radians target for the arm servos.

        The split is by joint, not by index range, so a manifest that reorders
        its joints cannot silently send a torque to a position servo.
        """
        assert self._data is not None
        assert self._model is not None
        for name, target in zip(self._joint_names, targets, strict=True):
            act_idx = self._actuator_index.get(name)
            if act_idx is None:
                continue
            low, high = self._model.actuator_ctrlrange[act_idx]
            if name in self._leg_joints:
                kp, kv = self._pd_gains[name]
                qpos_idx = self._joint_qpos_addr[name]
                qvel_idx = self._joint_qvel_addr[name]
                q = float(self._data.qpos[qpos_idx])
                dq = float(self._data.qvel[qvel_idx])
                command = kp * (float(target) - q) - kv * dq
            else:
                # Position servo: ctrl IS the radians target (gains left enabled).
                command = float(target)
            self._data.ctrl[act_idx] = max(float(low), min(float(high), command))
