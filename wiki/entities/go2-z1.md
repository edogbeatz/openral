---
type: entity
tags: [openral, go2, z1, unitree, quadruped, manipulator, hal, sim]
updated: 2026-09-19
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

This is **not** a quantized or remapped arm VLA. There is no learned
Z1 policy. Embodiment adapt here is: keep the 12-D Go2 walk, park the
arm with a scripted hold, freeze it while the legs run. `/simple`
**Adapt** retags that card; it does not retune the gait. A payload-aware
walk is mjlab resume of `model_500.pt` with Z1 mass in the train env,
then a new rSkill — still 12-D legs:
[[analyses/go2-z1-payload-walk-finetune]].

Locomotion still hold-pads 12→19. The HAL keeps a **sticky** arm hold:
spawn pose until Recalibrate / `arm_ready` writes it, then qpos-snaps
**arm joints only** (never legs or the free base) on every locomotion
chunk **and** idle physics step so gait cannot wave the Z1. Legs follow
the 12-D rsl-rl command. Dashboard Recalibrate parks the arm at
`GO2_Z1_ARM_READY`. **Apply skill** on the rsl-rl walk pick is the same
ONNX as bare Go2; runner pads; arm stays at that Recalibrate pose, not
limp and not chasing walk proprio. After a Go2+Z1 load the classic demo bar
**asks Recalibrate** (it does not auto-stand or auto-walk). `/simple`
auto-stands (same Recalibrate / arm-ready) so Apply is ready. Recalibrate
is the walk gate: Hub-stand legs, upright free base, Z1 at
`GO2_Z1_ARM_READY`, sticky hold latched. The picker **defaults to walk** after Recalibrate only when the pick is
empty or `arm_ready`: `preferWalk` must **override** a currently selected
`arm_ready` (not only a saved one), and must **not** steal hop.
Keeping the dropdown `keep` value re-dispatched
`rskill-zero-go2_z1-arm_ready-fp32` (2 s Hub hold) so Apply looked
frozen. A saved `arm_ready` pick is **not** restored over walk. An HTTP 200
from Recalibrate does not prove the hold latched — cricket once ran an
older HAL without `_arm_hold_pose`. A **second Apply** stops the running
skill first (no e-stop) and episode-resets the resident policy — reuse
used to leak `last_action` / horizon so the next walk stood still.
**Stop**
cancels the running skill without latching e-stop and holds Hub stand
(arm still at ready) so Apply can run again. Walk's last 3 s command
`[0, 0, 0]` (`coast_to_stand_s`; same skill as Bare Go2) then
`horizon_s` succeeds standing. `max_execution_s: 60` is the abort
backstop. `GET /simple` loads this twin
from UNIT, auto-stands (arm-ready Recalibrate), then Apply walk / hop / arm
— Stop still snaps Hub stand. Live
2026-09-19: walk `dxy≈1.21 m` / 8 s with arm frozen at `ARM_READY`
(later ticks ~1.0–2.1 m including 1.62 m with z held ~0.33; one sag
to z≈0.15 then recovered); hop hold-pad first looked like
`z_span≈0.08 m` with feet planted (Hub-z under hop legs — same
[[analyses/go2-hop-candidates]] bury). Dashboard hop is now
`rsl-rl-onnx-go2-spring-jump` (gym spring_jump ONNX, walk PD).
`arm_ready`
202 held that pose. The 12-D rsl-rl skill can also
**tip mid-gait** on this twin well before 60 s (18:05Z: ~8 s, xy
≈3.2 m, `world→base` z=0.058 roll ~180°, kernel unlatched). `/simple`
chat treats that tip as a verify miss: **the unit fell. this skill
needs retraining or finetuning.** (same 1.0 rad gate as the
mass-balance tool; once until RESET). Cameras are
the same as [[entities/go2]]: `front` is declared (`sim_render: false`);
the dashboard shows `top` only. Cricket `go2_z1` yaml already had
`top` when Bare did not — that is why this twin looked live first
([[concepts/deploy-sim-visualization]]). **End Cricket** stops the
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
bare-Go2 walk skill stays upright; full menagerie mass was seen to tip
within a few metres **on the live graph**. Meshes/kinematics unchanged.
Headless at honest mass it does **not** tip from `GO2_Z1_ARM_READY` (8/8
randomised 20 s trials, 9.9 m) — the arm **pose**, not the arm mass, is
what decides the walk, and neither CoM offset nor pitch inertia explains
which poses fall: [[analyses/go2-z1-arm-pose-decides-the-walk]]. The twin
therefore spawns at `GO2_Z1_SPAWN_JOINT_TARGETS` (Hub stand + `ready`),
not menagerie `home`, which fell 0/8; a 12-D locomotion row leaves the
sticky hold alone, so a gait applied before Recalibrate rides the spawn
pose. Soft / "non-physical" arm motion
during walk is **expected**: sticky control hold + bare-Go2 policy, not
a broken sim. Do **not** treat heading lock as the demo path —
Recalibrate → rsl-rl walk Apply is. After a tip, dashboard **Stand** /
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

## Proprio freshness is a hard limit

The deploy scene publishes proprio at **200 Hz**
(`publish_rate_hz` / `odom_publish_rate_hz` in
`scenes/deploy/go2_z1_walk.yaml`) and that is not a throughput preference. Two
policy ticks (40 ms) of observation age drops walk survival from 8/8 to 1/8;
one tick is still 8/8. Do not lower those rates. The live graph measures a
median 5.1 ms age, so it is inside the safe band — which also **excludes**
staleness as the cause of the live mid-gait tip:
[[analyses/go2-proprio-freshness-cliff]].

Dashboard `/simple` must label this twin **Go2 + Z1** while it is
loading or live (`go2z1mujocohal` / `robot_id=go2_z1`). Empty
state is **Load the unit**, never Bare Go2. After the both-dogs
skills loop (tick 7: Z1 walk `dxy≈1.62 m`, hop/arm pass) the
operator stopped the 10 min heartbeat and healthz watcher.
Occupant left standing here. Do not start another tick.

Related: [[entities/go2]], [[concepts/deploy-sim-visualization]],
[[analyses/proving-sim-motion-not-a-frozen-stand]],
[[analyses/go2-z1-arm-pose-decides-the-walk]],
[[analyses/go2-z1-payload-walk-finetune]],
[[analyses/go2-proprio-freshness-cliff]],
[[analyses/go2-hop-candidates]] (hop already tags `go2_z1` via the
same 12→19 hold-pad; quality on the armed twin is unclaimed). Cricket
start failures: `.agents/skills/go2-foxglove-view/SKILL.md`.
