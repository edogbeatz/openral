"""Where is the Go2+Z1's centre of mass, and which Z1 pose puts it back over the feet?

`robots/go2_z1/robot.yaml` carries a 4.70 kg Z1 bolted 0.18 m forward and 0.06 m
up on a 15.25 kg Go2, and drives it with `rskill-rsl_rl_onnx-go2-velocity_flat`
— a policy trained on the **bare** dog. The manifest's workaround is
`scene_defaults.composition.arm_mass_scale: 0.01`, which keeps the meshes and
throws the payload away.

This tool was built to test a plausible fix — park the arm so the composite
centre of mass returns to where the bare dog's was, and the policy should cope.
**It measured that fix and the fix does not work**: across the whole offset range
survival is uncorrelated with the offset (a 0.45 mm pose fell 0/6 while a 54.7 mm
pose walked 6/6), and the centred pose tracks the velocity command ~27 % slower
than `ARM_READY`. The statics are still worth measuring — they are just not what
gates the gait. Full result in `docs/reference/go2-z1-mass-balance.md`.

Three things are measured, never assumed:

* **`com_offset_mm`** — horizontal distance from the whole-model centre of mass
  (MuJoCo `subtree_com[0]`, so every body's real `<inertial>`) to the centroid of
  the four foot contacts.
* **`trot_margin_mm`** — the binding constraint. Statically the dog is nowhere
  near tipping: the front polygon edge is 139 mm away even at `ARM_READY`. But a
  trot stands on one *diagonal pair* at a time, and that support degenerates to a
  line, so the perpendicular distance from the centre of mass to the worse
  diagonal is the margin that actually shrinks.
* **`com_height_m`** — the lever arm the same offset acts through.

`measure` reports the named poses in `openral_hal.go2_z1`; `search` sweeps the
Z1's joint range for poses that zero the offset without self-collision; `walk`
rolls the real rsl-rl ONNX checkpoint out over the composed model at honest mass
and reports how far the dog gets before it tips, per arm pose. `walk` is the only
mode that can say a pose *helps* — the other two describe statics.

`stale` measures a different axis entirely, and found the one sharp threshold in
this robot's locomotion: **observation age**. Delaying the proprio bundle by two
policy ticks (40 ms) drops survival from 8/8 to 1/8; one tick (20 ms) is still
8/8. That is the measured justification for the 200 Hz publishers in
`scenes/deploy/go2_z1_walk.yaml`. It is **not** an explanation of the live
mid-gait tip: the deploy graph was measured at a median 5.1 ms proprio age,
inside the surviving band.

Base height is derived, not assumed: the legs are placed at Hub stand and the
free base is dropped until the lowest foot sphere touches z=0, so the support
polygon is the one the feet actually make.

Run::

    uv run python tools/go2_z1_mass_balance.py measure
    uv run python tools/go2_z1_mass_balance.py measure --arm-mass-scale 0.01
    uv run python tools/go2_z1_mass_balance.py search --top 10
    uv run python tools/go2_z1_mass_balance.py walk --pose ready --pose home
    uv run python tools/go2_z1_mass_balance.py stale
    uv run python tools/go2_z1_mass_balance.py stale --age 0 --age 2 --trials 4
    uv run python tools/go2_z1_mass_balance.py measure --json

Needs the `sim` group (MuJoCo); `walk` also needs onnxruntime and Hub access for
`hf://diasAiMaster/unitree-go2-velocity-flat`.

Results recorded in `docs/reference/go2-z1-mass-balance.md`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST = _REPO / "robots" / "go2_z1" / "robot.yaml"
_WALK_MANIFEST = _REPO / "rskills" / "rsl-rl-onnx-go2-velocity-flat" / "rskill.yaml"

#: Go2 foot collision spheres, one per leg, in the composed MJCF.
FOOT_GEOMS = ("FL", "FR", "RL", "RR")

#: A trot stands on one diagonal pair at a time — the two support lines whose
#: perpendicular offset `trot_margin_mm` measures.
TROT_DIAGONALS = (("FL", "RR"), ("FR", "RL"))

#: Bodies of the mounted arm. `link00`..`link06` plus the two gripper bodies.
ARM_BODY_PREFIXES = ("link0", "gripper")

#: Honest menagerie mass. The manifest ships 0.01 for locomotion demos.
HONEST_ARM_MASS_SCALE = 1.0

#: What `robots/go2_z1/robot.yaml` actually composes for the deploy scene, so a
#: sweep meant to explain live behaviour can match it.
LIVE_ARM_MASS_SCALE = 0.01

#: `deploy.yaml` `step_dt` of the Go2 velocity checkpoint: a 50 Hz policy.
WALK_STEP_DT_S = 0.02

#: Tipped when the base's own z-axis leans more than this off vertical.
TIP_TILT_RAD = 1.0

#: First observation age (in policy ticks) at which the walk stops surviving.
#: Measured by `stale`: 0 and 1 tick both survive 8/8, 2 ticks drops to 1/8,
#: and 3+ collapses inside 4 s. One tick is `WALK_STEP_DT_S` = 20 ms, so the
#: cliff is between 20 ms and 40 ms of proprio age. This is what
#: `scenes/deploy/go2_z1_walk.yaml` buys with `publish_rate_hz: 200.0`; the
#: live graph was measured at a median 5.1 ms / p90 10.2 ms age, inside the
#: surviving band. Do not lower those publisher rates.
PROPRIO_AGE_CLIFF_TICKS = 2

#: Observation ages `stale` sweeps by default, in policy ticks.
PROPRIO_AGE_SWEEP = (0, 1, 2, 3, 4)


@dataclass(frozen=True)
class BalanceMeasurement:
    """One arm pose's contribution to the composite's static balance.

    Attributes:
        pose: Named pose, or `search` for a swept candidate.
        arm: The 7 Z1 targets (joint1..joint6 + jaw), radians.
        total_mass_kg: Every body's `<inertial>` mass, including the arm.
        arm_mass_kg: The mounted arm's share of it.
        com_xyz_m: Whole-model centre of mass, world frame.
        support_centroid_xy_m: Centroid of the four foot contacts.
        com_offset_mm: Horizontal centre-of-mass distance from that centroid.
        com_height_m: Centre-of-mass height above the ground plane.
        trot_margin_mm: Perpendicular centre-of-mass distance to the worse of
            the two diagonal (trot) support lines.
        static_margin_mm: Distance to the nearest four-foot polygon edge — ample
            by construction, and reported so it stays visibly not the binding
            constraint.
        self_contacts: Arm-vs-robot contacts. Non-zero means the pose is
            unusable however well it balances.
        base_height_m: Free-base height once the feet were dropped onto z=0.
    """

    pose: str
    arm: tuple[float, ...]
    total_mass_kg: float
    arm_mass_kg: float
    com_xyz_m: tuple[float, float, float]
    support_centroid_xy_m: tuple[float, float]
    com_offset_mm: float
    com_height_m: float
    trot_margin_mm: float
    static_margin_mm: float
    self_contacts: int
    base_height_m: float


@dataclass(frozen=True)
class WalkRollout:
    """One rsl-rl rollout over the composed model at a given arm pose.

    Attributes:
        pose: Named arm pose held for the whole rollout.
        arm_mass_scale: Composition scale the arm inertias were built with.
        velocity_commands: Isaac `[vx, vy, yaw_rate]` joystick.
        commanded_s: Rollout length asked for.
        survived_s: Simulated seconds before the tip, or `commanded_s`.
        distance_m: Straight-line base displacement at that point.
        speed_m_s: `distance_m / survived_s` — compare against the commanded
            `vx`. A pose can keep the dog upright and still cost it tracking.
        tipped: Whether the base exceeded `TIP_TILT_RAD` off vertical.
        max_tilt_rad: Worst base tilt off vertical during the rollout.
        min_base_height_m: Lowest the base got — a near-fall the tilt gate
            alone would not catch.
        arm_drift_rad: Largest |commanded − actual| over the 6 arm joints
            (the jaw is excluded: `read_state` reports it normalised to [0, 1],
            not radians), so a rollout cannot claim a pose the servos never held.
        arm_contacts: Ticks on which an arm body touched the robot or the
            ground. Non-zero invalidates the pose however well it balances.
        proprio_age_ticks: How many policy ticks stale the observation was.
            0 is the in-process HAL read; see `walk` for why a live graph
            cannot offer 0.
        lateral_drift_m: Largest |y − y_start|. The live tip is preceded by a
            steady lateral creep, so distance alone hides it.
    """

    pose: str
    arm_mass_scale: float
    velocity_commands: tuple[float, float, float]
    commanded_s: float
    survived_s: float
    distance_m: float
    speed_m_s: float
    tipped: bool
    max_tilt_rad: float
    min_base_height_m: float
    arm_drift_rad: float
    arm_contacts: int
    proprio_age_ticks: int = 0
    lateral_drift_m: float = 0.0


def named_poses() -> dict[str, tuple[float, ...]]:
    """The Z1 poses `openral_hal.go2_z1` ships, by manifest name."""
    from openral_hal.go2_z1 import GO2_Z1_ARM_FOLD, GO2_Z1_ARM_HOME, GO2_Z1_ARM_READY

    return {
        "fold": GO2_Z1_ARM_FOLD,
        "home": GO2_Z1_ARM_HOME,
        "ready": GO2_Z1_ARM_READY,
    }


def compose(arm_mass_scale: float) -> tuple[Any, Any, Path]:
    """Compose the manifest's MJCF at *arm_mass_scale* and load it.

    Returns:
        `(model, data, path)` — the loaded `MjModel` / `MjData` and the written
        scene file, which is the artefact a viewer can open.
    """
    import mujoco as mj
    from openral_core import RobotDescription
    from openral_sim.scene_composers import compose_mounted_arm_mjcf

    description = RobotDescription.from_yaml(str(_MANIFEST))
    if description.scene_defaults is None or description.scene_defaults.composition is None:
        raise SystemExit("robots/go2_z1/robot.yaml no longer declares its arm composition")
    params: dict[str, Any] = dict(description.scene_defaults.composition.params)
    params["arm_mass_scale"] = arm_mass_scale
    xml, meshdir = compose_mounted_arm_mjcf(**params)
    path = meshdir.parent / f"go2_z1_balance_{arm_mass_scale:g}.xml"
    path.write_text(xml)
    model = mj.MjModel.from_xml_path(str(path))
    return model, mj.MjData(model), path


def _qpos_addr(model: Any, name: str) -> int:
    import mujoco as mj

    joint_id = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, name)
    if joint_id < 0:
        raise SystemExit(f"composed model has no joint {name!r}")
    return int(model.jnt_qposadr[joint_id])


def _geom_id(model: Any, name: str) -> int:
    import mujoco as mj

    geom_id = mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, name)
    if geom_id < 0:
        raise SystemExit(f"composed model has no geom {name!r}")
    return int(geom_id)


def _arm_mass(model: Any) -> float:
    import mujoco as mj

    total = 0.0
    for body in range(model.nbody):
        name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, body) or ""
        if name.startswith(ARM_BODY_PREFIXES):
            total += float(model.body_mass[body])
    return total


def _foot_contacts(model: Any, data: Any) -> dict[str, NDArray[np.float64]]:
    """Ground-contact point of each foot sphere: its centre, dropped by its radius."""
    points: dict[str, NDArray[np.float64]] = {}
    for foot in FOOT_GEOMS:
        geom = _geom_id(model, foot)
        centre = np.asarray(data.geom_xpos[geom], dtype=np.float64).copy()
        centre[2] -= float(model.geom_size[geom][0])
        points[foot] = centre
    return points


def _distance_to_segment(
    point: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64]
) -> float:
    """Perpendicular distance from *point* to the infinite line through a, b."""
    span = b - a
    length = float(np.hypot(span[0], span[1]))
    if length == 0.0:
        return float(np.hypot(*(point - a)))
    cross = span[0] * (point[1] - a[1]) - span[1] * (point[0] - a[0])
    return abs(float(cross)) / length


def _polygon_edge_margin(point: NDArray[np.float64], feet: dict[str, NDArray[np.float64]]) -> float:
    """Distance to the nearest edge of the four-foot polygon (FL, FR, RR, RL)."""
    ring = ("FL", "FR", "RR", "RL")
    return min(
        _distance_to_segment(point, feet[ring[i]][:2], feet[ring[(i + 1) % len(ring)]][:2])
        for i in range(len(ring))
    )


def measure(model: Any, data: Any, arm: tuple[float, ...], *, pose: str) -> BalanceMeasurement:
    """Place the legs at Hub stand, drop the feet onto z=0, and measure the balance."""
    import mujoco as mj
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_JOINT_NAMES, GO2_Z1_LEG_JOINT_NAMES

    data.qpos[:] = model.qpos0
    data.qpos[0:3] = [0.0, 0.0, 0.5]
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    for name, value in zip(GO2_Z1_LEG_JOINT_NAMES, GO2_HOME_JOINT_TARGETS, strict=True):
        data.qpos[_qpos_addr(model, name)] = float(value)
    for name, value in zip(GO2_Z1_ARM_JOINT_NAMES, arm, strict=True):
        data.qpos[_qpos_addr(model, name)] = float(value)
    data.qvel[:] = 0.0
    mj.mj_forward(model, data)

    # Drop the free base until the lowest foot rests on the ground plane, so the
    # support polygon is measured rather than guessed from a spawn height.
    lowest = min(point[2] for point in _foot_contacts(model, data).values())
    data.qpos[2] -= lowest
    mj.mj_forward(model, data)

    feet = _foot_contacts(model, data)
    com = np.asarray(data.subtree_com[0], dtype=np.float64).copy()
    centroid = np.mean([point[:2] for point in feet.values()], axis=0)

    ground = _geom_id(model, "openral_ground")
    self_contacts = 0
    for index in range(int(data.ncon)):
        contact = data.contact[index]
        if ground in (int(contact.geom1), int(contact.geom2)):
            continue
        self_contacts += 1

    trot_margin = min(
        _distance_to_segment(com[:2], feet[first][:2], feet[second][:2])
        for first, second in TROT_DIAGONALS
    )
    return BalanceMeasurement(
        pose=pose,
        arm=tuple(float(value) for value in arm),
        total_mass_kg=round(float(model.body_mass.sum()), 4),
        arm_mass_kg=round(_arm_mass(model), 4),
        com_xyz_m=(round(float(com[0]), 5), round(float(com[1]), 5), round(float(com[2]), 5)),
        support_centroid_xy_m=(round(float(centroid[0]), 5), round(float(centroid[1]), 5)),
        com_offset_mm=round(float(np.hypot(*(com[:2] - centroid))) * 1000.0, 2),
        com_height_m=round(float(com[2]), 5),
        trot_margin_mm=round(trot_margin * 1000.0, 2),
        static_margin_mm=round(_polygon_edge_margin(com[:2], feet) * 1000.0, 2),
        self_contacts=self_contacts,
        base_height_m=round(float(data.qpos[2]), 5),
    )


def search(
    model: Any, data: Any, *, steps: int, limit_margin_rad: float
) -> list[BalanceMeasurement]:
    """Sweep the Z1's balance-relevant joints for collision-free centred poses.

    Only `joint1`..`joint4` are swept: `joint5` / `joint6` / the jaw rotate the
    last 0.3 kg about its own axis and move the composite centre of mass by less
    than the rounding on `com_offset_mm`.

    `limit_margin_rad` keeps every swept joint that far inside its manifest
    `position_limits`. A balance pose is *held* by position servos for the length
    of a walk, and one parked on a mechanical stop has no headroom to reject the
    gait's own disturbance — it saturates instead of holding.
    """
    from openral_core import RobotDescription

    description = RobotDescription.from_yaml(str(_MANIFEST))
    limits = {
        joint.name: joint.position_limits
        for joint in description.joints
        if joint.position_limits is not None
    }
    swept = ("joint1", "joint2", "joint3", "joint4")
    missing = [name for name in swept if name not in limits]
    if missing:
        raise SystemExit(f"robots/go2_z1/robot.yaml declares no position limits for {missing}")
    grids = [
        np.linspace(limits[name][0] + limit_margin_rad, limits[name][1] - limit_margin_rad, steps)
        for name in swept
    ]
    results: list[BalanceMeasurement] = []
    for first, second, third, fourth in itertools.product(*grids):
        arm = (float(first), float(second), float(third), float(fourth), 0.0, 0.0, 0.0)
        found = measure(model, data, arm, pose="search")
        if found.self_contacts:
            continue
        results.append(found)
    results.sort(key=lambda found: (found.com_offset_mm, found.com_height_m))
    return results


def walk(
    *,
    arm: tuple[float, ...] | None,
    pose: str,
    arm_mass_scale: float,
    velocity_commands: tuple[float, float, float],
    seconds: float,
    trial: int = 0,
    perturbation: float = 0.0,
    proprio_age_ticks: int = 0,
) -> WalkRollout:
    """Roll the real rsl-rl ONNX checkpoint out with the arm parked at *arm*.

    `arm=None` skips the pose reset and walks on whatever the twin **spawned**
    with — the production path, because the runner publishes 12-D leg-only rows
    for this skill and a 12-D row leaves the sticky arm hold alone. That is the
    path a `deploy sim` walk takes when nobody ran Recalibrate first.

    The composed model is stepped through `Go2Z1MujocoHAL` — the same HAL the
    deploy graph uses, so the arm is held by the same sticky qpos snap and the
    legs by the same PD law. `settle_steps` realises the checkpoint's
    `step_dt: 0.02` exactly (10 × the 2 ms MJCF timestep) instead of leaning on
    a wall-clock idle stepper.

    Both the policy and MuJoCo are deterministic, so one rollout per pose is a
    single sample of a chaotic process — and the first battery run produced
    exactly the trap that warns of: `home` fell at 0.7 s while `ready`, whose
    static offset is 17 mm *worse*, walked the full 30 s. `perturbation` scales
    a seeded randomisation of the initial state (base yaw, leg positions, leg
    velocities) so `walk_battery` can report a survival rate instead of an
    anecdote. `trial` seeds it; `perturbation=0` reproduces the nominal rollout.

    `proprio_age_ticks` delays the whole observation bundle by that many policy
    ticks before the policy sees it. This loop reads the HAL in-process and so
    is the one thing a deploy graph can never be: zero-age. There the HAL
    snapshots proprio on its executor thread, a publisher thread emits
    `/odom` + `/joint_states`, and the WorldState aggregator caches them for
    `aggregator.snapshot()`. The bundle is delayed as a unit because the live
    path carries it in one `ProprioFrame`. The sweep this exists for found a
    sharp cliff — see `PROPRIO_AGE_CLIFF_TICKS` — which is the measured reason
    `scenes/deploy/go2_z1_walk.yaml` runs its publishers at 200 Hz.
    """
    from types import SimpleNamespace

    from openral_core import Action, RobotDescription
    from openral_core.schemas import VLASpec
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_JOINT_NAMES, Go2Z1MujocoHAL
    from openral_sim.factory import make_policy
    from openral_sim.policies.rsl_rl_onnx import RSL_RL_ONNX_FAMILY

    model, _, path = compose(arm_mass_scale)
    decimation = max(1, round(WALK_STEP_DT_S / float(model.opt.timestep)))
    description = RobotDescription.from_yaml(str(_MANIFEST))
    hal = Go2Z1MujocoHAL(
        description=description,
        mjcf_path=str(path),
        settle_steps=decimation,
        gravity_enabled=True,
        staleness_limit_s=1e9,
    )
    hal.connect()
    policy = make_policy(
        SimpleNamespace(  # type: ignore[arg-type]  # reason: the adapter reads only .vla / .scene (see tests/unit/test_rsl_rl_onnx_adapter.py)
            vla=VLASpec(
                id=RSL_RL_ONNX_FAMILY,
                weights_uri=str(_WALK_MANIFEST.parent),
                device="cpu",
                extra={"velocity_commands": list(velocity_commands)},
            ),
            scene=SimpleNamespace(cameras=()),
        )
    )
    policy.reset()

    # A 19-D Hub-stand row is the arm command the HAL captures as its sticky
    # hold — the same contract `rskill-zero-go2_z1-arm_ready-fp32` uses.
    if arm is not None:
        hal.reset_to_pose([*GO2_HOME_JOINT_TARGETS, *arm])
    held = tuple(float(value) for value in hal.arm_hold_pose)
    if perturbation > 0.0:
        _perturb_initial_state(hal, seed=trial, scale=perturbation)
    start = np.asarray(hal.base_pose_6dof()[0], dtype=np.float64)[:2]
    # The jaw is index 6 and is read back normalised, so hold-fidelity is judged
    # on the six revolute joints that carry the mass.
    servo_names = list(GO2_Z1_ARM_JOINT_NAMES[:6])
    servo_targets = list(held[:6])

    ticks = max(1, round(seconds / WALK_STEP_DT_S))
    tipped = False
    max_tilt = 0.0
    min_height = float("inf")
    drift = 0.0
    contacts = 0
    elapsed = 0.0
    distance = 0.0
    lateral = 0.0
    # Primed empty, so the first `proprio_age_ticks` ticks see the oldest frame
    # available rather than a fabricated one — the same ramp a live graph shows
    # when a skill starts before a fresh snapshot lands.
    bundles: deque[dict[str, Any]] = deque(maxlen=proprio_age_ticks + 1)
    try:
        for tick in range(ticks):
            state = hal.read_state()
            xyz, quat_xyzw = hal.base_pose_6dof()
            bundles.append(
                {
                    "joint_pos": list(state.position),
                    "joint_vel": list(state.velocity),
                    "base_twist": tuple(float(value) for value in hal.base_twist),
                    "base_pose": {
                        "xyz": tuple(float(value) for value in xyz),
                        "quat_xyzw": tuple(float(value) for value in quat_xyzw),
                    },
                }
            )
            # The command is not proprio and is never delayed.
            observation: dict[str, Any] = {
                **bundles[0],
                "velocity_commands": list(velocity_commands),
            }
            targets = np.asarray(policy.step(observation, ""), dtype=np.float64)
            hal.send_action(
                Action(
                    control_mode="joint_position",
                    horizon=1,
                    joint_targets=[[float(value) for value in targets]],
                    stamp_ns=0,
                )
            )
            xyz, quat_xyzw = hal.base_pose_6dof()
            elapsed = (tick + 1) * WALK_STEP_DT_S
            planar = np.asarray(xyz, dtype=np.float64)[:2]
            distance = float(np.hypot(*(planar - start)))
            lateral = max(lateral, abs(float(planar[1] - start[1])))
            tilt = _tilt_off_vertical(quat_xyzw)
            max_tilt = max(max_tilt, tilt)
            min_height = min(min_height, float(xyz[2]))
            after = hal.read_state()
            positions = dict(zip(after.name, after.position, strict=True))
            drift = max(
                drift,
                *(
                    abs(positions[name] - value)
                    for name, value in zip(servo_names, servo_targets, strict=True)
                ),
            )
            if _arm_is_touching(hal):
                contacts += 1
            if tilt > TIP_TILT_RAD:
                tipped = True
                break
    finally:
        hal.disconnect()

    return WalkRollout(
        pose=pose,
        arm_mass_scale=arm_mass_scale,
        velocity_commands=velocity_commands,
        commanded_s=seconds,
        survived_s=round(elapsed, 3),
        distance_m=round(distance, 3),
        speed_m_s=round(distance / elapsed if elapsed else 0.0, 3),
        tipped=tipped,
        max_tilt_rad=round(max_tilt, 4),
        min_base_height_m=round(min_height, 4),
        arm_drift_rad=round(drift, 4),
        arm_contacts=contacts,
        proprio_age_ticks=proprio_age_ticks,
        lateral_drift_m=round(lateral, 3),
    )


def _perturb_initial_state(hal: Any, *, seed: int, scale: float) -> None:
    """Randomise the initial base yaw and leg state, seeded by *seed*.

    Arm joints are left exactly on the pose under test — perturbing them would
    confound the very thing being compared.
    """
    import mujoco as mj
    from openral_hal.go2_z1 import GO2_Z1_LEG_JOINT_NAMES

    # The HAL has no state-injection API; this tool is a probe, so reach in.
    model = hal._model
    data = hal._data
    rng = np.random.default_rng(seed)
    yaw = float(rng.uniform(-0.15, 0.15)) * scale
    data.qpos[3] = np.cos(yaw / 2.0)
    data.qpos[4] = 0.0
    data.qpos[5] = 0.0
    data.qpos[6] = np.sin(yaw / 2.0)
    for name in GO2_Z1_LEG_JOINT_NAMES:
        joint = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, name)
        data.qpos[model.jnt_qposadr[joint]] += float(rng.uniform(-0.03, 0.03)) * scale
        data.qvel[model.jnt_dofadr[joint]] += float(rng.uniform(-0.10, 0.10)) * scale
    mj.mj_forward(model, data)


@dataclass(frozen=True)
class WalkBattery:
    """A pose's rollouts over randomised initial conditions.

    Attributes:
        pose: Named arm pose.
        arm_mass_scale: Composition scale the arm inertias were built with.
        trials: Rollouts run.
        survived: How many reached `commanded_s` upright.
        median_distance_m: Median base displacement across trials.
        median_speed_m_s: Median tracked speed, against the commanded `vx`.
        worst_survived_s: Earliest tip, or `commanded_s` when none tipped.
        max_arm_drift_rad: Worst arm-hold error over every trial.
        proprio_age_ticks: Observation age every trial ran at.
        max_lateral_drift_m: Worst lateral creep over every trial.
        tip_times_s: Sorted tip times, so a cliff shows its shape (early
            collapse vs a late scattered tail) and not just a count.
    """

    pose: str
    arm_mass_scale: float
    trials: int
    survived: int
    median_distance_m: float
    median_speed_m_s: float
    worst_survived_s: float
    max_arm_drift_rad: float
    proprio_age_ticks: int = 0
    max_lateral_drift_m: float = 0.0
    tip_times_s: tuple[float, ...] = ()


def walk_battery(
    *,
    arm: tuple[float, ...] | None,
    pose: str,
    arm_mass_scale: float,
    velocity_commands: tuple[float, float, float],
    seconds: float,
    trials: int,
    perturbation: float,
    proprio_age_ticks: int = 0,
) -> tuple[WalkBattery, list[WalkRollout]]:
    """Run *trials* randomised rollouts of one pose and summarise them."""
    rollouts = [
        walk(
            arm=arm,
            pose=pose,
            arm_mass_scale=arm_mass_scale,
            velocity_commands=velocity_commands,
            seconds=seconds,
            trial=trial,
            perturbation=perturbation,
            proprio_age_ticks=proprio_age_ticks,
        )
        for trial in range(trials)
    ]
    summary = WalkBattery(
        pose=pose,
        arm_mass_scale=arm_mass_scale,
        trials=trials,
        survived=sum(1 for row in rollouts if not row.tipped),
        median_distance_m=round(float(np.median([row.distance_m for row in rollouts])), 3),
        median_speed_m_s=round(float(np.median([row.speed_m_s for row in rollouts])), 3),
        worst_survived_s=round(min(row.survived_s for row in rollouts), 3),
        max_arm_drift_rad=round(max(row.arm_drift_rad for row in rollouts), 4),
        proprio_age_ticks=proprio_age_ticks,
        max_lateral_drift_m=round(max(row.lateral_drift_m for row in rollouts), 3),
        tip_times_s=tuple(sorted(row.survived_s for row in rollouts if row.tipped)),
    )
    return summary, rollouts


def _arm_is_touching(hal: Any) -> bool:
    """True when any arm body is in contact with the robot or the ground."""
    import mujoco as mj

    # The HAL exposes no contact accessor; this tool is a probe, so reach in.
    model = hal._model
    data = hal._data
    for index in range(int(data.ncon)):
        contact = data.contact[index]
        for geom in (int(contact.geom1), int(contact.geom2)):
            body = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, model.geom_bodyid[geom]) or ""
            if body.startswith(ARM_BODY_PREFIXES):
                return True
    return False


def _tilt_off_vertical(quat_xyzw: tuple[float, ...]) -> float:
    """Angle between the base's own z-axis and world up, radians."""
    from openral_sim.policies.rsl_rl_onnx import projected_gravity_from_quat_xyzw

    gravity = projected_gravity_from_quat_xyzw(np.asarray(quat_xyzw, dtype=np.float32))
    return float(np.arccos(float(np.clip(-gravity[2], -1.0, 1.0))))


