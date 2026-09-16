---
type: source
tags: [openral, repo-layout, architecture]
updated: 2026-09-16
source: docs/architecture/repo-map.md
source_kind: in-repo
---

# Source — Repo map

Paths: `docs/architecture/repo-map.md` (textual) and
`docs/architecture/repo-state-map.html` (the canonical visual map).
Standing source, cited in place.

Rebuilt 2026-09-16 after the page was lost uncommitted.

## The split that matters

| Tree | Contains |
| --- | --- |
| `python/*` | uv-workspace pure-Python libs — `core`, `cli`, `detect`, `hal`, `sensors`, `world_state`, `rskill`, `state_adapter`, `sim`, `runner`, `reasoner`, `dataset`, `wam`, `observability` |
| `packages/*` | ROS 2 colcon packages — `msgs`, `world_state`, per-robot HAL lifecycle nodes, reasoner / prompt-router / rskill-runner / safety / perception / octomap / nav2 / slam / foxglove bringup |
| `cpp/` | `openral_safety_kernel` — implemented and tested, certification pending |
| `robots/`, `rskills/`, `scenes/`, `benchmarks/` | the manifests everything else validates against |
| `tests/{unit,integration,sim,hil}/` | all four tiers |

Naming convention: directories use short forms (`core/`, `msgs/`); Python
and PyPI names keep the `openral_` / `openral-` prefix.

`deployments/` is retired — deploy configs live in `scenes/deploy/`
(e.g. `scenes/deploy/go2_bench.yaml`, see [[entities/go2]]).

The bootstrap scripts live under `python/cli/src/openral_cli/bootstrap/`
rather than `scripts/`, deliberately: `openral install ros` must work
from the wheel with no clone.

## The state map is a PR gate

`repo-state-map.html` is hand-edited, data-driven JS arrays (`LAYERS`,
`CROSS`, `CANCELLED`, `SCHEMAS`), no build step. Adding, renaming, or
removing a package, flipping a status colour, or changing a layer
boundary without updating it makes the PR incomplete
(from [[sources/engineering-playbook]]). `green` requires source **and**
tests.

## Out of tree on purpose

Skill weights and datasets on the Hugging Face Hub
(`huggingface.co/openral/skill-*`, `dataset-*`), `openral/cloud`
(hosted control plane), `openral/contrib-closed-shims` (closed vendor SDK
adapters), and `openral/awesome-ros`. Their code does not belong in this
monorepo.

Related: [[entities/openral]], [[sources/engineering-playbook]].
