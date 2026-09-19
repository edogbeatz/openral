---
type: entity
tags: [openral, go2, unitree, quadruped, hal, sim]
updated: 2026-09-19
---

# Unitree Go2

Quadruped, **sim-only**. Manifest `robots/go2/robot.yaml`, HAL
`openral_hal.go2:Go2MujocoHAL`. `hal.real` is `null`, so
`openral deploy run` is refused. There is no `BODY_TWIST` / `cmd_vel`
contract. **Go2 Edu** extras are undeclared.

The twin has a floating base. With no policy it falls under gravity, so
the HAL default is `gravity_enabled=False`. Two scenes override that:

| Scene | Gravity | Role |
| --- | --- | --- |
| `scenes/deploy/go2_bench.yaml` | off | HAL pipe proof (Hub stand, cameras, lifecycle) |
| `scenes/deploy/go2_walk.yaml` | on + collidable ground, 200 Hz proprio | rsl-rl ONNX locomotion |

The same 12-DoF skill runs on [[entities/go2-z1]] via hold-pad. That
adopt is not a payload finetune
([[analyses/go2-z1-payload-walk-finetune]]). There is
**no dedicated U-turn rSkill** — see [[analyses/no-uturn-rskill]].
Dashboard hop is gym spring_jump `rskills/rsl-rl-onnx-go2-spring-jump`
([[analyses/go2-hop-candidates]]). One-shot jump under walk PD
(`air_ticks≈15`, max foot ≈0.34 m, `z_max≈0.53 m`). The mjlab ONNX
(`rsl-rl-onnx-go2-hop-flat`) only crouches on this HAL. Scripted
`rskill-zero-go2-hop-fp32` stays as fallback. Dashboard
PoC: **Load Bare Go2** (already calibrated) → pick skill → Apply; **Go2+Z1**
asks Recalibrate first, then pick skill → Apply. A **second Apply**
stops the running skill first (no e-stop) and episode-resets the
resident policy so the dog actually walks again; previously the next
skill reused last_action/horizon and stood still. **Stop** cancels the
running skill (no e-stop latch) and holds Hub stand so Apply can run again.
**End Cricket** shuts the GPU session (not Stop, not E-STOP); idle auto-Ends
after 15 min. See [[concepts/deploy-sim-visualization]]. Native-MuJoCo view without
lags is a laptop-side kinematic viewer of `qpos`, not another cricket
camera ([[analyses/mujoco-render-without-lag]]). First cut: HAL copies
`MjData.qpos` onto the existing `hal.read_state` span; dashboard
`GET /api/qpos`; laptop `openral viz mujoco --dashboard http://127.0.0.1:4318`
(`mj_forward` only). WASM in the dashboard tab is still backlog.

Normative detail stays in the manifest and `robots/go2/README.md`.

**Not upstream.** `OpenRAL/openral` master (checked 2026-09-17) has no
`robots/go2`, no `openral_hal/go2.py`, no `rsl_rl_onnx` adapter and no
rsl-rl rSkill — the whole stack is fork-only, added 2026-09-14, ~2.2k
lines now on `origin/master`. [[entities/go2-z1]] is not even on fork
master (working branch only). In-repo docs linking
`github.com/OpenRAL/openral/tree/master/robots/go2/` are fork-written
and **not** evidence of an upstream merge.

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
| `front` | egocentric RGB, `observation.images.front` | official URDF `front_camera_joint` pose; **`sim_render: false`** — not spliced, not `mjr_readPixels`; spec stays for a future VLA |
| `top` | third-person overview, **live twin** | menagerie `track` pose on `base`, `fovy 50°`, no `vla_feature_key` |

`top` is spliced into the bare MJCF by the generic camera rig
(`openral_hal._camera_rig`) — the menagerie model ships no `<camera>`.
`front` is declared but not spliced (`sim_render: false`). `top` exists
because `front` looks +X out of the snout and can never show the body.
The generated Foxglove layout is `top` only. A cricket checkout that
omits `top` makes `/simple` CAM_TOP a leftover ~1 Hz still while
[[entities/go2-z1]] looks live — sync `robots/go2/robot.yaml` and reload;
do not add a second EGL camera.

## Policies

