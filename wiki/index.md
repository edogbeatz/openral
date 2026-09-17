---
type: index
tags: [openral, index]
updated: 2026-09-17
---

# OpenRAL Second Brain — Index

A maintained knowledge base for **OpenRAL**, the open Robot Agentic Layer.
Pages are cross-linked with `[[wikilinks]]`. Normative engineering stays in
`docs/`, `docs/METHODS.md`, Pydantic schemas, and IDL. This wiki is
compounding agent memory for tasks, synthesis, and contradictions.

Start here: [[entities/openral]].

**Tasks must cite this wiki.** See [[concepts/task-wiki-contract]].
**Finished work is filed here** — update pages, append `wiki/log.md`.
See [[concepts/wiki-maintenance-workflow]].

> The four pages lost in the 2026-09-16 partial restore were rebuilt the
> same day from their in-repo sources (`CLAUDE.md`,
> `docs/architecture/repo-map.md`, `README.md`, the wiki skill). They are
> re-derivations, not the original text. See `wiki/log.md`.

## Sources

- [[sources/engineering-playbook]] — `CLAUDE.md` (agent + contributor contract); what it governs and where it points.
- [[sources/repo-map]] — `python/*` vs `packages/*` vs `cpp/`, the state-map PR gate, out-of-tree repos.

## Entities

- [[entities/openral]] — the project overall (harness, eight layers, where truth lives).
- [[entities/go2]] — Unitree Go2 sim-only quadruped: 12-DoF, torque-motor PD hold, `go2_bench` vs `go2_walk`, `front` + viz-only `top`.
- [[entities/go2-z1]] — Go2 + Z1 19-DoF composite; Recalibrate parks Z1 at arm-ready; rsl-rl walk hold-pads 12→19 and qpos-snaps **arm only**; demo Apply defaults to walk (does not restore saved arm_ready).
- [[entities/openral-foxglove-bringup]] — read-only Foxglove live-scene package; `package://` meshes via ament overlay; layout generator.

## Concepts

- [[concepts/second-brain]] — what the wiki is and is not.
- [[concepts/task-wiki-contract]] — Linear / PR / agent tasks cite wiki pages; how the wiki references Linear back.
- [[concepts/wiki-maintenance-workflow]] — ingest, query, lint, **Done / finish** close-out, log format; cricket/dashboard/Foxglove start failures also append `.agents/skills/go2-foxglove-view/SKILL.md` the same turn.
- [[concepts/deploy-sim-visualization]] — hybrid `--dashboard` + `--foxglove`; laptop viewer vs remote graph; display frame, floor, up-axis; host-clock freshness; Event log collapsed live-debug; command-band counters are session totals (Recalibrate does not zero them); write-controls **demo** bar (Bare Go2 auto-calibrates then Apply; Go2+Z1 asks Recalibrate first then defaults Apply to walk, not saved arm_ready; **Stop** cancels the skill without e-stop; laptop **Start Cricket** `brev start`s + tunnels Foxglove `:8765` and cricket dashboard `:14318`; **End Cricket** + 15 min idle auto-stop still `brev stop`); laptop `openral dashboard` is an empty collector (WAITING) — live twin is cricket `deploy sim`; Bare Go2 / Go2+Z1 cold-reload must not `pkill -f` its own argv; dashboard always mounts Go2 `front` (main) + `top` (side) even while WAITING; opaque `waiting for camera` placeholder must not cover live MJPEG (tiles start `is-streaming`); laptop `:4318` is often the cricket tunnel (else proxies `:14318`); camera tiles 25 Hz MJPEG (not 1 Hz stills); Foxglove Image panels on `/compressed`; start failures catalog in `.agents/skills/go2-foxglove-view/SKILL.md`.

## Analyses

- [[analyses/foxglove-web-meshes-need-package-uri]] — Studio (web and desktop) only requests `package://` from the bridge; the overlay works, and Studio still caches the earlier failure.
- [[analyses/proving-sim-motion-not-a-frozen-stand]] — `/joint_states` span is ground truth; `action_applied`, `ros2 node list`, and a silent `docker exec` all lie.
