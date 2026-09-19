---
type: analysis
tags: [openral, rskill, navigation, go2]
updated: 2026-09-19
---

# There is no dedicated U-turn rSkill

Settled 2026-09-17 from a repo + Linear search, then a Hub / SDK /
GitHub pass. **Re-checked 2026-09-19** (Hub API + Isaac official
policies + GitHub). Still zero named U-turn / turn-around **weights**.
Home for Go2: [[entities/go2]].

`gr00t-n17-b1k-turning-on-radio` is a BEHAVIOR-1K radio task, not a
heading change.

## Closest existing skills

| Skill | What it actually does | U-turn? |
| --- | --- | --- |
| `OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32` | Isaac joystick `[vx, vy, yaw_rate]` on Go2 / Go2+Z1 | No closed-loop 180°. Demo Apply is `[0.35, 0, 0]` (forward only). A yaw-only command like `[0, 0, ω]` is a per-call override, not a named skill, and the checkpoint does not claim in-place turn quality. |
| `OpenRAL/rskill-nav2-mobile_base-navigate_to_pose` | Nav2 `NavigateToPose`. `base_link` relative goals document a 180° quaternion `z=1, w=0` | Yes as a **goal**, not a skill name. Requires `mobile_base` + `body_twist`. Go2 has neither. |
| `OpenRAL/rskill-internvla_n1-mobile_base-vln-nf4` | RGB instruction → 6-D `BODY_TWIST`. Paper claims Go2 zero-shot | Instruction-level ("turn around"), still `mobile_base` + `body_twist`. Go2 HAL does not expose that. |

## Go2 gap

[[entities/go2]] is `joint_position` only. `BODY_TWIST` / `cmd_vel` /
`mobile_base` are undeclared on purpose (`robots/go2/README.md`). Nav2
and InternVLA cannot resolve on this twin. The only in-tree way to
command a heading change on Go2 is the rsl-rl joystick override, which
is open-loop yaw rate for `max_execution_s` (60 s default), not "rotate
180° then stop."

## What we can adapt (no new weights)

The dog **already has a turn-capable policy**. Demo Apply hides it:
`[0.35, 0, 0]` forward only. The same ONNX takes
`{"velocity_commands": [0, 0, ω]}`. TypeSafe already maps
`turn_left` / `turn_right` to `[0, 0, ±0.6]`
(`WALK_VELOCITY_COMMANDS` in `openral_reasoner.typesafe_policy`).

Upstream `params/env.yaml` on `diasAiMaster/unitree-go2-velocity-flat`:
`heading_command: true`, heading ∈ [−π, π], `rel_heading_envs: 0.25`,
`ang_vel_z` ∈ [−0.5, 0.5] (curriculum ±1.0). So it *was* trained on
full-circle heading goals, at a narrower yaw-rate than
`m3/go2z1-walking-rsl-rl-v2` (±2.0). In-place 180° quality is still
unclaimed — V1 of that line oscillated past ~90° at ±0.5.

Adaptation order, cheapest first:

1. Command yaw on the walk skill we already load. No new checkpoint.
2. Closed-loop heading: same ONNX, outer loop on `/odom` yaw, stop when
   error is small. Still no new weights.
3. Only if (1)/(2) fail quality: export / wrap `m3` v2 (`walking_v2.pt`,
   Go2+Z1, Isaac Lab, no ONNX) or retrain with `ang_vel_z` ±2.

## Outside this repo

2026-09-19 Hub API (`go2+uturn`, `go2+turn+around`, `uturn+robot`,
`rskill+uturn`, `turn+around+quadruped`) returned **empty**. No public
model is named `uturn` / `u-turn` / `turn-around`. Hub `rskill` hits
are OpenRAL's own packages. Unitree `SportClient` (`sport_client.hpp`,
API IDs 1001–2058) has `Move(vx, vy, vyaw)`, `Euler`, dances and flips
— **not** `UTurn` or `TurnAround`.

