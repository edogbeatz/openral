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
inference: false
---

# rskill-rsl_rl_onnx-go2-hop_flat-fp32

> **OpenRAL rSkill** — mjlab rsl-rl ONNX **hop** on the 12-DoF Unitree
> Go2. Wraps
> [`Renkunzhao/legged_rl_deploy`](https://github.com/Renkunzhao/legged_rl_deploy)
> `policies/go2/mjlab/hop/` (`Mjlab-Hopping-Flat-Unitree-Go2`). Ships no
> weights. **Not SmolVLA.** License of the ONNX is **unknown** (upstream
> repo has no GitHub license). The loader warns `rskill.unknown_license`
> and `is_commercial_use_allowed` is false.

Same `model_family: rsl_rl_onnx` as
[`rsl-rl-onnx-go2-velocity-flat`](../rsl-rl-onnx-go2-velocity-flat/).
Different observation: **470-D**, not 45-D. Loading this ONNX through
the walk YAML would be the wrong obs and the dog would fall.

## What this skill does

Closed-loop **joint-position** hop: read 12-D proprio + base
orientation/angular velocity, append a 3-D velocity command and a 1.5 s
gait-phase clock, stack 10 frames term-major, run `policy.onnx`, write
`default_joint_pos + action * 0.25` as a 12-D `JOINT_POSITION` action.
No cameras. Does **not** claim hop quality.

## Upstream model

- **Checkpoint:** `policies/go2/mjlab/hop/policy.onnx` (~1.6 MB) in
  [Renkunzhao/legged_rl_deploy](https://github.com/Renkunzhao/legged_rl_deploy)
  (task label `Mjlab-Hopping-Flat-Unitree-Go2`).
- **Files:** `policy.onnx` fetched at load via `policy_extras.onnx_url`
  into `~/.cache/openral/rsl_rl_onnx/`. In-tree
  `params/deploy.yaml` is OpenRAL's translation of the public config
  comments (term names, widths, history 10, cycle 1.5 s, scale 0.25) —
  not a copy of the upstream YAML.
- **License:** unknown. Not Apache-2.0-cleared. Weights stay out of
  this repo until that is settled.
- Same repo also ships `spring_jump/` (one-shot jump on button A, not
  this skill).

`kind` stays `vla` so the existing `ModelFamily` → `@POLICIES.register`
path can load it. The policy is proprio-only RL, not a vision-language
model.

## Supported robots / embodiments

`embodiment_tags: [go2, go2_z1]`. Joint order on the OpenRAL HAL is
menagerie **FL, FR, RL, RR**. On `go2_z1` the same 12-D action is
hold-padded to 19-D. Hop quality on the armed twin is unclaimed.

Trained default pose (this manifest's `starting_pose`) is **not** the
Hub walk stand: front thighs 0.8, rear 1.0, calves −1.5, hip signs
flipped vs `diasAiMaster/unitree-go2-velocity-flat`. Dashboard
Recalibrate still parks the Hub walk stand. Apply hop on the
simple dashboard is **not** this ONNX — it runs
[`rsl-rl-onnx-go2-spring-jump`](../rsl-rl-onnx-go2-spring-jump/) (gym
spring_jump). This checkpoint still only crouches on the torque-motor
HAL (`air_ticks=0`). The scripted zero hop stays in-tree as a fallback.

## Sensors / observation contract

Read from `params/deploy.yaml` `observations:` (do not invent keys), in
YAML order. Each term is history-10, `oldest_first`,
`repeat_first` warmup, packed **term-major** (not 10 stacked 47-D
frames):

| Term | Width × history | OpenRAL source |
|---|---|---|
| `gait_phase_2` | 2 × 10 | `sin/cos(2π · step · 0.02 / 1.5)` |
| `velocity_commands` | 3 × 10 | YAML default **or** per-call override |
| `base_ang_vel_B` | 3 × 10 | `WorldState.base_twist[3:6]` |
| `eulerZYX_rpy` | 3 × 10 | `base_pose.quat_xyzw` → roll/pitch/yaw |
| `joint_pos_rel` | 12 × 10 | `q[map] − default_joint_pos[map]` |
| `joint_vel_rel` | 12 × 10 | `dq[map]` |
| `last_action` | 12 × 10 | previous raw ONNX action |

Total **470-D**. First tick repeats the first frame ten times.

Default joystick is **in-place** `[0, 0, 0]`. Override with
`goal_params_json` `{"velocity_commands": [vx, vy, yaw]}` the same way
as the walk skill. The reasoner prompt is not mapped to that vector.

Gravity-on scene: `scenes/deploy/go2_walk.yaml` (or `go2_z1_walk.yaml`).
HAL walk PD stays on a hop-stand `ResetToPose`.

## Manifest summary

| Field | Value |
|---|---|
| `model_family` | **`rsl_rl_onnx`** |
| `kind` | `vla` |
| `runtime` | `onnx` |
| `license` | `unknown` |
| `weights_uri` | `local://rskills/rsl-rl-onnx-go2-hop-flat` |
| `action_contract` | `dim: 12`, `representation: joint_positions` |

```yaml
model_family: rsl_rl_onnx
runtime: onnx
license: unknown
weights_uri: local://rskills/rsl-rl-onnx-go2-hop-flat
policy_extras:
  velocity_commands: [0.0, 0.0, 0.0]
  onnx_filename: policy.onnx
  deploy_yaml: params/deploy.yaml
  onnx_url: https://raw.githubusercontent.com/Renkunzhao/legged_rl_deploy/master/policies/go2/mjlab/hop/policy.onnx
```

## License

Upstream ONNX: **unknown** (`RSkillLicensePosture.unknown`). The loader
emits `rskill.unknown_license` and does not treat `OPENRAL_ALLOW_NONCOMMERCIAL=1`
as a substitute for a real license. OpenRAL adapter code in this repo:
Apache-2.0.
