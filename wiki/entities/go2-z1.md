---
type: entity
tags: [openral, go2, z1, unitree, quadruped, manipulator, hal, sim]
updated: 2026-09-17
---

# Unitree Go2 + Z1

19-DoF **sim-only** composite: 12 Go2 legs + 6 Z1 arm joints + jaw.
Manifest `robots/go2_z1/robot.yaml`, HAL `openral_hal.go2_z1:Go2Z1MujocoHAL`,
walk scene `scenes/deploy/go2_z1_walk.yaml`. Real Unitree mounts the Z1
on a B1, not a Go2 — this is a sim study. `hal.real` is null.

The arm is part of the robot, not scenery: MJCF composition lives under
`scene_defaults.composition` →
`openral_sim.scene_composers:compose_mounted_arm_mjcf` (arm last on
`base` so leg indices stay 0–11). A scene-level `composition:` would
replace the arm mount with a bare ground plane.

Locomotion still hold-pads 12→19. The HAL keeps a **sticky** arm hold:
spawn home until Recalibrate / `arm_ready` writes it, then qpos-snaps
**arm joints only** (never legs or the free base) on every locomotion
chunk **and** idle physics step so gait cannot wave the Z1. Legs follow
the 12-D rsl-rl command. Dashboard Recalibrate parks the arm at
`GO2_Z1_ARM_READY`. **Apply skill** on the rsl-rl walk pick is the same
ONNX as bare Go2; runner pads; arm stays at that Recalibrate pose, not
limp and not chasing walk proprio. After a Go2+Z1 load the demo bar
**asks Recalibrate** (it does not auto-stand or auto-walk). Recalibrate
is the walk gate: Hub-stand legs, upright free base, Z1 at
`GO2_Z1_ARM_READY`, sticky hold latched. The picker **defaults to walk** after Recalibrate: `preferWalk` must
**override** a currently selected `arm_ready` (not only a saved one).
Keeping the dropdown `keep` value re-dispatched
`rskill-zero-go2_z1-arm_ready-fp32` (2 s Hub hold) so Apply looked
frozen. A saved `arm_ready` pick is **not** restored over walk. An HTTP 200
from Recalibrate does not prove the hold latched — cricket once ran an
older HAL without `_arm_hold_pose`. **Stop**
cancels the running skill without latching e-stop and holds Hub stand
(arm still at ready) so Apply can run again. Walk runs 60 s then `deadline_missed`; idle then holds the last gait
pose (fall risk) unless Stop runs first. The 12-D rsl-rl skill can also
**tip mid-gait** on this twin well before 60 s (18:05Z: ~8 s, xy
≈3.2 m, `world→base` z=0.058 roll ~180°, kernel unlatched). Cameras are the same Go2
`front` + `top` slots; the dashboard always shows both. **End Cricket** stops the
GPU session; **Stop** keeps the sim. To retarget the Z1 after
that, pick `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32`
(`model_family: zero`): a 19-D `JOINT_POSITION` hold, default pose
`ready`. `goal_params_json` `{pose: home|ready|fold}` or a 7-D `arm`
list.

## Joint order is load-bearing

Legs occupy indices **0–11**, byte-identical to [[entities/go2]]. That is
why the same 12-DoF rsl-rl skill runs here: the runner hold-pads 12→19
from a frozen episode-start proprio, and `Go2Z1MujocoHAL` **qpos-snaps
the sticky arm hold (Z1 joints only)** on 12-D chunks and on 19-D walk
rows whose legs have left Hub stand. A 19-D Hub-stand row is an explicit
arm command
and updates the hold (the `rskill-zero-go2_z1-arm_ready-fp32` /
Recalibrate path). Zero-filling the pad folds the Z1 position servos
to 0.

`arm_mass_scale: 0.01` on the composition shrinks arm inertias so the
bare-Go2 walk skill stays upright; full menagerie mass tips within a few
metres. Meshes/kinematics unchanged. After a tip, dashboard **Stand** /
**Recalibrate** (write-controls) call `reset_to_pose`, which also
`_snap_base_upright` — joint-only reset leaves the free base on its side.
Go2+Z1 Recalibrate uses Hub stand + arm-ready, not menagerie arm home.

Embodiment tags include `go2` so the skill capability gate intersects.

## Control split

| Joints | Actuators | Drive |
| --- | --- | --- |
| Legs 0–11 | torque `<motor>` | software PD (same law as Go2) |
| Arm + jaw 12–18 | position servos | ctrl = radians target; qpos-snapped to sticky hold |

Idle ticks PD-hold the legs (Go2 `idle_step`) and snap the arm to the
sticky hold. Soft servos plus gait coupling would otherwise wave the
Z1 between 50 Hz `send_action` ticks.

Related: [[entities/go2]], [[concepts/deploy-sim-visualization]],
[[analyses/proving-sim-motion-not-a-frozen-stand]]. Cricket start
failures: `.agents/skills/go2-foxglove-view/SKILL.md`.
