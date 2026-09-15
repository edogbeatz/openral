---
language:
- en
license: bsd-3-clause
pipeline_tag: robotics
tags:
- OpenRAL
- rskill
- rsl_rl_onnx
- vision-language-action
- go2
inference: false
---

# rskill-rsl_rl_onnx-go2-velocity_flat-fp32

> **OpenRAL rSkill** — Isaac Lab / Unitree **rsl-rl ONNX** locomotion on the
> 12-DoF Unitree Go2. Wraps
> [`diasAiMaster/unitree-go2-velocity-flat`](https://huggingface.co/diasAiMaster/unitree-go2-velocity-flat).
> Ships no weights. **Not SmolVLA** — SmolVLA cannot load `policy.onnx`.

This package adds capability checking, license surfacing, and
`execute_rskill` / `make_policy` dispatch via the `rsl_rl_onnx` family
token. It does **not** copy model weights and it does **not** claim gait
quality — only that the adapter can load the ONNX graph and emit 12-D
`JOINT_POSITION` targets.

## Preview

Upstream flat-terrain PPO demo (author video, not an OpenRAL rollout):

![Unitree Go2 rsl-rl velocity-flat demo](https://img.youtube.com/vi/smxh8Uu2Zpo/maxresdefault.jpg)

## What this skill does

Closed-loop **joint-position** locomotion: read 12-D proprio + base
orientation/angular velocity, append a 3-D velocity command, run
`policy.onnx`, write `default_joint_pos + action * scale` as a 12-D
`JOINT_POSITION` action. No cartesian representation. No cameras.

## Upstream model / training

- **Checkpoint:** `hf://diasAiMaster/unitree-go2-velocity-flat`
- **Files:** `policy.onnx` (+ `policy.onnx.data` external weights),
  `params/deploy.yaml` (observation order, scales, `JointPositionAction`,
  `joint_ids_map`, `default_joint_pos`).
- **Trainer:** [unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab)
  task `Mjlab-Velocity-Flat-Unitree-Go2`, PPO / rsl-rl, flat plane.
- **License:** BSD-3-Clause (upstream model card).
- Trained **without** `gait_phase`; action scale **0.5**. Use this repo's
  `params/deploy.yaml`, not a generic unitree_rl_mjlab default.

`kind` stays `vla` so the existing `ModelFamily` → `@POLICIES.register`
path can load it. The policy is proprio-only RL, not a vision-language
model.

## Supported robots / embodiments

`embodiment_tags: [go2]`. Joint order on the OpenRAL HAL is menagerie
**FL, FR, RL, RR** × hip / thigh / calf (`robots/go2`, `Go2MujocoHAL`).
`params/deploy.yaml` `joint_ids_map: [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]`
is applied inside the adapter (policy slot → robot index). Do not invent
a second remap.

`default_joint_pos` in the Hub YAML is menagerie-like with hip offsets
`±0.1` (thigh `0.9`, calf `−1.8`). The HAL home keyframe uses hip `0.0`.

## Sensors / observation contract

Read from `params/deploy.yaml` `observations:` (do not invent keys), in
YAML order, concatenated:

| Term | Width | OpenRAL source |
|---|---|---|
| `base_ang_vel` | 3 | `WorldState.base_twist[3:6]` (or `obs["base_ang_vel"]`) |
| `projected_gravity` | 3 | `WorldState.base_pose.quat_xyzw` → \(R^\top [0,0,-1]\) |
| `velocity_commands` | 3 | **`policy_extras.velocity_commands`** — not the reasoner prompt |
| `joint_pos_rel` | 12 | `joint_state.position[map] − default_joint_pos[map]` |
| `joint_vel_rel` | 12 | `joint_state.velocity[map]` (zeros if the HAL omits velocity) |
| `last_action` | 12 | previous raw ONNX action |

Total **45-D**. History length is 1 on this checkpoint.

### Velocity command gap (honest)

Isaac `velocity_commands` is a joystick `[vx, vy, yaw_rate]`. The reasoner
sends a natural-language prompt. This hackathon adapter does **not** parse
the prompt. `execute_rskill` / `make_policy` read:

```yaml
policy_extras:
  velocity_commands: [0.5, 0.0, 0.0]   # default forward walk
  onnx_filename: policy.onnx
  deploy_yaml: params/deploy.yaml
```

Override `velocity_commands` in the manifest or `VLASpec.extra` for a
different cmd. A real nav stack (BODY_TWIST → joystick) is out of scope.

### HAL gaps vs `go2_bench`

`scenes/deploy/go2_bench.yaml` boots the MuJoCo digital twin with
**gravity off** and no locomotion controller — it is a 12-DoF HAL pipe
proof, not a walking scene. `Go2MujocoHAL` does not publish IMU /
`base_pose_6dof` the way the G1 walking controller does. When
`WorldState.base_pose` / `base_twist` are missing the adapter uses
identity projected gravity `[0, 0, −1]` and zero angular velocity. PD
gains in `deploy.yaml` (`stiffness` / `damping`) are **not** applied here;
the HAL keeps its own software PD. Success criterion is `make_policy`
load + 12-D emit, not gait quality.

## Manifest summary

| Field | Value |
|---|---|
| `model_family` | **`rsl_rl_onnx`** (Acquire token) |
| `kind` | `vla` (do not invent a new `RSkillKind`) |
| `runtime` | `onnx` |
| `weights_uri` | `hf://diasAiMaster/unitree-go2-velocity-flat` |
| `action_contract` | `dim: 12`, `representation: joint_positions`, `joint_units: radians` |
| Hub layout | `policy.onnx` (+ `.data`) and `params/deploy.yaml` beside it |

```yaml
model_family: rsl_rl_onnx
runtime: onnx
weights_uri: hf://diasAiMaster/unitree-go2-velocity-flat
policy_extras:
  velocity_commands: [0.5, 0.0, 0.0]
  onnx_filename: policy.onnx
  deploy_yaml: params/deploy.yaml
```

Local `make_policy` tests point `VLASpec.weights_uri` at a directory that
already contains those two files so CI never hits the Hub.

## License

Upstream checkpoint: **BSD-3-Clause** (`RSkillLicensePosture.bsd`).
OpenRAL adapter code in this repo: Apache-2.0.
