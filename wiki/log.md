---
type: log
tags: [openral, log]
updated: 2026-09-16
---

Each entry starts with `## [YYYY-MM-DD] <op> | <title>`. Ops: `ingest`, `query`, `lint`, `manual`, `bootstrap`.

## [2026-09-16] ingest | Go2 Foxglove session state + rebuild of the four lost pages

- summary: wiki/entities/go2.md, wiki/analyses/proving-sim-motion-not-a-frozen-stand.md
- touched: wiki/index.md, wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- new: wiki/entities/openral.md, wiki/entities/go2.md, wiki/concepts/wiki-maintenance-workflow.md, wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md, wiki/analyses/proving-sim-motion-not-a-frozen-stand.md
- linear: none
- notes: swept the uncommitted working tree (Go2 HAL, camera rig,
  foxglove bringup, dashboard.js) plus `.agents/skills/go2-foxglove-view/`
  into the wiki. New durable findings the earlier pages predated: the
  ament mesh overlay is **confirmed** on cricket and the remaining blocker
  is Studio caching the earlier fetch failure; COLLADA `<up_axis>` (RViz
  ignores it, Foxglove honours it, so the layout forces `z_up`); Image
  panels need the paired CameraInfo on the *manifest* `frame_id`; the
  dashboard freshness pill ages against the host clock, not the browser's;
  Go2 torque motors need `idle_step` to PD-hold or the calves fold.
  Filed the actuation-verification traps as their own analysis —
  `/joint_states` span is the only ground truth, `action_applied` stayed
  silent through a real trot, and `docker exec` without `-i` drops a
  heredoc and still exits 0.
  Rebuilt the four pages lost on 2026-09-16 from in-repo sources only
  (`CLAUDE.md`, `docs/architecture/repo-map.md`, `README.md`,
  `.agents/skills/openral-wiki/SKILL.md`) — re-derivations, flagged as
  such in the index, no attempt to reproduce the lost wording.
  Every `[[wikilink]]` now resolves; no dangling targets remain.
  Operational host state (cricket container, pids, script invocations)
  deliberately stays in the `go2-foxglove-view` skill, not in wiki prose.

## [2026-09-16] query | Front camera cannot see the robot; add Go2 top cam

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- linear: none
- notes: Foxglove 3D showed Go2; `/openral/cameras/front/image` did not.
  Front cam looks +X from the face. Added viz-only `top` (menagerie
  track pose). Layout leads with `top`; sim layout uses all RGB sensors.

## [2026-09-16] query | Front camera gray slab is empty staging, not zoom

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- linear: none
- notes: Go2 `/openral/cameras/front/image` in Foxglove looked like a
  zoomed-in gray card. Local MuJoCo render was ~70° FoV, official URDF
  pose, black sky over a flat `camrig_floor`. Foxglove's dark panel hid
  the sky. Staging floor is now infinite checker + skybox.

## [2026-09-16] query | Foxglove web meshes need package:// + ament overlay

- summary: wiki/analyses/foxglove-web-meshes-need-package-uri.md
- touched: wiki/index.md, wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- new: wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- linear: none
- notes: filed from a cricket Go2 `deploy sim --foxglove` session (Mac web viewer). Studio requests only `package://` from the bridge; the old `rewrite_package_mesh_uris` (`file://`) cannot feed app.foxglove.dev or a laptop desktop Studio. No older wiki page claimed the file:// rewrite (domain had no home after the 2026-09-16 partial restore). Go2 entity page not created — none existed. `wiki/concepts/wiki-maintenance-workflow.md` still lost; not reconstructed.

## [2026-09-16] manual | Wiki references Linear back (provenance only)

- touched: wiki/concepts/task-wiki-contract.md, .agents/skills/openral-wiki/SKILL.md
- linear: none — decided in chat, filed here
- notes: task→wiki stays a mandatory gate; wiki→Linear is optional provenance.
  Two carriers only — a `linear:` line on log entries, and an optional
  `linear:` frontmatter list on pages. Identifier + title, no linear.app
  URLs, because `wiki/` shares an upstream with the public OpenRAL repo.
  Status / acceptance criteria / assignees are banned from page prose: they
  rot, and agents read the wiki as settled belief. OpenRAL work is the
  Linear **Acquire** project, team `LaunchPad` key `1`, so IDs read `1-131`.

## [2026-09-16] manual | Partial restore after uncommitted wiki was destroyed

- restored: wiki/index.md, wiki/log.md, wiki/concepts/second-brain.md,
  wiki/concepts/task-wiki-contract.md, .agents/skills/openral-wiki/SKILL.md
- lost: wiki/entities/openral.md, wiki/concepts/wiki-maintenance-workflow.md,
  wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md, raw/,
  tests/unit/test_wiki_second_brain.py
- notes: the bootstrap was never committed. A concurrent process in this
  working directory moved HEAD (master → c40e8b8 → 7e5a6de → 1ddc80e →
  7f62992, detached) and removed the untracked files. Nothing was
  recoverable: no stash, no `wiki/` path in any git object, no copy on disk.
  The five restored files are verbatim from an agent session that had read
  them in full; the four lost pages were never read and are NOT
  reconstructed, because inventing them would violate CLAUDE.md §1.2.
  Committing the wiki from now on is the fix — that is why this entry
  exists rather than a silent re-bootstrap.

## [2026-09-16] bootstrap | OpenRAL second brain

- summary: seeded wiki from CareTrace / Karpathy LLM-wiki logic
- new: wiki/index.md, wiki/entities/openral.md, wiki/concepts/second-brain.md, wiki/concepts/task-wiki-contract.md, wiki/concepts/wiki-maintenance-workflow.md, wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md
- notes: docs/ + schemas remain normative; tasks must cite wiki pages; skill at `.agents/skills/openral-wiki/`