`rsl_rl_onnx` is the proprio-only Isaac Lab / rsl-rl ONNX locomotion
family (in-process ONNX Runtime, 12-D `JOINT_POSITION`); not a VLM and
not SmolVLA. Walk customer: `diasAiMaster/unitree-go2-velocity-flat`
(BSD-3-Clause, 45-D). Dashboard hop: `rskills/rsl-rl-onnx-go2-spring-jump` (gym
spring_jump ONNX, frame-major 470-D). Measured on `go2_walk` with
walk PD: `air_ticks≈15`, max foot ≈0.34 m, `z_max≈0.53 m`. The mjlab ONNX
(`rskills/rsl-rl-onnx-go2-hop-flat`) only crouches
(`air_ticks=0`) — see [[analyses/go2-hop-candidates]]. Scripted
`rskill-zero-go2-hop-fp32` is fallback. HAL sits
every stand on z=0 and keeps walk PD (Isaac `kp=20` sags calves).
Drive either on `go2_walk`, not
`go2_bench`. ACM pairs on the walk scene are stand-justified, not
gait-swept. Demo Apply sends `velocity_commands: [0.35, 0, 0]` for up to 57 s
(`policy_extras.horizon_s`) on the walk skill. A yaw-only joystick `[0, 0, ω]` is a per-call
override, not a named U-turn. The last `coast_to_stand_s` (3 s) command
`[0, 0, 0]` so the ONNX stands the dog; the goal then succeeds.
Without that, `_drain_and_idle_hold` PD-holds the last mid-gait
waypoint under gravity and a frozen stride cannot balance. Guard:
`tests/sim/test_go2_walk_coast_mujoco.py` (HAL proprio into
`policy.step`, then idle-hold). **Stop**
on the demo bar still cancels the goal *and* snaps Hub stand (no e-stop
latch) so Apply can run again. Unset `coast_to_stand_s` on
`rsl_rl_onnx` still defaults to 3.0 s (Hub walk cards included); `0`
disables.
`GET /simple` is a simpler dashboard: Start engine, pick this twin
or [[entities/go2-z1]] from UNIT, load auto-stands (Hub stand),
then **Apply** walk from chat. Walk coasts to stand in the last 3 s.
Reset / Recalibrate recover a tip while a skill is still running or after
a fall. Live Bare walk can also tip mid-gait (2026-09-19 loop:
4/7 upright — 2.4 m, two tips, two 1.73 m passes, one walk that
started already down at z≈0.06 after Recalibrate 200, then 2.59 m)
— same Stop + Recalibrate recovery as [[entities/go2-z1]]. A
sub-metre tip (z→0.06 after 0.43 m, ~1 s at `vx=0.35`) looks like
"walks weird then falls in a couple of seconds." The runner does
**not** abort on tip, so legs keep cycling on the ground until
Stop. Hub ONNX weights did not change. This branch did: Load
overwrites cricket `rsl_rl_onnx.py` (hop/jump/coast on the shared
adapter), HAL ResetToPose now plants feet on z=0, chat forward is
`[0.5,0,0]` (demo Apply is still `[0.35,0,0]`). Live execute id is
still `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`; 60 s
`deadline_exceeded` means cricket is not on in-tree `horizon_s: 57`.
Neither checkpoint claims MuJoCo gait quality.

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
real trot from a frozen stand. The OTel dashboard always shows `top`
(side/3/4), even while WAITING; a laptop
`:4318` collector seeds those MJPEG tiles from the tunneled
`/api/state` thumb, then splices cricket `:14318` MJPEG (old cricket
graphs 404 `/latest.jpg` — do not wait on that 404). `/simple`
tiles attach `/stream` plus a sibling still; they must not SSH
`GET /api/demo/cricket` before painting.
`/simple` UNIT says **Load the unit** when nothing is loaded;
**Bare Go2** only when that twin is the live occupant or the
in-flight load — a stale `sessionStorage` `go2` pick must not
label a Go2+Z1 graph. The both-dogs skills loop stopped after
tick 7 (Bare walk 4/7); occupant left [[entities/go2-z1]].
Sim HAL publishes `/openral/cameras/top/image/compressed`
natively (same JPEG as the tiles). `front` is declared, not rendered
(`sim_render: false`) so the walk thread pays one EGL camera. Operator runbook (cricket host, layout generator,
`march.sh`, start failures): `.agents/skills/go2-foxglove-view/SKILL.md`.
Append that skill on every cricket/dashboard/Foxglove start failure.
