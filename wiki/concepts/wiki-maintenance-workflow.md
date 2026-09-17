---
type: concept
tags: [openral, wiki, workflow]
updated: 2026-09-17
---

# Wiki maintenance workflow

How this wiki is changed. The normative version is the skill at
`.agents/skills/openral-wiki/SKILL.md`; this page is the synthesis an
agent reads when it lands mid-task. `CLAUDE.md` wins on conflict.

Rebuilt 2026-09-16 from the skill after the page was lost uncommitted;
close-out made mandatory 2026-09-17 — see `wiki/log.md`.

## Before touching anything

Read `wiki/index.md`, skim the newest `wiki/log.md` entries
(`grep "^## \[" wiki/log.md | tail -10`), then follow the links into the
pages the task actually touches. Answering a project question without
reading the index is the top red flag.

## Directory contract

| Path | Holds | Rule |
| --- | --- | --- |
| `raw/` | dropped source material | never modified after the drop |
| `wiki/sources/` | source summaries | cite the path or URL |
| `wiki/entities/` | concrete things | layers, packages, robots, rSkills |
| `wiki/concepts/` | reusable ideas | architecture, workflow, product |
| `wiki/analyses/` | filed answers and audits | durable synthesis only |
| `wiki/index.md` | catalog | update when pages are added or their blurb changes |
| `wiki/log.md` | audit trail | append on every finished piece of work |

In-repo `docs/`, schemas, and `CLAUDE.md` are standing sources cited in
place. Do not snapshot them into `raw/` and do not copy METHODS
inventories or schema field lists into wiki prose — link instead.

## Close-out is the default operation

A task is not done until the wiki matches what is now true **and**
`wiki/log.md` has an entry. Do not ask whether to file. Skill op:
**Done / finish**. Log op: `work` (or `ingest` / `query` / `lint` when
that is what happened).

1. Patch the pages the work changed beliefs about. Create a thin page
   only when the domain has no home.
2. Durable settled answers → `wiki/analyses/` (`type: analysis`).
3. Refresh [[index]] if the catalog changed.
4. Append a parseable log entry, newest first.
5. Write the files to disk. Commit `wiki/` when the user asked to
   commit the change.

A log with no page update is allowed only when no belief changed (pure
format / typo) — say so in `notes:`. Host-specific PIDs and SSH stay in
the operator skill, not here. Cricket / dashboard / Foxglove start
failures are filed in `.agents/skills/go2-foxglove-view/SKILL.md`
(**Troubleshooting / Start failures**) in the same turn — chat is not
the runbook.

## Other operations

**Ingest.** Read the source in full, discuss 2–4 takeaways and ask what
to emphasize, then write the `wiki/sources/` summary, update every page
the source touches (one source usually touches several), refresh the
index, and append a log entry.

**Query.** Answer from the index plus linked pages, with `[[wikilink]]`
citations. If the answer settled a belief, file it (analysis or home
page) and log `query`. Do not ask _"File this back?"_.

**Lint.** Report orphans, dangling `[[links]]` with no page,
contradictions, stale claims, coverage gaps, leaked task state,
uncommitted `wiki/` changes, and **unlogged work**. Present the report;
let the human prioritize. Never silently resolve a contradiction — flag
it: `> ⚠️ Contradicts [[other-page]]: …`. Append a `lint` entry after.

## Page rules

Kebab-case filenames. YAML frontmatter with at least `type`, `tags`,
`updated` (`linear:` optional — see [[concepts/task-wiki-contract]]).
Obsidian wikilinks. Inline provenance as `(from [[sources/slug]])`.
Uncertainty marked with `?` or a blockquote. Extend an existing page
before creating a near-duplicate.

## Log format

Append-only, newest first, parseable:

```markdown
## [YYYY-MM-DD] work | Title

- summary: wiki/entities/slug.md
- touched: wiki/entities/a.md, wiki/concepts/b.md
- new: wiki/concepts/c.md
- linear: 1-131        # or omit / `none`
- notes: what landed, contradictions, uncertainty
```

Ops: `work` (default close-out), `ingest`, `query`, `lint`, `manual`,
`bootstrap`.

## Commit the wiki

`wiki/` is project memory, not scratch state. The 2026-09-16 partial
restore happened because a bootstrap was never committed and a
concurrent process removed the untracked files — nothing was
recoverable. Finishing a task means the wiki files exist on disk; a
user-requested commit must include them.

Related: [[concepts/second-brain]], [[concepts/task-wiki-contract]],
[[entities/openral]].
