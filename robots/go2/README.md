# `go2` — Robot description

Canonical `RobotDescription` manifest for the **Unitree Go2** quadruped —
a 12-DoF robot (4 legs × hip / thigh / calf). The same manifest covers
the real Unitree Go2 (over `unitree_sdk2`, not yet implemented) and the
real-physics MuJoCo digital twin (`Go2MujocoHAL` on the
`mujoco_menagerie` `unitree_go2` MJCF).

## What this is — and what it isn't

This is a **sim-only** Unitree Go2: HAL + manifest + two deploy scenes.
`hal.real` is null, so `openral deploy run` is refused. **Go2 Edu**
(extra cameras / compute) is a separate follow-up. There is no
`BODY_TWIST` / `cmd_vel` contract.

The twin has a floating base. With no policy it falls under gravity, so
the HAL default (`hal.parameters.defaults.gravity_enabled`) is `false`.
Two scenes override that:

| Scene | Gravity | What it is for |
| --- | --- | --- |
| [`scenes/deploy/go2_bench.yaml`](../../scenes/deploy/go2_bench.yaml) | off | HAL pipe proof: 12-DoF layout, lifecycle, camera rig, Hub stand |
| [`scenes/deploy/go2_walk.yaml`](../../scenes/deploy/go2_walk.yaml) | on (+ collidable ground, 200 Hz proprio) | rsl-rl ONNX locomotion (`rskills/rsl-rl-onnx-go2-velocity-flat`) |

The same 12-DoF skill runs on the Go2 + Z1 composite
([`robots/go2_z1/`](../go2_z1/)) — the runner hold-pads the arm.

The bench is the right tool for verifying:

- 12-DoF joint-position action layout,
- lifecycle wiring (`connect → read_state → send_action → estop`),
- joint indexing and ordering (FL, FR, RL, RR × hip / thigh / calf),
- `RobotDescription` round-trip,
- the generic camera rig splicing third-person `top` into the bare MJCF
  (`front` is declared, `sim_render: false` — no EGL).

The walk scene is the right tool for a locomotion policy. ACM pairs on
that scene are **stand-justified, not gait-swept** — a genuine
base↔calf contact mid-stride is admitted rather than caught. Sim-only
containment until a real HAL lands.

## At a glance

| Field | Value |
| --- | --- |
| `name` | `go2` |
| `embodiment_kind` | `quadruped` |
| Joints | 12 actuated (4 × hip / thigh / calf). The MJCF's free joint is implicit world state and is NOT enumerated in `joints`. |
| End-effectors | none |
| Sensors | `front` declared (`observation.images.front`, `sim_render: false` — no EGL) plus viz-only `top` (3/4 overview; the live twin). Hardware radar / Edu extras are **not** declared. |
| Embodiment tags | `go2`, `unitree_go2`, `quadruped` |
| Supported VLA embodiments | `go2` |
| Supported control modes | `joint_position` (no `body_twist` this spike) |
| Locomotion | `quadruped` |
| `sdk_kind` | `open` (menagerie model BSD-3-Clause Unitree + `mujoco` Apache-2.0) |
| `hal.sim` | `openral_hal.go2:Go2MujocoHAL` (`deploy sim`) |
| `hal.real` | _null_ — sim-only (`deploy run` raises `ROSCapabilityMismatch`) |

## Attribution

