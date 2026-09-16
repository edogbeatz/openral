---
type: index
tags: [openral, index]
updated: 2026-09-16
---

# OpenRAL Second Brain — Index

A maintained knowledge base for **OpenRAL**, the open Robot Agentic Layer.
Pages are cross-linked with `[[wikilinks]]`. Normative engineering stays in
`docs/`, `docs/METHODS.md`, Pydantic schemas, and IDL. This wiki is
compounding agent memory for tasks, synthesis, and contradictions.

Start here: [[entities/openral]].

**Tasks must cite this wiki.** See [[concepts/task-wiki-contract]].

> The four pages lost in the 2026-09-16 partial restore were rebuilt the
> same day from their in-repo sources (`CLAUDE.md`,
> `docs/architecture/repo-map.md`, `README.md`, the wiki skill). They are
> re-derivations, not the original text. See `wiki/log.md`.

## Sources

- [[sources/engineering-playbook]] — `CLAUDE.md` (agent + contributor contract); what it governs and where it points.
- [[sources/repo-map]] — `python/*` vs `packages/*` vs `cpp/`, the state-map PR gate, out-of-tree repos.

## Entities

- [[entities/openral]] — the project overall (harness, eight layers, where truth lives).
- [[entities/go2]] — Unitree Go2 sim-only spike: 12-DoF quadruped, torque-motor PD hold, `front` + viz-only `top` cameras.
- [[entities/openral-foxglove-bringup]] — read-only Foxglove live-scene package; `package://` meshes via ament overlay; layout generator.

## Concepts

- [[concepts/second-brain]] — what the wiki is and is not.
- [[concepts/task-wiki-contract]] — Linear / PR / agent tasks cite wiki pages; how the wiki references Linear back.
- [[concepts/wiki-maintenance-workflow]] — ingest, query, lint, page rules, log format.
- [[concepts/deploy-sim-visualization]] — hybrid `--dashboard` + `--foxglove`; laptop viewer vs remote graph; display frame, floor, up-axis; host-clock freshness.

## Analyses

- [[analyses/foxglove-web-meshes-need-package-uri]] — Studio (web and desktop) only requests `package://` from the bridge; the overlay works, and Studio still caches the earlier failure.
- [[analyses/proving-sim-motion-not-a-frozen-stand]] — `/joint_states` span is ground truth; `action_applied`, `ros2 node list`, and a silent `docker exec` all lie.
