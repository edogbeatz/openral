---
type: source
tags: [openral, claude-md, rules, safety, licensing]
updated: 2026-09-19
source: CLAUDE.md
source_kind: in-repo
---

# Source — Engineering playbook (`CLAUDE.md`)

Path: `CLAUDE.md` (repo root). Standing source, cited in place and never
snapshotted into `raw/`. `AGENTS.md` is a three-line pointer at it for
tool-neutral agents; vendor-neutral skills live in `.agents/skills/`.

Rebuilt 2026-09-16 after the page was lost uncommitted. This is a map of
what the playbook governs, not a copy — read the file for the rules.

## What it is

The single contract for AI agents and human contributors: operating
principles in priority order, coding standards, architecture discipline,
the PR checklist, and the exception hierarchy. When this wiki and
`CLAUDE.md` disagree, `CLAUDE.md` wins.

## The parts that surprise people

- **Priority order is load-bearing.** Safety beats helpfulness; truth
  beats plausibility. Refusing a request is the documented behavior for
  anything that bypasses a safety check.
- **Types are the contract.** Only `openral_core` schemas and
  `packages/msgs/` IDL are normative API; everything else is
  implementation detail.
- **Don't duplicate — search `docs/methods/` first.** A public symbol
  added, renamed, moved, or removed without its `docs/methods/` update is
  an incomplete PR. `tools/refresh_methods_linenos.py` keeps the `(LNN)`
  markers honest.
- **Docs travel with the code.** No "docs follow-up" PRs. That includes
  the hand-edited repo state map (see [[sources/repo-map]]).
- **Wiki close-out is mandatory.** Every finished task updates the
  pages it touched and appends `wiki/log.md` (skill
  `.agents/skills/openral-wiki/`, op `work`). Chat is not project
  memory. Ask-to-file is banned — file.
- **Pre-existing errors get their own commit** — a separate prior
  `fix(...)` on the same branch, never folded into the feature commit.
- **Conventional Commit types decide the release.** `fix` → patch,
  `feat` → minor, `!` → minor while <1.0; `docs`/`test`/`chore` are
  silent in both the changelog and the version bump.
- **Env rule:** `just sync`, never bare `uv sync`.

## Where it points

Repo layout → [[sources/repo-map]]. Public symbols → `docs/METHODS.md`.
Operator `/simple` → `docs/quickstart/dashboard.md` (agents run
`just dashboard` / `scripts/start-app.sh` when asked to start the app).
Releasing → `docs/contributing/releasing.md` (one lockstep SemVer across
root and every `python/*`; never hand-edit a `version =`). Decisions →
`docs/decisions.md`, with the ADR log itself in the private
`OpenRAL/management` repo.

## Licensing posture

The public repo is uniformly Apache-2.0. Commercial capabilities live in
the private OpenRAL Pro monorepo. Third-party **weights** keep their
upstream license and it is version-specific, not family-wide — the
playbook carries the full VLA license matrix, including which checkpoints
are noncommercial and which env vars gate them. Provenance signing is
**planned, not implemented**: skills are not "signed" or "verified" today.

Related: [[entities/openral]], [[concepts/task-wiki-contract]].
