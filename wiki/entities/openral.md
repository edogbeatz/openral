---
type: entity
tags: [openral, architecture, harness, layers]
updated: 2026-09-16
---

# OpenRAL

The open **Robot Agentic Layer** — a harness for physical AI. It sits
between a robot's motor API and a task planner and makes one fixed,
typed, traceable runtime out of fast policies, slow reasoning,
perception, and classical control. Capabilities are swappable
**rSkills**; the harness itself does not change per robot
(from [[sources/engineering-playbook]], `README.md`).

Rebuilt 2026-09-16 from in-repo sources after the page was lost
uncommitted — see `wiki/log.md`.

## Where truth lives

Nothing normative lives in this wiki. The load-bearing files:

| Contract | File |
| --- | --- |
| Schemas | `python/core/` (`openral_core`), Pydantic v2 |
| Message IDL | `packages/msgs/` (`openral_msgs`) |
| Public symbols | `docs/METHODS.md` index → `docs/methods/*.md` |
| Agent + contributor rules | `CLAUDE.md` ([[sources/engineering-playbook]]) |
| Repo surface | `docs/architecture/repo-state-map.html` ([[sources/repo-map]]) |
| Layer-boundary decisions | private `OpenRAL/management` repo, `adr/` |

`grep -rn <symbol> docs/methods/` before writing any helper. A public
symbol added without its `docs/methods/` entry is an incomplete PR.

## Eight layers

`0 HAL → 1 Sensors → 2 World State → 3 rSkill (S1) → 4 Reasoning (S2) →
5 World Action Model → 6 Safety → 7 Observability`.

Non-adjacent dependencies are rejected. Moving a responsibility between
layers needs a recorded decision *before* the code.

Dual system: **S1** is the fast policy (30–200 Hz action chunks) as a
`Skill`; **S2** is the event-driven LLM `Reasoner` emitting typed
`ReasonerToolCall`s; **S0** is a 500–1000 Hz C++ cerebellar layer inside
`ros2_control` for humanoids. The skill manifest declares the role and
the loader enforces it.

## Two invariants worth restating

- **Python proposes, C++ disposes.** The safety kernel
  (`cpp/openral_safety_kernel/`) is a separate deny-by-default process.
  `ROSSafetyViolation` is caught only at the safety-supervisor boundary.
  No flag disables safety; no debug mode bypasses E-stop.
- **Real components, not mocks.** Tests exercise real manifests in
  `robots/`, real rSkill packages, real simulators. A missing dependency
  is a `pytest.skip`, never a fake.

## Layout in one line

`python/*` are pure-Python uv workspace libs, `packages/*` are ROS 2
colcon packages, `cpp/` is the safety kernel, and
`robots/` · `rskills/` · `scenes/` hold the manifests everything else
validates against (from [[sources/repo-map]]).

## Live surfaces

`openral deploy sim` can raise a dashboard and a Foxglove bridge, both
view-only — see [[concepts/deploy-sim-visualization]]. First robot with
a full sim visualization story is [[entities/go2]].

Related: [[concepts/second-brain]], [[entities/openral-foxglove-bringup]].
