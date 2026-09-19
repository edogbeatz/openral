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

The last `coast_to_stand_s` seconds of `horizon_s` command `[0, 0, 0]`
so the ONNX stands the dog before the goal ends. Without that, the
runner idle-holds the last mid-gait waypoint under gravity and the
twin falls. `horizon_s: 57` succeeds standing; `max_execution_s: 60`
is the abort backstop.

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

`embodiment_tags: [go2, go2_z1]`. Joint order on the OpenRAL HAL is menagerie
**FL, FR, RL, RR** × hip / thigh / calf (`robots/go2`, `Go2MujocoHAL`).
On `go2_z1` the same 12-D action is hold-padded to 19-D (arm frozen at the sticky Recalibrate / `arm_ready` pose).
`params/deploy.yaml` `joint_ids_map: [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]`
is applied inside the adapter (policy slot → robot index). Do not invent
a second remap.

`default_joint_pos` in the Hub YAML is menagerie-like with hip offsets
`±0.1` (thigh `0.9`, calf `−1.8`). `Go2MujocoHAL` spawn / `GO2_HOME_JOINT_TARGETS`
/ this manifest's `starting_pose` use that same vector. Menagerie keyframe 0
still supplies free-joint height; actuated hips are snapped to Hub ±0.1 after
`connect()`. The in-tree ACM is empty — when collision lower lands, rest pose
should be this Hub stand, not menagerie hip `0.0`.

## Sensors / observation contract

Read from `params/deploy.yaml` `observations:` (do not invent keys), in
YAML order, concatenated:

| Term | Width | OpenRAL source |
|---|---|---|
| `base_ang_vel` | 3 | `WorldState.base_twist[3:6]` (or `obs["base_ang_vel"]`) |
| `projected_gravity` | 3 | `WorldState.base_pose.quat_xyzw` → \(R^\top [0,0,-1]\) |
| `velocity_commands` | 3 | YAML default **or** per-call override (see below) — not the reasoner prompt |
| `joint_pos_rel` | 12 | `joint_state.position[map] − default_joint_pos[map]` |
| `joint_vel_rel` | 12 | `joint_state.velocity[map]` (zeros if the HAL omits velocity) |
| `last_action` | 12 | previous raw ONNX action |

Total **45-D**. History length is 1 on this checkpoint.

### Velocity command (per-call override)

Isaac `velocity_commands` is a joystick `[vx, vy, yaw_rate]`. The reasoner
prompt is natural language and is **not** parsed into that vector. YAML is
the default only:

```yaml
policy_extras:
  velocity_commands: [0.5, 0.0, 0.0]   # default forward walk
  onnx_filename: policy.onnx
  deploy_yaml: params/deploy.yaml
  horizon_s: 57.0                      # succeed after coast, not deadline abort
  coast_to_stand_s: 3.0                # last 3 s command [0, 0, 0]
```

Override **without editing this YAML** (highest wins):

1. `observation["velocity_commands"]` on this `step()` (verify / runner attach).
2. `ExecuteRskill.goal_params_json` — the reasoner tool palette surfaces
   `goal_params_schema.velocity_commands`:

   ```json
   {"velocity_commands": [1.0, 0.0, 0.3]}
   ```

   Empty `goal_params_json` restores the YAML default on a resident skill.
3. `VLASpec.extra["velocity_commands"]` at `make_policy` / `openral sim run`.

A real nav stack (BODY_TWIST → joystick) is still out of scope.

### HAL IMU / pose and PD

`Go2MujocoHAL` publishes `base_pose_6dof()` (free-joint xyz + quat_xyzw) and
`base_twist` (`qvel[0:6]`; angular part is base-frame, Isaac `base_ang_vel`).
The HAL lifecycle republishes that as `/odom` (no extra TF parent). WorldState
subscribes and fills `WorldState.base_pose` / `base_twist`. The runner copies
those onto the observation. When pose/twist are still missing the adapter
logs a **one-shot** `rsl_rl_onnx.obs_fallback` warning and uses identity
projected gravity `[0, 0, −1]` and zero angular velocity.

`scenes/deploy/go2_bench.yaml` still boots with **gravity off** — it is a
12-DoF HAL pipe proof, not a walking scene. Success criterion is load +
correct 45-D obs sources + 12-D emit, **not** gait quality. For a
gravity-on locomotion bench use `scenes/deploy/go2_walk.yaml` (or
`go2_z1_walk.yaml` for the composite). ACM on those walk scenes is
stand-justified, not gait-swept.

Hub `deploy.yaml` PD (`stiffness` `[20, 20, 40]`, `damping` `[1, 1, 2]` per
hip/thigh/calf) is **not** applied. HAL software PD stays
`kp = ctrlrange` (23.7 / 23.7 / 45.43) and `kv = 0.05 * kp` so 1 rad of
error saturates torque and estop / home-acm holds do not change. That
delta is intentional and documented.

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
  horizon_s: 57.0
  coast_to_stand_s: 3.0
goal_params_schema:
  type: object
  properties:
    velocity_commands: {type: array, minItems: 3, maxItems: 3}
starting_pose: [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8]
```

Local `make_policy` tests point `VLASpec.weights_uri` at a directory that
already contains those two files so CI never hits the Hub.

## License

Upstream checkpoint: **BSD-3-Clause** (`RSkillLicensePosture.bsd`).
OpenRAL adapter code in this repo: Apache-2.0.
