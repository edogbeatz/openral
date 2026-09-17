---
language:
- en
license: apache-2.0
pipeline_tag: robotics
tags:
- OpenRAL
- rskill
- zero
- vision-language-action
- go2_z1
inference: false
---

# rskill-zero-go2_z1-arm_ready-fp32

> **OpenRAL rSkill** — scripted **arm-ready** pose for the 19-DoF Unitree
> Go2 + Z1 sim twin. No neural weights. `model_family: zero` emits a 19-D
> `JOINT_POSITION` hold: Hub stand on the 12 legs, named pose on the Z1.

This package is the command module that **turns the Z1 servos on** and
parks them at a reachable pose. Locomotion stays the 12-DoF rsl-rl skill;
this skill is what actually moves the arm.

## Preview

Named poses (radians, `joint1` … `jointGripper`):

| Pose | `joint1..6` + jaw | When to use |
| --- | --- | --- |
| `ready` (default) | `0.0, 1.2, -1.0, -0.4, 0.0, 0.0, 0.0` | Shoulder up, gripper forward of the snout |
| `home` | menagerie `z1_gripper.xml` home | Park at spawn |
| `fold` | all zeros | Limp/folded servos |

## What this skill does

Open-loop **joint-position** hold. Each tick emits the same 19-D row:
Go2 Hub `default_joint_pos` for indices 0–11, the selected Z1 pose for
12–18. No cameras. No ONNX. `policy_extras.horizon_s: 2.0` so
`ExecuteRskill` succeeds after two seconds of holding (a learned VLA
never self-terminates).

`Go2Z1MujocoHAL` still **freezes** the arm on a 12-D locomotion chunk.
This skill is 19-D, which is the explicit arm-command path.

## Upstream model / training

There is no upstream checkpoint. The adapter is
`openral_sim.policies.mock._ZeroPolicy` (`model_family: zero`). Joint
numbers are the Hub Go2 stand plus menagerie Z1 limits. Pose constants
live in `openral_hal.go2_z1` (`GO2_Z1_ARM_READY` / `_HOME` / `_FOLD`)
and are drift-guarded against this package's `controller.json`.

| Field | Value |
| --- | --- |
| Source | in-tree `controller.json` + HAL pose constants |
| Paper | [mujoco_menagerie unitree_z1](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_z1) |
| License | Apache-2.0 |
| Parameters | none (scripted hold) |
| Training data | none |

## Supported robots / embodiments

| Robot | Embodiment tag | Status | Notes |
| --- | --- | --- | --- |
| Unitree Go2 + Z1 | `go2_z1` | experimental | Sim-only (`hal.real` is null). Bare `go2` has no arm joints. |

## Sensors / observation contract

Proprio-only. The policy ignores cameras and `observation.state`; it
replays `hold_targets`.

| Key | Modality | Notes |
| --- | --- | --- |
| (none) | — | Scripted hold; no sensor requirement |

## Manifest summary

| Field | Value |
| --- | --- |
| `name` | `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` |
| `version` | `0.1.0` |
| `license` | `apache-2.0` |
| `role` | `s1` |
| `embodiment_tags` | `go2_z1` |
| `runtime` / `quantization.dtype` | `pytorch` / `fp32` (adapter is numpy) |
| `weights_uri` | `local://rskills/rskill-zero-go2_z1-arm_ready-fp32` |
| `latency_budget.per_chunk_ms` | `20.0` |
| `commercial_use_allowed` | true (Apache-2.0, no third-party weights) |

## Quick start

```python
from openral_rskill.loader import rSkill

pkg = rSkill.from_yaml("rskills/rskill-zero-go2_z1-arm_ready-fp32/rskill.yaml")
print(pkg.manifest.name, pkg.manifest.model_family)
```

On a live `go2_z1_walk` graph:

```bash
openral deploy sim --config scenes/deploy/go2_z1_walk.yaml --dashboard --foxglove
ros2 action send_goal /openral/execute_rskill openral_msgs/action/ExecuteRskill \
  "{rskill_id: 'OpenRAL/rskill-zero-go2_z1-arm_ready-fp32', \
    goal_params_json: '{\"pose\": \"ready\"}', \
    deadline_s: 10.0}"
```

`goal_params_json` may also pass `"pose": "home" | "fold"` or an explicit
7-D `"arm": [j1, j2, j3, j4, j5, j6, jaw]` list (radians).

## Reproduction

```bash
just bootstrap && uv sync --all-packages
uv run pytest tests/sim/test_go2_z1_hal_mujoco.py tests/unit/test_zero_arm_pose.py \
  tests/unit/test_rskill_zero_go2_z1_arm_ready.py
```

No benchmarks shipped — this is a scripted hold, not a trained policy.

## Evaluation

No benchmarks shipped. See CLAUDE.md §6.4.

## License

This rSkill package (`rskill.yaml`, `README.md`, `controller.json`) is
**Apache-2.0**. There are no wrapped third-party weights.

## See also

- `robots/go2_z1/README.md` — composite RobotDescription.
- `scenes/deploy/go2_z1_walk.yaml` — gravity-on walk bench.
- `rskills/rsl-rl-onnx-go2-velocity-flat` — 12-DoF locomotion (arm held).
- [`docs/reference/vla_compatibility.md`](../../docs/reference/vla_compatibility.md) — VLA × Robot × Sim matrix.
