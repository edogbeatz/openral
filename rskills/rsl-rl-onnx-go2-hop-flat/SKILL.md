---
name: rsl-rl-onnx-go2-hop-flat
description: >-
  S1 Vision-Language-Action policy. Capabilities: navigate on terrain. mjlab rsl-rl ONNX hop for the 12-DoF Go2. Loads policy.onnx (fetched at runtime; not vendored) plus in-tree params/deploy.yaml and emits absolute JOINT_POSITION targets. Observation is 470-D (gait phase + command + ang vel + euler RPY + joints + last action, history 10). License of the ONNX is unknown (loader warns rskill.unknown_license). Does not claim hop quality. Discovery view of an OpenRAL rSkill — NOT directly runnable by an agent harness; it runs via rSkill.from_pretrained + the robot HAL.
metadata:
  openral_rskill: true            # generated discovery view of an rSkill
  schema_version: 0.1
  rskill_id: OpenRAL/rskill-rsl_rl_onnx-go2-hop_flat-fp32
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
  latency_budget: {per_chunk_ms: 20.0, max_execution_s: 20.0}
  license_code: Apache-2.0
  license_weights: unknown
  weights_uri: local://rskills/rsl-rl-onnx-go2-hop-flat
  paper_url: https://github.com/Renkunzhao/legged_rl_deploy
---

# rsl-rl-onnx-go2-hop-flat — rSkill discovery view

> **Generated view, not a hand-written skill.** This `SKILL.md` is a discovery-only
> mirror of [`rskill.yaml`](./rskill.yaml). The `rskill.yaml` manifest is the
> single source of truth (CLAUDE.md §1.3). Do not edit by hand — edit the
> manifest and regenerate.

## What it is

An OpenRAL **Vision-Language-Action policy** (`role: s1`, `kind: vla`). mjlab rsl-rl ONNX hop for the 12-DoF Go2. Loads policy.onnx (fetched at runtime; not vendored) plus in-tree params/deploy.yaml and emits absolute JOINT_POSITION targets. Observation is 470-D. License of the ONNX is unknown (loader warns `rskill.unknown_license`). Does not claim hop quality.

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
- **Weights:** `unknown` — loader warns `rskill.unknown_license`; `is_commercial_use_allowed` is false

## How to actually run it (not via an agent harness)

```python
from openral_rskill import rSkill

skill = rSkill.from_yaml("rskills/rsl-rl-onnx-go2-hop-flat/rskill.yaml")
```

See [`rskill.yaml`](./rskill.yaml) for the authoritative, validated manifest.
