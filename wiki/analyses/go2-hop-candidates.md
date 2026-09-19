---
type: analysis
tags: [openral, rskill, go2, hop, locomotion]
updated: 2026-09-19
---

# Go2 hop: closest public artifacts

Settled 2026-09-19 (gym spring_jump as dashboard hop). The walk
checkpoint (`diasAiMaster/unitree-go2-velocity-flat`) is still
**without** `gait_phase` and cannot hop.

## Dashboard hop Apply (winner)

`OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32` —
`rskills/rsl-rl-onnx-go2-spring-jump`. Same `model_family: rsl_rl_onnx`
as walk. Weights:
[Renkunzhao/legged_rl_deploy](https://github.com/Renkunzhao/legged_rl_deploy)
`policies/go2/My_unitree_go2_gym/spring_jump/policy.onnx` (fetched via
`policy_extras.onnx_url`, not vendored; upstream has no GitHub license;
manifest `license: unknown`).

Obs is **470-D frame-major** (Isaac Gym `frame_stack`, zero warmup):
`constants` `[0,0,0.7,0]` + joystick A + scaled ang vel / euler / joints
/ last action, history 10. YAML `jump_trigger` default **1.0**. Action
scale 0.25, clip ±100. Default pose hips **0.0** (not mjlab ±0.1).

Headless on `Go2MujocoHAL` + `compose_ground_plane_mjcf` + walk PD
(2026-09-19): **`air_ticks≈15–16`**, max foot ≈**0.34 m**,
`z_max≈0.53 m`, takeoff ~0.26 s, lands and recovers (~5° tilt /
z≈0.30). Scripted bounce same run: `air_ticks≈51`, foot ≈0.25 m,
`z_max≈0.47 m`. Spring_jump hops **higher**; fewer air ticks because
it is a one-shot jump, not a repeating squat cycle.

Gym hop in the same repo (`My_unitree_go2_gym/hop/`, scaled obs,
frame-major) still crouches (`air_ticks=0`). First bake-off used
term-major on those gym nets (wrong layout → NaN / exploding calves).
After matching training layout, gym hop still planted.

Cricket Load copies `rskills/rsl-rl-onnx-go2-spring-jump` + this-branch
`rsl_rl_onnx.py` (`sync_cricket_scripted_hop`) then reloads. Old cricket
adapter cannot load `constants` / `joystick_buttons` / `frame_major`.
`isHopSkillId` matches `jump` as well as `hop` so Apply does not treat
the id as a walk skill.

## Still in-tree, not the picker

- mjlab hop `rskills/rsl-rl-onnx-go2-hop-flat` — term-major 470-D,
  `gait_phase_2`. Planted crouch on this HAL (`air_ticks=0`) even with
  feet on z=0. Isaac hop `kp=20` sags calves. Do not put it back as
  the picker.
- scripted `rskills/rskill-zero-go2-hop-fp32` (`gait: jump`) —
  crouch-extend-tuck-land under walk PD. Leaves the floor (measured)
  but the user still said it does not hop high. Fallback only.

## Go2+Z1 later

The spring_jump manifest tags `go2_z1`. No new `ModelFamily` and no
19-D hop policy: the runner hold-pads the same 12-D rows to 19, and
`Go2Z1MujocoHAL` keeps the sticky arm freeze.

> ⚠️ Acquire catalog will **not** warrant hop on Go2+Z1
> (`check=payload`, 4.69 kg Z1 vs unladen budget). Dashboard picker
> can still hold-pad. Different surfaces
> ([[analyses/creating-acquire]]). Scene is
`go2_z1_walk`. Dashboard Recalibrate / `preferWalk` overrides `arm_ready`
back to walk and leaves hop selected. Hop is a picker choice on both
twins, not the post-Recalibrate default.

Live dispatch of the **mjlab** hop (2026-09-19 cricket, earlier this
branch) was a planted crouch (`air_ticks=0`). Apply hop `ResetToPose`
must sit the skill's own `starting_pose` on z=0 and keep walk PD.

## Upstream artifacts (Renkunzhao)

[Renkunzhao/legged_rl_deploy](https://github.com/Renkunzhao/legged_rl_deploy)
`policies/go2/`:

| Path | Layout | This HAL |
| --- | --- | --- |
| `mjlab/hop/` | term-major 470-D, gait_phase 1.5 s | crouch (`air_ticks=0`) |
| `My_unitree_go2_gym/hop/` | frame-major 470-D, scaled obs | crouch (`air_ticks=0`) |
| `My_unitree_go2_gym/spring_jump/` | frame-major 470-D, joystick A | **jumps** (dashboard hop) |

`policy.onnx` is **not** vendored. `policy_extras.onnx_url` fetches into
`~/.cache/openral/rsl_rl_onnx/`.

## Why the walk adapter was not enough

Walk is **45-D, history=1, no gait_phase, action scale 0.5**. Hop/jump
nets are **47-D × 10 = 470-D**. Gym policies need **frame-major + zero
warmup**; mjlab hop is **term-major + repeat_first**. Same family, three
customers, not a new `ModelFamily`.

## Other public options (worse fit)

Live re-search 2026-09-19 (GitHub / Hugging Face / Unitree). Prior notes
held:

| Artifact | Fit |
| --- | --- |
| Unitree `SportClient.FrontJump` / `FreeBound` / `FreeJump` | Real firmware only. [[entities/go2]] is sim-only, `hal.real` is null. |
| [Teddy-Liao/walk-these-ways-go2](https://github.com/Teddy-Liao/walk-these-ways-go2) | Gait-conditioned MoB; hop/pronk via gait command, not ONNX, adaptation module. |
| [eppl-erau-db/go2_rl_ws](https://github.com/eppl-erau-db/go2_rl_ws) | Pronking.gif is old walk; shipped ONNX is walk/nav, not hop. |
| [saifahmadgit/go2-sim2real-locomotion-rl](https://github.com/saifahmadgit/go2-sim2real-locomotion-rl) | Genesis jump eval (`go2-jump` ckpt 999). README says walk/stairs transferred; jump did not. |
| Hugging Face `go2 hop` / `go2 jump` | Still empty. |
| LSJ-0829/mpr-go2 | 401. |
| cagataydev SAC | walk torques, not hop. |

A taller learned hop than spring_jump still needs a new public ONNX
that leaves this HAL, or train in Isaac Lab / mjlab against walk PD.
Do not retune the scripted squat as the picker answer.
