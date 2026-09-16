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

So ``_per_step_update`` splits by joint, and everything else (estop latch,
idle stepping, proprio, cameras) is inherited unchanged.

The arm's spawn pose is the menagerie ``home`` keyframe. Position servos
default to a ctrl of 0, which is a *legal* arm pose, so an unseeded arm does
not fault — it silently folds to joint=0 over the first few steps (measured:
0.43 rad off home). ``sim.seed_ctrl_from_qpos`` in the manifest plus
``_snap_actuated_home`` here are what keep it up.

Sim-only, inherited from the Go2: there is no ``unitree_sdk2`` adapter, and
Unitree pairs the Z1 with the larger B1 rather than a Go2 in the real world.

Example:
    >>> hal = Go2Z1MujocoHAL(gravity_enabled=False)  # doctest: +SKIP
"""

from __future__ import annotations

from typing import Final

from openral_core import RobotDescription

from openral_hal.go2 import GO2_HOME_JOINT_TARGETS, Go2MujocoHAL, _go2_pd_gains

__all__ = [
    "GO2_Z1_ARM_HOME",
    "GO2_Z1_ARM_JOINT_NAMES",
    "GO2_Z1_HOME_JOINT_TARGETS",
    "GO2_Z1_LEG_JOINT_NAMES",
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

#: Full 19-DoF spawn pose: Hub stand for the legs, ``home`` for the arm.
GO2_Z1_HOME_JOINT_TARGETS: Final[tuple[float, ...]] = (
    *GO2_HOME_JOINT_TARGETS,
    *GO2_Z1_ARM_HOME,
)


class Go2Z1MujocoHAL(Go2MujocoHAL):
    """Go2 + Z1 composite twin: torque-PD legs, position-servo arm.

    Exposes a 19-D ``openral_core.Action`` in ``robots/go2_z1/robot.yaml``
    joint order — the 12 Go2 legs first, byte-identical to ``robots/go2``,
    then the Z1's 6 arm joints, then the jaw. A 12-DoF locomotion policy's
    action therefore still lands on the joints it was trained for; the arm
    occupies indices the policy never writes.

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

    def _home_targets(self) -> tuple[float, ...]:
        """Spawn pose sized to whatever joint list the manifest declared."""
        n = len(self._joint_names)
        if n == len(GO2_Z1_HOME_JOINT_TARGETS):
            return GO2_Z1_HOME_JOINT_TARGETS
        # A manifest with a different arm still gets the legs' Hub stand; the
        # remaining joints spawn at 0, which every position servo accepts.
        return (*GO2_HOME_JOINT_TARGETS, *((0.0,) * (n - len(GO2_HOME_JOINT_TARGETS))))

    def _snap_actuated_home(self) -> None:
        """Snap all 19 joints to the composite spawn pose, then hold it.

        Overrides the Go2's 12-joint snap, which would raise on the ``zip(...,
        strict=True)`` against this robot's longer joint list.
        """
        assert self._model is not None
        assert self._data is not None
        home = self._home_targets()
        for name, target in zip(self._joint_names, home, strict=True):
            qpos_addr = self._joint_qpos_addr.get(name)
            if qpos_addr is not None:
                self._data.qpos[qpos_addr] = float(target)
        self._hold_targets = list(home)

        import mujoco as mj  # noqa: PLC0415  # reason: optional sim-only dep

        mj.mj_forward(self._model, self._data)
        self._per_step_update(self._hold_targets)

    def _per_step_update(self, targets: list[float]) -> None:
        """Torque PD for the legs, direct position write for the arm.

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
                # Position servo: ctrl IS the radians target.
                command = float(target)
            self._data.ctrl[act_idx] = max(float(low), min(float(high), command))