MJCF: DeepMind [`mujoco_menagerie/unitree_go2`](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_go2)
(BSD-3-Clause, Copyright Unitree Robotics), derived from
[`unitreerobotics/unitree_ros`](https://github.com/unitreerobotics/unitree_ros)
`go2_description`. Fetched lazily via `robot_descriptions`
(`rd:go2_mj_description` / `rd:go2_description`). Not vendored in this repo.

## Joints

Canonical order (matches the menagerie MJCF actuators after
`mujoco_menagerie#148` and `Action.joint_targets[i]`):

| Index | Name | Range (rad) | Effort (N·m) |
| ---: | --- | --- | ---: |
| 0 | `FL_hip_joint` | ±1.0472 | 23.7 |
| 1 | `FL_thigh_joint` | −1.5708 – 3.4907 | 23.7 |
| 2 | `FL_calf_joint` | −2.7227 – −0.83776 | 45.43 |
| 3 | `FR_hip_joint` | ±1.0472 | 23.7 |
| 4 | `FR_thigh_joint` | −1.5708 – 3.4907 | 23.7 |
| 5 | `FR_calf_joint` | −2.7227 – −0.83776 | 45.43 |
| 6 | `RL_hip_joint` | ±1.0472 | 23.7 |
| 7 | `RL_thigh_joint` | −0.5236 – 4.5379 | 23.7 |
| 8 | `RL_calf_joint` | −2.7227 – −0.83776 | 45.43 |
| 9 | `RR_hip_joint` | ±1.0472 | 23.7 |
| 10 | `RR_thigh_joint` | −0.5236 – 4.5379 | 23.7 |
| 11 | `RR_calf_joint` | −2.7227 – −0.83776 | 45.43 |

Calf range **excludes 0**. `connect()` loads menagerie keyframe `home`
for free-joint height, then snaps actuated joints to Hub
`params/deploy.yaml` `default_joint_pos` (hip ±0.1, thigh 0.9, calf
−1.8). Menagerie keyframe hips are 0.0 — that delta is closed on
purpose so rsl-rl `joint_pos_rel` is zero at stand. Velocity limits in the manifest
are halved published-spec values (hip/thigh 30.1 rad/s, calf 15.70
rad/s) for the safety envelope.

The menagerie MJCF uses torque `<motor>` actuators. `Go2MujocoHAL`
runs a software PD loop every `mj_step` (same as `H1MujocoHAL`) so
the public contract stays position targets in radians. Hub
`deploy.yaml` PD (`stiffness` 20/20/40, `damping` 1/1/2) is **not**
the walk default — HAL `kp` saturates `ctrlrange` at 1 rad error
(`kv = 0.05 * kp`) so estop / home holds stay conservative. A hop-stand
`ResetToPose` sits the feet on z=0 and **keeps** walk PD. Isaac hop
`kp=20 kd=0.5` sags the calves on these torque motors.

## Detect & deploy

`openral detect` still classifies Unitree DDS (`/lowstate`, `/lowcmd`)
as `unitree_g1` — those topics are shared across Go2 / G1 / H1 and
this spike does **not** invent a distinguisher. Select the Go2
manifest explicitly:

```bash
openral doctor
openral deploy sim --config scenes/deploy/go2_bench.yaml
# gravity on + rsl-rl ONNX (see the scene header for the ExecuteRskill goal):
openral deploy sim --config scenes/deploy/go2_walk.yaml --dashboard --foxglove
# laptop kinematic MuJoCo window (qpos, not cricket EGL pixels):
openral viz mujoco --dashboard http://127.0.0.1:4318
```

`--dry-run` resolves the HAL registry + `hal_mode=sim` without
bringing up ROS. Gravity is pinned off in this manifest's
`hal.parameters.defaults` (consumed by `build_hal`, not a ROS param);
`go2_walk.yaml` overlays `gravity_enabled: true`. Real hardware
(`deploy run`) is refused until `hal.real` is filled in.

## Pair with

| Component | Path |
| --- | --- |
| Python HAL adapter | `openral_hal.go2.Go2MujocoHAL` (MuJoCo digital twin) |
| Python description | `openral_hal.GO2_DESCRIPTION` |
| Deploy bench (gravity off) | [`scenes/deploy/go2_bench.yaml`](../../scenes/deploy/go2_bench.yaml) |
| Deploy walk (gravity on) | [`scenes/deploy/go2_walk.yaml`](../../scenes/deploy/go2_walk.yaml) |
| Locomotion rSkill | [`rskills/rsl-rl-onnx-go2-velocity-flat`](../../rskills/rsl-rl-onnx-go2-velocity-flat/) |
| Hop rSkill | [`rskills/rsl-rl-onnx-go2-spring-jump`](../../rskills/rsl-rl-onnx-go2-spring-jump/) (gym spring_jump ONNX; feet leave the floor higher than the scripted bounce). Apply sits the spring-jump stand on z=0 and keeps walk PD. The mjlab ONNX ([`rsl-rl-onnx-go2-hop-flat`](../../rskills/rsl-rl-onnx-go2-hop-flat/)) only crouches on this HAL. Scripted [`rskill-zero-go2-hop-fp32`](../../rskills/rskill-zero-go2-hop-fp32/) stays as fallback. |
| Composite sibling | [`robots/go2_z1/`](../go2_z1/) |
| ROS lifecycle node | `packages/openral_hal_go2` (also hosts `robots/go2_z1`) |
| Sim test | `tests/sim/test_go2_hal_mujoco.py` |
| Future real-HW HAL | not started — `unitree_sdk2` + locomotion controller |

## Remaining gaps (pipe_gate-quality smoke)

- No `BODY_TWIST` / `cmd_vel` (HAL publishes `base_pose_6dof` +
  `base_twist` for rsl-rl obs via `/odom`; no `mobile_base` tag until a
  cmd_vel contract exists). Walking is the 12-D `JOINT_POSITION`
  rsl-rl ONNX skill on `go2_walk`, not a gait inside the HAL.
- No real HAL (`hal.real` is null).
- No authored collision geometry / ACM (`openral collision lower` not run).
  Deploy may still MJCF-lower self-collision capsules. ACM rest should
  use Hub `default_joint_pos` / `GO2_HOME_JOINT_TARGETS` (hip ±0.1),
  not menagerie hip 0.0. Attached-payload collision stays **off**:
  this robot has no end-effector and never publishes
  `/openral/attachment_state`. Enabling that gate fail-closes every
  WorldState snapshot as `DROP_ATTACHED_OVERFLOW`
  (`attachment_stamp_ns == 0`) and drops scripted `JOINT_POSITION`.
- Front-camera intrinsics are nominal, not calibrated. The spliced
  `front` cam looks at camera-rig staging (infinite checker + skybox),
  not a task scene — a flat gray floor used to look zoomed-in in Foxglove.
- Hardware radar / Go2 Edu cameras / compute are undeclared.
- `openral detect` does not distinguish Go2 from G1/H1 on DDS.

## Tests

- Sim: `tests/sim/test_go2_hal_mujoco.py` exercises `Go2MujocoHAL`
  against real MuJoCo physics on the Menagerie MJCF: lifecycle,
  schema-drift guard, home-keyframe rest, per-leg convergence.
- Unit: `tests/unit/test_robot_manifests_match_hal_constants.py` pins
  this YAML to `GO2_DESCRIPTION`.
- HIL: none — no real HAL.

## See also

- [`python/hal/README.md`](../../python/hal/README.md) — `Go2MujocoHAL`.
- [`robots/go2_z1/`](../go2_z1/) — same legs, Z1 arm bolted on `base`.
- [`robots/g1/`](../g1/) / [`robots/h1/`](../h1/) — Unitree humanoid
  siblings this spike mirrors.
- [`docs/architecture/repo-state-map.html`](../../docs/architecture/repo-state-map.html)
  — HAL · Unitree Go2 (sim, MuJoCo).