def _print_measurements(rows: list[BalanceMeasurement]) -> None:
    print(f"{'pose':8s} {'offset':>10s} {'trot':>10s} {'static':>10s} {'com_z':>8s} {'self':>5s}")
    for row in rows:
        print(
            f"{row.pose:8s} {row.com_offset_mm:8.2f}mm {row.trot_margin_mm:8.2f}mm "
            f"{row.static_margin_mm:8.2f}mm {row.com_height_m:8.4f} {row.self_contacts:5d}"
        )


def _print_stale_row(battery: WalkBattery) -> None:
    """One line per observation age, printed as the sweep runs.

    Streamed rather than collected because a full sweep is minutes of real
    rollouts and the cliff is visible from the first two rows.
    """
    age_ms = battery.proprio_age_ticks * WALK_STEP_DT_S * 1000.0
    tips = ", ".join(f"{t:.1f}" for t in battery.tip_times_s) or "none"
    print(
        f"  age={battery.proprio_age_ticks:d} tick ({age_ms:4.0f} ms) "
        f"survived={battery.survived:2d}/{battery.trials:<2d} "
        f"median_distance={battery.median_distance_m:6.3f}m "
        f"lateral={battery.max_lateral_drift_m:6.3f}m  tips@[{tips}]"
    )


def _quiet_per_step_logs() -> None:
    """Hold structlog to the `OPENRAL_LOG_LEVEL` floor and send it to stderr.

    Two fixes for one problem. Unconfigured, structlog emits every `log.debug`,
    and `walk` makes one `hal.send_action` record per 20 ms tick — thousands of
    lines around the measurement this tool exists to print. It also writes them
    to **stdout**, which interleaves them into `--json` and leaves the caller
    parsing "Extra data".
    """
    import structlog
    from openral_observability.logging import resolve_log_level

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(resolve_log_level()),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )


