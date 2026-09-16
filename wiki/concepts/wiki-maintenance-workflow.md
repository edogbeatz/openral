---
type: concept
tags: [openral, wiki, workflow]
updated: 2026-09-16
---

# Wiki maintenance workflow

How this wiki is changed. The normative version is the skill at
`.agents/skills/openral-wiki/SKILL.md`; this page is the synthesis an
agent reads when it lands mid-task. `CLAUDE.md` wins on conflict.

Rebuilt 2026-09-16 from the skill after the page was lost uncommitted —
see `wiki/log.md`.

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

In-repo `docs/`, schemas, and `CLAUDE.md` are standing sources cited in
place. Do not snapshot them into `raw/` and do not copy METHODS
inventories or schema field lists into wiki prose — link instead.

## Three operations

**Ingest.** Read the source in full, discuss 2–4 takeaways and ask what
to emphasize, then write the `wiki/sources/` summary, update every page
the source touches (one source usually touches several), refresh the
index, and append a log entry.

**Query.** Answer from the index plus linked pages, with `[[wikilink]]`
citations. Ask whether to file the answer back; if yes it becomes a
`wiki/analyses/` page with `type: analysis`.

**Lint.** Report orphans, dangling `[[links]]` with no page,
contradictions, stale claims, coverage gaps, leaked task state, and
uncommitted `wiki/` changes. Present the report; let the human
prioritize. Never silently resolve a contradiction — flag it:
`> ⚠️ Contradicts [[other-page]]: …`.

## Page rules

Kebab-case filenames. YAML frontmatter with at least `type`, `tags`,
`updated` (`linear:` optional — see [[concepts/task-wiki-contract]]).
Obsidian wikilinks. Inline provenance as `(from [[sources/slug]])`.
Uncertainty marked with `?` or a blockquote. Extend an existing page
before creating a near-duplicate.

## Log format

Append-only, newest first, parseable:

```markdown
## [YYYY-MM-DD] ingest | Title

- summary: wiki/sources/slug.md
- touched: wiki/entities/a.md, wiki/concepts/b.md
- new: wiki/concepts/c.md
- linear: 1-131        # or omit / `none`
- notes: contradictions, uncertainty, open questions
```

Ops are `ingest`, `query`, `lint`, `manual`, `bootstrap`.

## Commit the wiki

`wiki/` is project memory, not scratch state. The 2026-09-16 partial
restore happened because a bootstrap was never committed and a
concurrent process removed the untracked files — nothing was
recoverable. Finishing a wiki task means committing it.

Related: [[concepts/second-brain]], [[concepts/task-wiki-contract]],
[[entities/openral]].
