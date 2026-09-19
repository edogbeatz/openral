---
language:
- en
license: apache-2.0
pipeline_tag: robotics
tags:
- OpenRAL
- rskill
- zero
- go2
- go2_z1
- hop
inference: false
---

# rskill-zero-go2-hop-fp32

> **OpenRAL rSkill** — scripted **hop** for the 12-DoF Unitree Go2 sim
> twin. No neural weights. `model_family: zero` emits a repeating
> crouch → extend → tuck → land cycle so the feet leave the `go2_walk` floor.

This is **not** the simple-dashboard hop picker. Apply hop is
[`rsl-rl-onnx-go2-spring-jump`](../rsl-rl-onnx-go2-spring-jump/). This
scripted crouch-extend stays in-tree as a fallback. The mjlab hop ONNX
(`rsl-rl-onnx-go2-hop-flat`) only crouches on this torque-motor HAL
(`air_ticks=0`).

## What this skill does

Open-loop **joint-position** hop. Each tick writes a 12-D row:

| Phase | Duration | Pose |
| --- | --- | --- |
| Crouch | 0.30 s | thighs 1.70 / 1.90, calves −2.65 |
| Extend | 0.24 s | thighs 0.05 / 0.10, calves −0.84 |
| Tuck | 0.22 s | thighs 1.40 / 1.60, calves −2.30 |
| Land | 0.40 s | hop stand (thighs 0.8 / 1.0, calves −1.5) |

Measured 2026-09-19 on `go2_walk` with HAL walk PD (1 rad saturates
`ctrlrange`): `air_ticks≈45`, max foot-bottom ≈0.25 m, `z_max≈0.47 m`.
A 0.16 s extend never finished the push (calves still ~−1.4 at land).
Isaac hop PD `kp=20 kd=0.5` is **not** used — calves sag and the dog
cannot push off.

`policy_extras` carries `jump_crouch` / `jump_extend` / `jump_tuck` and
the four phase times so the cycle is set on the skill, not only in
`mock.py`. `horizon_s: 6.0` so `ExecuteRskill` succeeds after a few
cycles. No cameras.

## Upstream model / training

There is no upstream checkpoint. The adapter is
`openral_sim.policies.mock._ZeroPolicy` (`gait: jump`).

| Field | Value |
| --- | --- |
| Source | in-tree `policy_extras` + measured poses |
| License | Apache-2.0 |
| Parameters | none (scripted hop) |
| Training data | none |

## Supported robots / embodiments

| Robot | Embodiment tag | Status | Notes |
| --- | --- | --- | --- |
| Unitree Go2 | `go2` | experimental | Sim-only (`hal.real` is null) |
| Unitree Go2 + Z1 | `go2_z1` | experimental | 12-D hold-pad; arm stays frozen |

## Sensors / observation contract

Proprio-only. The policy ignores cameras and `observation.state`.

## Manifest summary

| Field | Value |
| --- | --- |
| `name` | `OpenRAL/rskill-zero-go2-hop-fp32` |
| `model_family` | `zero` |
| `weights_uri` | `local://rskills/rskill-zero-go2-hop-fp32` |
| `starting_pose` | hop stand (`GO2_HOP_JOINT_TARGETS`) |
