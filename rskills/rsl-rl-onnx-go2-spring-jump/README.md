---
language:
- en
license: other
pipeline_tag: robotics
tags:
- OpenRAL
- rskill
- rsl_rl_onnx
- vision-language-action
- go2
- go2_z1
- hop
- jump
inference: false
---

# rskill-rsl_rl_onnx-go2-spring_jump-fp32

> **OpenRAL rSkill** — Isaac Gym rsl-rl ONNX **one-shot spring jump** on
> the 12-DoF Unitree Go2. Wraps
> [`Renkunzhao/legged_rl_deploy`](https://github.com/Renkunzhao/legged_rl_deploy)
> `policies/go2/My_unitree_go2_gym/spring_jump/`. Ships no weights.
> **Not SmolVLA.** License of the ONNX is **unknown** (upstream repo has
> no GitHub license). The loader warns `rskill.unknown_license` and
> `is_commercial_use_allowed` is false.

Same `model_family: rsl_rl_onnx` as
[`rsl-rl-onnx-go2-velocity-flat`](../rsl-rl-onnx-go2-velocity-flat/) and
[`rsl-rl-onnx-go2-hop-flat`](../rsl-rl-onnx-go2-hop-flat/). Same **470-D**
width as mjlab hop, but **frame-major** (Isaac Gym `frame_stack`) with
zero warmup, plus `constants` + joystick **A** as the jump trigger.
Loading this ONNX through the mjlab hop YAML would be the wrong layout
and the dog would not jump.

This is the skill the simple-dashboard **hop** picker Applys. The mjlab
hop ONNX only crouches on this torque-motor HAL (`air_ticks=0`). The
scripted zero hop stays in-tree as a fallback.

## What this skill does

Closed-loop **joint-position** one-shot jump: read 12-D proprio + base
orientation/angular velocity, append constants `[0, 0, 0.7, 0]` and
joystick A, stack 10 full 47-D frames (oldest first, zeros until the
buffer fills), run `policy.onnx`, write
`default_joint_pos + action * 0.25` as a 12-D `JOINT_POSITION` action.
No cameras. Measured on `Go2MujocoHAL` + walk PD (`go2_walk`):
`air_ticks≈15`, max foot ≈0.34 m, `z_max≈0.53 m`, lands and recovers.

YAML `jump_trigger` default is **1.0** so Apply hops. Per-call override
via `goal_params_json` `{"jump_trigger": 0}` (or observation
`joystick_buttons`) holds the spring-jump stand without jumping.

## Upstream model

[`Renkunzhao/legged_rl_deploy`](https://github.com/Renkunzhao/legged_rl_deploy)
`policies/go2/My_unitree_go2_gym/spring_jump/policy.onnx`. Fetched at
load via `policy_extras.onnx_url` into `~/.cache/openral/rsl_rl_onnx/`.
Not vendored.

Gym hop in the same repo (`My_unitree_go2_gym/hop/`) is the same 470-D
width with scaled obs and still only crouches on this HAL. Do not swap
it in.

## Embodiment

`go2`. Same 12-D rows hold-pad 12→19 on `go2_z1`. Hop quality on the
armed twin is unclaimed — the policy trained on the bare dog. Acquire
catalog will not warrant hop on Go2+Z1 (`check=payload`).

## Sensors / observation contract

Read from `params/deploy.yaml` `observations:` (do not invent keys), in
YAML order. Each term is history-10, `oldest_first`, `zero` warmup,
packed **frame-major** (10 stacked 47-D frames, not term-major):

| Term | Width × history | OpenRAL source |
|---|---|---|
| `constants` | 4 × 10 | YAML `params.vec` `[0, 0, 0.7, 0]` |
| `joystick_buttons` | 1 × 10 | YAML `jump_trigger` (default 1) **or** per-call override |
| `base_ang_vel_B` | 3 × 10 | `WorldState.base_twist[3:6]`, scale 0.25 |
| `eulerZYX_rpy` | 3 × 10 | `base_pose.quat_xyzw` → roll/pitch/yaw |
| `joint_pos` | 12 × 10 | `q[map] − default_joint_pos[map]` |
| `joint_vel` | 12 × 10 | `dq[map]`, scale 0.05 |
| `last_action` | 12 × 10 | previous raw ONNX action |

Total **470-D**. First tick is nine zero frames then the current frame.

Default pose hips are **0.0** (not mjlab hop ±0.1). The reasoner prompt
is not mapped to the jump trigger.

Gravity-on scene: `scenes/deploy/go2_walk.yaml` (or `go2_z1_walk.yaml`).
HAL walk PD stays on a spring-jump-stand `ResetToPose`. Isaac hop
`kp=20` is not applied (calves sag on these torque motors).

## Manifest summary

| Field | Value |
|---|---|
| `model_family` | **`rsl_rl_onnx`** |
| `kind` | `vla` |
| `runtime` | `onnx` |
| `license` | `unknown` |
| `weights_uri` | `local://rskills/rsl-rl-onnx-go2-spring-jump` |
| `action_contract` | `dim: 12`, `representation: joint_positions` |

```yaml
model_family: rsl_rl_onnx
runtime: onnx
license: unknown
weights_uri: local://rskills/rsl-rl-onnx-go2-spring-jump
policy_extras:
  velocity_commands: [0.0, 0.0, 0.0]
  jump_trigger: 1.0
  onnx_filename: policy.onnx
  deploy_yaml: params/deploy.yaml
  onnx_url: https://raw.githubusercontent.com/Renkunzhao/legged_rl_deploy/master/policies/go2/My_unitree_go2_gym/spring_jump/policy.onnx
```

## License

Upstream ONNX: **unknown** (`RSkillLicensePosture.unknown`). The loader
emits `rskill.unknown_license` and does not treat `OPENRAL_ALLOW_NONCOMMERCIAL=1`
as a substitute for a real license. OpenRAL adapter code in this repo:
Apache-2.0.
