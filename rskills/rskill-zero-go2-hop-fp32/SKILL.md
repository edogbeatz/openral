---
name: rskill-zero-go2-hop-fp32
description: >-
  S1 Vision-Language-Action policy. Capabilities: navigate on terrain. Scripted 12-D joint-position hop for Unitree Go2: crouch, extend, tuck, land. In-tree fallback. Dashboard hop Apply is gym spring_jump (rsl-rl-onnx-go2-spring-jump). Feet leave the go2_walk floor (measured air_ticks≈45, foot-bottom ≈0.25 m, z_max≈0.47 m) under HAL walk PD. Not the mjlab hop ONNX — that checkpoint only crouches on this torque-motor twin. Go2+Z1 hold-pads 12→19. Discovery view of an OpenRAL rSkill — NOT directly runnable by an agent harness; it runs via rSkill.from_pretrained + the robot HAL.
metadata:
  openral_rskill: true            # generated discovery view of an rSkill
  schema_version: 0.1
  rskill_id: OpenRAL/rskill-zero-go2-hop-fp32
  manifest: ./rskill.yaml
  role: s1
  kind: vla
  model_family: zero
  embodiment_tags: [go2, go2_z1]
  actions: [navigate]
  objects: [terrain]
  scenes: [flat]
  action_dim: 12
  action_representation: joint_positions
  runtime: pytorch
  quantization: fp32/pytorch
  chunk_size: 1
  latency_budget: {per_chunk_ms: 20.0, max_execution_s: 10.0}
  license_code: Apache-2.0
  license_weights: apache-2.0
  weights_uri: local://rskills/rskill-zero-go2-hop-fp32
  paper_url: https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_go2
---

# rskill-zero-go2-hop-fp32 — rSkill discovery view

> **Generated view, not a hand-written skill.** This `SKILL.md` is a discovery-only
> mirror of [`rskill.yaml`](./rskill.yaml), produced by `tools/generate_rskill_skillmd.py`.
> It lets tools that read the standard agent-skill format find and reason about this
> OpenRAL rSkill. The `rskill.yaml` manifest is the single source of truth
> (CLAUDE.md §1.3). Do not edit by hand — edit the manifest and regenerate.

## What it is

An OpenRAL **Vision-Language-Action policy** (`role: s1`, `kind: vla`). Scripted 12-D joint-position hop for Unitree Go2: crouch, extend, tuck, land. In-tree fallback. Dashboard hop Apply is gym spring_jump (rsl-rl-onnx-go2-spring-jump). Feet leave the go2_walk floor (measured air_ticks≈45, foot-bottom ≈0.25 m, z_max≈0.47 m) under HAL walk PD. Not the mjlab hop ONNX — that checkpoint only crouches on this torque-motor twin. Go2+Z1 hold-pads 12→19.

## Capabilities

- **Verbs:** navigate
- **Objects:** terrain
- **Scenes:** flat
- **Embodiments:** go2 · go2_z1

## Why this is discovery-only

An agent skill is natural-language instructions loaded into an LLM's context. An rSkill
is an executable artifact: it carries a typed capability/embodiment contract, model weights,
a runtime, and a license/provenance gate — none of which fit in freeform markdown. So an
agent can use this view to *select* the right skill, but cannot *execute* it by loading
this file. Execution always goes through the OpenRAL loader and the robot HAL.

## License

- **Code:** Apache-2.0.
- **Weights:** `apache-2.0` — permissive / commercial-use OK

## How to actually run it (not via an agent harness)

```python
from openral_rskill import rSkill

skill = rSkill.from_pretrained("OpenRAL/rskill-zero-go2-hop-fp32")
# the loader validates embodiment / sensors / runtime / quantization against the target
# RobotDescription and enforces the weight-license gate before any weights load.
```

See [`rskill.yaml`](./rskill.yaml) for the authoritative, validated manifest.
