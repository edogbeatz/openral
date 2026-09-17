---
name: rskill-zero-go2-z1-arm-ready
description: >-
  S1 scripted pose skill. Capabilities: reach. Parks the Unitree Z1 on a
  Go2+Z1 sim twin at a named joint pose (default ready). Discovery view of
  an OpenRAL rSkill — NOT directly runnable by an agent harness; it runs
  via rSkill.from_pretrained + the robot HAL.
metadata:
  openral_rskill: true
  schema_version: 0.1
  rskill_id: OpenRAL/rskill-zero-go2_z1-arm_ready-fp32
  manifest: ./rskill.yaml
  role: s1
  kind: vla
  model_family: zero
  embodiment_tags: [go2_z1]
  actions: [reach]
  chunk_size: 1
  latency_budget: {per_chunk_ms: 20.0}
  license_code: Apache-2.0
  license_weights: apache-2.0
  paper_url: https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_z1
---

# rskill-zero-go2_z1-arm_ready-fp32 — rSkill discovery view

> **Generated view, not a hand-written skill.** This `SKILL.md` is a discovery-only
> mirror of [`rskill.yaml`](./rskill.yaml). The `rskill.yaml` manifest is the
> single source of truth (CLAUDE.md §1.3).

## What it is

An OpenRAL **scripted joint-position hold** (`role: s1`, `kind: vla`,
`model_family: zero`). Turns the Z1 position servos on and drives them to
`ready` / `home` / `fold`. Not a learned manipulator.

## Capabilities

- **Verbs:** reach
- **Embodiments:** go2_z1

## Why this is discovery-only

An agent skill is natural-language instructions loaded into an LLM's context. An rSkill
is an executable artifact. Execution always goes through the OpenRAL loader and the robot HAL.

## License

- **Code:** Apache-2.0. No third-party weights.

## How to actually run it (not via an agent harness)

```python
from openral_rskill import rSkill

skill = rSkill.from_yaml("rskills/rskill-zero-go2_z1-arm_ready-fp32/rskill.yaml")
```

See [`rskill.yaml`](./rskill.yaml) for the authoritative, validated manifest.
