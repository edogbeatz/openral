---
type: log
tags: [openral, log]
updated: 2026-09-16
---

Each entry starts with `## [YYYY-MM-DD] <op> | <title>`. Ops: `ingest`, `query`, `lint`, `manual`, `bootstrap`.

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