def main(argv: list[str] | None = None) -> int:
    """Measure, search, or walk. Returns a process exit code."""
    _quiet_per_step_logs()
    # `--json` hangs off a shared parent so it is accepted on either side of the
    # subcommand — `walk --json` is what a caller reaches for first.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable records")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], parents=[common])
    sub = parser.add_subparsers(dest="mode", required=True)

    measure_parser = sub.add_parser(
        "measure", help="balance of each named Z1 pose", parents=[common]
    )
    measure_parser.add_argument("--arm-mass-scale", type=float, default=HONEST_ARM_MASS_SCALE)

    search_parser = sub.add_parser(
        "search", help="sweep the Z1 range for centred poses", parents=[common]
    )
    search_parser.add_argument("--arm-mass-scale", type=float, default=HONEST_ARM_MASS_SCALE)
    search_parser.add_argument("--steps", type=int, default=9, help="samples per joint")
    search_parser.add_argument("--top", type=int, default=10)
    search_parser.add_argument(
        "--limit-margin",
        type=float,
        default=0.15,
        help="radians of headroom kept inside every joint limit",
    )

    walk_parser = sub.add_parser("walk", help="rsl-rl rollout per arm pose", parents=[common])
    walk_parser.add_argument("--arm-mass-scale", type=float, default=HONEST_ARM_MASS_SCALE)
    walk_parser.add_argument(
        "--pose",
        action="append",
        default=None,
        help="repeatable; a named pose, or `spawn` to walk on the twin's own spawn hold",
    )
    walk_parser.add_argument("--seconds", type=float, default=30.0)
    walk_parser.add_argument(
        "--velocity", type=float, nargs=3, default=(0.5, 0.0, 0.0), metavar=("VX", "VY", "YAW")
    )
    walk_parser.add_argument(
        "--trials", type=int, default=8, help="randomised initial conditions per pose"
    )
    walk_parser.add_argument(
        "--perturbation",
        type=float,
        default=1.0,
        help="scale of the initial-state randomisation; 0 = deterministic nominal rollout",
    )

    stale_parser = sub.add_parser(
        "stale",
        help="sweep observation age to locate the proprio freshness cliff",
        parents=[common],
    )
    stale_parser.add_argument(
        "--arm-mass-scale",
        type=float,
        default=LIVE_ARM_MASS_SCALE,
        help="defaults to the deploy scene's scale, so the sweep matches the live graph",
    )
    stale_parser.add_argument("--pose", default="ready", help="single named pose, or `spawn`")
    stale_parser.add_argument(
        "--age",
        action="append",
        type=int,
        default=None,
        help=f"repeatable observation age in policy ticks; default {list(PROPRIO_AGE_SWEEP)}",
    )
    stale_parser.add_argument("--seconds", type=float, default=30.0)
    stale_parser.add_argument(
        "--velocity", type=float, nargs=3, default=(0.5, 0.0, 0.0), metavar=("VX", "VY", "YAW")
    )
    stale_parser.add_argument("--trials", type=int, default=8)
    stale_parser.add_argument("--perturbation", type=float, default=1.0)

    args = parser.parse_args(argv)
    poses = named_poses()

    if args.mode == "measure":
        model, data, _ = compose(args.arm_mass_scale)
        rows = [measure(model, data, arm, pose=name) for name, arm in poses.items()]
        if args.json:
            print(json.dumps([asdict(row) for row in rows], indent=2))
        else:
            print(
                f"composed at arm_mass_scale={args.arm_mass_scale:g}: "
                f"{rows[0].total_mass_kg} kg total, {rows[0].arm_mass_kg} kg arm"
            )
            _print_measurements(rows)
        return 0

    if args.mode == "search":
        model, data, _ = compose(args.arm_mass_scale)
        found = search(model, data, steps=args.steps, limit_margin_rad=args.limit_margin)
        best = found[: args.top]
        if args.json:
            print(json.dumps([asdict(row) for row in best], indent=2))
        else:
            print(f"{len(found)} collision-free candidates; best {len(best)} by offset:")
            for row in best:
                print(
                    f"  offset={row.com_offset_mm:6.2f}mm trot={row.trot_margin_mm:6.2f}mm "
                    f"com_z={row.com_height_m:.4f} arm={row.arm[:4]}"
                )
        return 0

    if args.mode == "stale":
        if args.pose not in poses and args.pose != "spawn":
            parser.error(f"unknown pose {args.pose!r}; have {['spawn', *sorted(poses)]}")
        ages = args.age or list(PROPRIO_AGE_SWEEP)
        velocity_stale: tuple[float, float, float] = (
            float(args.velocity[0]),
            float(args.velocity[1]),
            float(args.velocity[2]),
        )
        sweep: list[WalkBattery] = []
        for age in ages:
            summary, _ = walk_battery(
                arm=None if args.pose == "spawn" else poses[args.pose],
                pose=args.pose,
                arm_mass_scale=args.arm_mass_scale,
                velocity_commands=velocity_stale,
                seconds=args.seconds,
                trials=args.trials,
                perturbation=args.perturbation,
                proprio_age_ticks=max(0, age),
            )
            sweep.append(summary)
            if not args.json:
                _print_stale_row(summary)
        if args.json:
            print(json.dumps([asdict(row) for row in sweep], indent=2))
        return 0

    # `spawn` is not a named pose but the absence of one: walk on whatever the
    # twin came up holding, which is what a `deploy sim` walk does by default.
    selected = args.pose or ["spawn", *sorted(poses)]
    unknown = [name for name in selected if name not in poses and name != "spawn"]
    if unknown:
        parser.error(f"unknown pose(s) {unknown}; have {['spawn', *sorted(poses)]}")
    velocity: tuple[float, float, float] = (
        float(args.velocity[0]),
        float(args.velocity[1]),
        float(args.velocity[2]),
    )
    batteries: list[WalkBattery] = []
    every_rollout: list[WalkRollout] = []
    for name in selected:
        summary, rollouts = walk_battery(
            arm=None if name == "spawn" else poses[name],
            pose=name,
            arm_mass_scale=args.arm_mass_scale,
            velocity_commands=velocity,
            seconds=args.seconds,
            trials=args.trials,
            perturbation=args.perturbation,
        )
        batteries.append(summary)
        every_rollout.extend(rollouts)
    if args.json:
        print(
            json.dumps(
                {
                    "batteries": [asdict(battery) for battery in batteries],
                    "rollouts": [asdict(roll) for roll in every_rollout],
                },
                indent=2,
            )
        )
    else:
        print(
            f"rsl-rl battery at arm_mass_scale={args.arm_mass_scale:g}, velocity={velocity}, "
            f"{args.seconds:g} s commanded, {args.trials} trials "
            f"(perturbation={args.perturbation:g})"
        )
        for battery in batteries:
            print(
                f"  {battery.pose:8s} survived={battery.survived:2d}/{battery.trials:<2d} "
                f"median_distance={battery.median_distance_m:6.3f}m "
                f"median_speed={battery.median_speed_m_s:.3f}m/s "
                f"worst_survived={battery.worst_survived_s:6.2f}s "
                f"arm_drift={battery.max_arm_drift_rad:.4f}rad"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