| External artifact | What it is | U-turn? |
| --- | --- | --- |
| [m3/go2z1-walking-rsl-rl-v2](https://huggingface.co/m3/go2z1-walking-rsl-rl-v2) | Go2+Z1 PPO walk. File: `walking_v2.pt` only (no ONNX). `ω_z` ∈ [-2, 2] rad/s "covers 180° pivot" + heading tracking. V1 was ±0.5 and oscillated past ~90°; V1 *does* ship `exported/policy.onnx`. | Closest public **weights**. Rotation-capable walk, not a named U-turn skill. Code: `aws300/go2_z1_warehouse`. Apache-2.0. |
| [diasAiMaster/unitree-go2-velocity-flat](https://huggingface.co/diasAiMaster/unitree-go2-velocity-flat) | Bare-Go2 mjlab PPO; `policy.onnx` + `model_500.pt`. Isaac joystick `[vx, vy, yaw_rate]`. In-tree as `rsl-rl-onnx-go2-velocity-flat`. | Can command yaw. Does not claim in-place 180° quality. |
| Isaac Sim 6.0 official Go2 Flat Terrain Policy (PhysX / Newton) | Public `.pt` + `env.yaml` on NVIDIA S3 (`Isaac/Samples/Policies/go2/`). Keyboard turn left/right. | Joystick walk, not a U-turn. Isaac Lab / PhysX obs — not the current `rsl_rl_onnx` adapter. |
| [wty-yy/go2_rl_gym_data](https://huggingface.co/wty-yy/go2_rl_gym_data) | Many Go2 velocity / MoE-CTS `.pt` + `.onnx`. | Same joystick family. |
| [Artefacts/go2-locomotion](https://huggingface.co/Artefacts/go2-locomotion), [HEAVINT/Go2BlindFlat](https://huggingface.co/HEAVINT/Go2BlindFlat), [UWRobotics/Go2BlindFlat](https://huggingface.co/UWRobotics/Go2BlindFlat) | More flat / Walk-These-Ways / delayed-obs walks. | Joystick or WTW; no named turn skill. |
| OpenGo (arXiv:2604.01708) | Paper demo of an OpenClaw Go2 skill library. Fig. 1 lists **Turn Around** next to Move Forward / Backflip / Dance. Sequence example: "Move 5m, turn around, and sit." Paper "weights" are skill-selection preferences, not NN checkpoints. | Named in the paper. **No public code repo.** |
| [LooperRobotics/OpenClaw-Robotics](https://github.com/LooperRobotics/OpenClaw-Robotics) | OpenClaw skill. Commands: `turn left X` / `turn right X` (degrees). | Compose `turn left 180`. Not weights. |
| [dongsheng123132/go2-openclaw-skill](https://github.com/dongsheng123132/go2-openclaw-skill) | HTTP gateway over `unitree_sdk2py`. Directions: `turn_left` / `turn_right` with duration. | Timed yaw, not closed-loop 180°. |
| [StrikeRobot/Go2-Nav_System](https://huggingface.co/StrikeRobot/Go2-Nav_System) | Nav2 + Qwen / NaVILA. Discrete `turn left 30°` executed by the **built-in gait**. README: "No RL or learned locomotion is involved." | High-level command, not turn weights. |
| [LeCAR-Lab/ABS](https://github.com/LeCAR-Lab/ABS) | Go1 agile/recovery. Hardware map: `A` = Turn around. Train-yourself; no Hub checkpoint. | Go1, not Go2. Button is a high-level mapping on a goal policy. |
| [dontKnow23456/rambo-go2-policies](https://huggingface.co/dontKnow23456/rambo-go2-policies) | RAMBO loco-manipulation (quadruped + biped). CC-BY-NC. | Not a heading-180 skill. |
| HEX / `dvt217_turn_around_and_carry_boxes` | TienKung humanoid LeRobot dataset. | Humanoid demo data, not Go2 weights. |

Drive-stack "Make a U-turn" caption classes (DriveAGI etc.) are cars,
not quadrupeds.
