# `go2` — Robot description

Canonical `RobotDescription` manifest for the **Unitree Go2** quadruped —
a 12-DoF robot (4 legs × hip / thigh / calf). The same manifest covers
the real Unitree Go2 (over `unitree_sdk2`, not yet implemented) and the
real-physics MuJoCo digital twin (`Go2MujocoHAL` on the
`mujoco_menagerie` `unitree_go2` MJCF).

## What this is — and what it isn't

This is a **sim-only spike**: enough HAL + manifest + deploy-sim bench
to get past "no HAL entry" and publish joints + a spliced front camera.
It is **not** a polished product, a walking controller, or a real-HW
bring-up.

The MuJoCo digital twin is a **HAL contract validator**, not a useful
quadruped sim. The Go2 has a floating base and no locomotion
controller; left to its own devices it falls over under gravity. The
closed-loop sim tests and `scenes/deploy/go2_bench.yaml` therefore run
with `gravity_enabled=False`.

The twin is the right tool for verifying:

- 12-DoF joint-position action layout,
- lifecycle wiring (`connect → read_state → send_action → estop`),
- joint indexing and ordering (FL, FR, RL, RR × hip / thigh / calf),
- `RobotDescription` round-trip,
- the generic camera rig splicing the front RGB camera into the bare MJCF.

It is **not** the tool for rolling out a walking policy. Gait + balance
are the same follow-up class as G1/H1 S0 (CLAUDE.md §6.2). **Go2 Edu**
(extra cameras / compute) is a separate follow-up.

## At a glance

| Field | Value |
| --- | --- |
| `name` | `go2` |
| `embodiment_kind` | `quadruped` |
| Joints | 12 actuated (4 × hip / thigh / calf). The MJCF's free joint is implicit world state and is NOT enumerated in `joints`. |
| End-effectors | none |
| Sensors | spliced front RGB (`front` → `observation.images.front`). Hardware radar / Edu extras are **not** declared. |
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
applied — HAL `kp` saturates `ctrlrange` at 1 rad error (`kv = 0.05 * kp`)
so estop / home holds stay conservative. Documented intentional delta.

## Detect & deploy

`openral detect` still classifies Unitree DDS (`/lowstate`, `/lowcmd`)
as `unitree_g1` — those topics are shared across Go2 / G1 / H1 and
this spike does **not** invent a distinguisher. Select the Go2
manifest explicitly:

```bash
openral doctor
openral deploy sim --config scenes/deploy/go2_bench.yaml
```

`--dry-run` resolves the HAL registry + `hal_mode=sim` without
bringing up ROS. Gravity is pinned off in this manifest's
`hal.parameters.defaults` (consumed by `build_hal`, not a ROS param).
Real hardware (`deploy run`) is refused until `hal.real` is filled in.

## Pair with

| Component | Path |
| --- | --- |
| Python HAL adapter | `openral_hal.go2.Go2MujocoHAL` (MuJoCo digital twin) |
| Python description | `openral_hal.GO2_DESCRIPTION` |
| Deploy bench | [`scenes/deploy/go2_bench.yaml`](../../scenes/deploy/go2_bench.yaml) |
| ROS lifecycle node | `packages/openral_hal_go2` (manifest-driven) |
| Sim test | `tests/sim/test_go2_hal_mujoco.py` |
| Future real-HW HAL | not started — `unitree_sdk2` + locomotion controller |

## Remaining gaps (pipe_gate-quality smoke)

- No walking / BODY_TWIST control (HAL now publishes `base_pose_6dof` +
  `base_twist` for rsl-rl obs via `/odom`; no `mobile_base` tag until a
  cmd_vel contract exists).
- No real HAL (`hal.real` is null).
- No collision geometry / ACM (`openral collision lower` not run).
  When that lands, ACM rest should use Hub `default_joint_pos` /
  `GO2_HOME_JOINT_TARGETS` (hip ±0.1), not menagerie hip 0.0.
- Front-camera intrinsics are nominal, not calibrated.
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
- [`robots/g1/`](../g1/) / [`robots/h1/`](../h1/) — Unitree humanoid
  siblings this spike mirrors.
- [`docs/architecture/repo-state-map.html`](../../docs/architecture/repo-state-map.html)
  — HAL · Unitree Go2 (sim, MuJoCo).
