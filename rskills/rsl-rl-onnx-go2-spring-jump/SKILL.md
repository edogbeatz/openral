---
name: rsl-rl-onnx-go2-spring-jump
description: >-
  S1 Vision-Language-Action policy. Capabilities: navigate on terrain. Isaac Gym rsl-rl ONNX one-shot spring jump for the 12-DoF Go2. Loads policy.onnx (fetched at runtime; not vendored) plus in-tree params/deploy.yaml and emits absolute JOINT_POSITION targets. Observation is 470-D frame-major (constants + joystick A + joints, history 10). License of the ONNX is unknown (loader warns ``rskill.unknown_license``; ``is_commercial_use_allowed`` is false). Dashboard hop Apply. Discovery view of an OpenRAL rSkill — NOT directly runnable by an agent harness; it runs via rSkill.from_pretrained + the robot HAL.
metadata:
  openral_rskill: true            # generated discovery view of an rSkill
  schema_version: 0.1
  rskill_id: OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32
  manifest: ./rskill.yaml
  role: s1
  kind: vla
  model_family: rsl_rl_onnx
  embodiment_tags: [go2, go2_z1]
  actions: [navigate]
  objects: [terrain]
  scenes: [flat]
  action_dim: 12
  action_representation: joint_positions
  runtime: onnx
  quantization: fp32/onnx
  chunk_size: 1
  latency_budget: {per_chunk_ms: 20.0, max_execution_s: 8.0}
  license_code: Apache-2.0
  license_weights: unknown   # NOT permissive — see License section
  weights_uri: local://rskills/rsl-rl-onnx-go2-spring-jump
  paper_url: https://github.com/Renkunzhao/legged_rl_deploy
---

# rsl-rl-onnx-go2-spring-jump — rSkill discovery view

> **Generated view, not a hand-written skill.** This `SKILL.md` is a discovery-only
> mirror of [`rskill.yaml`](./rskill.yaml), produced by `tools/generate_rskill_skillmd.py`.
> It lets tools that read the standard agent-skill format find and reason about this
> OpenRAL rSkill. The `rskill.yaml` manifest is the single source of truth
> (CLAUDE.md §1.3). Do not edit by hand — edit the manifest and regenerate.

## What it is

An OpenRAL **Vision-Language-Action policy** (`role: s1`, `kind: vla`). Isaac Gym rsl-rl ONNX one-shot spring jump for the 12-DoF Go2. Loads policy.onnx (fetched at runtime; not vendored) plus in-tree params/deploy.yaml and emits absolute JOINT_POSITION targets. Observation is 470-D frame-major (constants + joystick A + joints, history 10). License of the ONNX is unknown (loader warns ``rskill.unknown_license``; ``is_commercial_use_allowed`` is false). Dashboard hop Apply.

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
- **Weights:** `unknown` — **NOT** fully permissive. The loader surfaces this posture and enforces the non-commercial guard (`OPENRAL_ALLOW_NONCOMMERCIAL=1`) where applicable. Commercial use may require a separate upstream agreement. This is third-party weight lineage; OpenRAL's own code is Apache-2.0.

## How to actually run it (not via an agent harness)

```python
from openral_rskill import rSkill

skill = rSkill.from_pretrained("OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32")
# the loader validates embodiment / sensors / runtime / quantization against the target
# RobotDescription and enforces the weight-license gate before any weights load.
```

See [`rskill.yaml`](./rskill.yaml) for the authoritative, validated manifest.
