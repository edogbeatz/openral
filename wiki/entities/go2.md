---
type: entity
tags: [openral, go2, unitree, quadruped, hal, sim]
updated: 2026-09-16
---

# Unitree Go2

Quadruped, **sim-only spike**. Manifest `robots/go2/robot.yaml`, HAL
`openral_hal.go2:Go2MujocoHAL`, deploy scene `scenes/deploy/go2_bench.yaml`.
Normative detail stays in the manifest and `robots/go2/README.md`.

`hal.real` is `null`, so `openral deploy run` is refused. There is no
locomotion controller, so the floating-base twin falls over under
gravity: the scene and the sim tests run `gravity_enabled=False`. Today
the twin is a **contract validator**, not a walking robot.

## Shape

- 12 actuated joints, `FL / FR / RL / RR × (hip, thigh, calf)`. The MJCF
  free joint is implicit world state and is deliberately not enumerated.
- Root TF frame is **`base`** (matches `base_frame`; no static transform
  needed). Not `base_link` — see [[concepts/deploy-sim-visualization]],
  where a wrong follow frame draws an empty 3D panel.
- Assets are `robot_descriptions` refs: `rd:go2_description` (URDF),
  `rd:go2_mj_description` (MJCF). Limits are verbatim from the official
  Unitree URDF; rear thighs have a wider range than the front pair.
- `collision_geometry` is empty this spike; deploy still lowers
  self-collision capsules from the menagerie model. ACM rest-pose
  excludes must use the Hub stand, not `q=0`.

## Torque motors change the idle path

Go2 MJCF actuators are `<motor>` (torque), not position servos. The HAL
recomputes `tau = kp*(target-q) - kv*dq` in `_per_step_update` every
step, and Go2 additionally overrides `send_action`, `reset_to_pose`, and
`idle_step` to PD-hold `_hold_targets`.

> The base `MujocoArmHAL.idle_step` leaves `ctrl` untouched, which is
> correct for position actuators and a **constant-N·m fold** here:
> writing home angles into `ctrl` folds the calves into their stops.

Stand pose is the Hub `deploy.yaml` `default_joint_pos`
(`GO2_HOME_JOINT_TARGETS`, hip ±0.1 / thigh 0.9 / calf −1.8) — not
menagerie keyframe hips, which are 0.0. Logged in
`docs/methods/14-duplication-watch.md` item 26 so nobody adds a second PD
helper before a third torque-MJCF robot lands.

## Cameras

| Slot | Purpose | Notes |
| --- | --- | --- |
| `front` | egocentric RGB, `observation.images.front` | official URDF `front_camera_joint` pose; frame `front_camera`; intrinsics **nominal**, not calibrated |
| `top` | third-person overview, **viz only** | menagerie `track` pose on `base`, `fovy 50°`, no `vla_feature_key` |

Both are spliced into the bare MJCF by the generic camera rig
(`openral_hal._camera_rig`) — the menagerie model ships no `<camera>`.
`top` exists because `front` looks +X out of the snout and can never show
the body. The generated Foxglove layout therefore leads with `top`.

## Policies

`rsl_rl_onnx` is the proprio-only Isaac Lab / rsl-rl ONNX locomotion
family (BSD-3-Clause weights, in-process ONNX Runtime, 12-D
`JOINT_POSITION`); first checkpoint
`diasAiMaster/unitree-go2-velocity-flat`, aligned to the Hub's trained
conditions. It is not a VLM and not SmolVLA.

## Undeclared on purpose

Hardware face radar (no calibrated lidar spec in tree), Go2 Edu extra
cameras and compute, `body_twist` control mode. `openral detect` cannot
tell a Go2 from a G1/H1 on DDS.

## Seeing it run

[[concepts/deploy-sim-visualization]] for the viewer,
[[entities/openral-foxglove-bringup]] for the bridge,
[[analyses/foxglove-web-meshes-need-package-uri]] for why the meshes
need `package://`, and
[[analyses/proving-sim-motion-not-a-frozen-stand]] for how to tell a
real trot from a frozen stand. Operator runbook (cricket host, layout
generator, `march.sh`): `.agents/skills/go2-foxglove-view/SKILL.md`.
