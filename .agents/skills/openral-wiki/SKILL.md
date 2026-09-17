---
name: openral-wiki
description: >-
  Use when finishing any OpenRAL coding, debugging, docs, or planning
  task (mandatory: update wiki pages and append wiki/log.md); and when
  creating, updating, querying, linting, or maintaining the second-brain
  wiki, Obsidian vault, sources, entities, concepts, analyses, index.md,
  or log.md; and when writing Linear issues, PR plans, or agent task
  lists that must cite wiki pages.
argument-hint: 'done / ingest / query / lint / Linear issue / task cite'
---

# OpenRAL Second Brain

Maintain `wiki/` as a persistent LLM knowledge layer. The wiki is not a
scratchpad and it does not replace `docs/`, `docs/METHODS.md`, schemas, or
ADRs. Those stay normative. The wiki is compounding project memory:
synthesis, task context, cross-links, contradictions, and "what we believe
right now."

**Tasks reference the second brain.** Linear issues, PR plans, and agent
task lists cite wiki pages. See [[concepts/task-wiki-contract]].

**Done work is filed.** A task is not finished until the wiki reflects
what changed and `wiki/log.md` has an entry. Chat is ephemeral; the log
is the audit trail. Do not ask whether to file — file.

Keep pages sparse. Prefer updating an existing page over creating a
near-duplicate. Create a new page only when the domain has no home.

Commit `wiki/` changes. The wiki is project memory, not scratch state:
uncommitted pages are one `git clean` away from being unrecoverable.

## First steps

Before changing or answering from the wiki:

1. Read `wiki/index.md`.
2. Skim the latest relevant entries in `wiki/log.md`
   (`grep "^## \\[" wiki/log.md | tail -10`).
3. Read `wiki/concepts/wiki-maintenance-workflow.md` and
   `wiki/concepts/task-wiki-contract.md`.
4. Follow links to the relevant entity, concept, source, or analysis pages.
5. Resolve any `linear:` identifiers you actually need through the Linear
   MCP. The wiki records which issue shaped a page, never its live status.
6. Follow `CLAUDE.md` for engineering rules. If this skill and `CLAUDE.md`
   conflict, `CLAUDE.md` wins.

If `wiki/index.md` or `wiki/log.md` is missing, bootstrap `raw/`,
`wiki/index.md`, `wiki/log.md`, `wiki/sources/`, `wiki/entities/`,
`wiki/concepts/`, and `wiki/analyses/`.

## Directory contract

| Path | Purpose | Rule |
| --- | --- | --- |
| `raw/` | Immutable source material | Never modify after drop |
| `docs/` | Normative engineering docs | Cite; do not copy into wiki prose |
| `wiki/sources/` | Source summaries with provenance | Cite path or URL |
| `wiki/entities/` | Concrete project things | Layers, packages, robots, rSkills |
| `wiki/concepts/` | Reusable ideas and conventions | Architecture, workflow, product |
| `wiki/analyses/` | Saved answers and audits | File useful synthesis |
| `wiki/index.md` | Content catalog | Update on every meaningful change |
| `wiki/log.md` | Chronological audit trail | Append parseable entries; newest first |

Standing sources that already live in-repo (`CLAUDE.md`, `docs/`, schemas)
are cited in place. Do not snapshot them into `raw/` unless the user asks.

## Page rules

- Use kebab-case filenames.
- Start every page with YAML frontmatter containing at least `type`, `tags`,
  and `updated`. `linear:` is optional — see "Referencing Linear" below.
- Use Obsidian wikilinks like `[[entities/openral]]`.
- Prefer updating existing pages over creating near-duplicates.
- Cite sources inline with `(from [[sources/source-slug]])`.
- Mark uncertainty with `?` or a blockquote warning.
- Flag contradictions: `> ⚠️ Contradicts [[other-page]]: ...` — surface
  them, do not silently resolve.
- Do not paste `docs/METHODS.md` inventories or schema field lists into
  wiki pages. Link to the normative file.

## Task contract

Every Linear issue, PR plan, and agent task list must include a **Wiki**
block that cites existing pages (create a thin page first if the domain
has no home):

```markdown
## Wiki
- [[concepts/page]] — why this task exists
- [[entities/page]] — what it touches
```

1. **Create / plan** — cite wiki pages. No cite, no task.
2. **Start** — read `wiki/index.md` and the cited pages before editing code.
3. **Finish** — not optional. Follow **Done / finish** below. No log
   entry, the task is not done.

Do not treat Linear, chat, or a PR description as a second knowledge base.

## Referencing Linear

The task cite is mandatory. The reverse reference is optional provenance —
which issue shaped a page, never what that issue is currently doing. Full
rules in [[concepts/task-wiki-contract]].

OpenRAL work is the Linear **Acquire** project (team `LaunchPad`, key `1`),
so identifiers look like `1-131`. Record the identifier and the title. No
`linear.app` URLs — `wiki/` shares an upstream with the public
`OpenRAL/openral` repo.

Two carriers, and no others:

- `linear:` line on a `wiki/log.md` entry — append-only and dated, so it
  cannot go stale.
- `linear: [1-131]` in page frontmatter — greppable provenance.

Never write issue status, acceptance criteria, assignees, or priorities
into page prose. They rot, and agents read wiki prose as settled belief.
Resolve the identifier through the Linear MCP when live state is needed.

## Operations

### Done / finish (default close-out)

Run this at the end of **every** completed piece of work — a coding
change, a debug session that settled a belief, a docs pass, a plan that
was executed. Do not wait to be asked. Do not skip because the user did
not mention the wiki.

1. Read `wiki/index.md` and the pages the work actually touched (or
   should have a home on).
2. Update those pages so they match what is now true. Patch stale
   claims; do not leave the old belief sitting next to new code.
3. If the domain has no page, create a thin one and add it to the index.
   Durable settled answers go under `wiki/analyses/` with `type: analysis`.
4. Refresh `wiki/index.md` when pages were added, renamed, or their
   one-line catalog blurb changed.
5. Append a `work` (or more specific) entry to `wiki/log.md`, newest
   first. Every close-out has a log line. A page-only update with no log
   is incomplete; a log with no page update is allowed only when no
   belief changed (pure format / typo) — say that in `notes:`.
6. Commit `wiki/` with the rest of the change when the user asked to
   commit; if they did not, still write the files so they are not lost
   to `git clean`. Never leave wiki updates only in chat.

```markdown
## [YYYY-MM-DD] work | Title

- summary: wiki/entities/example.md
- touched: wiki/entities/example.md, wiki/concepts/example.md
- new: none
- linear: 1-131        # or `none`
- notes: what landed, what is still uncertain, contradictions
```

Host-specific runbook state (container names, PIDs, one-off SSH) stays
in the operator skill that owns that host, not in wiki prose. Promote
durable findings here. Cricket / dashboard / Foxglove **start failures**
are appended to `.agents/skills/go2-foxglove-view/SKILL.md` in the same
turn (**Troubleshooting / Start failures**) — do not leave them only in
chat; still close out durable lessons here.

### Ingest

When a user adds a source or asks to process material:

1. Read the source in full.
2. Briefly discuss key takeaways (2–4 bullets). Ask what to emphasize
   before writing.
3. Create or update a summary in `wiki/sources/` with full source frontmatter.
4. Update affected entity and concept pages. A single source typically
   touches several pages.
5. Add only durable new pages when the source introduces something
   important without a home.
6. Update `wiki/index.md`.
7. Append to `wiki/log.md` (op `ingest`, same field list as **Done / finish**).
8. Report back: pages changed, pages created, contradictions surfaced.

### Query

Read `wiki/index.md` first, then relevant linked pages. Answer with
wikilink citations (`[[page-name]]`) and cite raw or `docs/` sources when
quoting. If the answer settled a belief or would be useful next session,
file it under `wiki/analyses/` (or patch the home page), update the
index, and append a `query` log entry. Do not ask _"File this back?"_ —
file it. Skip only trivia that does not change what we believe.

### Lint

When asked to lint or audit the wiki, report:

- **Orphans** — pages with no inbound `[[links]]`.
- **Missing pages** — concepts mentioned in `[[brackets]]` but with no page.
- **Contradictions** — pairs of pages making opposing claims.
- **Stale claims** — pages not updated since a newer source on the same
  topic was ingested.
- **Coverage gaps** — concepts referenced often but thinly covered.
- **Leaked task state** — issue status, assignees, or acceptance criteria
  sitting in page prose instead of Linear.
- **Uncommitted pages** — `wiki/` changes not yet in git.
- **Unlogged work** — recent commits or chat conclusions with no
  `wiki/log.md` entry.
- **Suggested next sources / questions** — what would fill the gaps?

Do not silently resolve contradictions. Present the report, let the user
prioritize, then execute. After the lint itself, append a `lint` log entry.

## Red flags

- Finishing a task without updating the wiki and appending `wiki/log.md`.
- Answering a project question without reading `wiki/index.md`.
- Writing a Linear issue or PR plan with no Wiki cites.
- Summarizing a source without updating cross-referenced pages.
- Asking "file this back into the wiki?" — the answer is yes.
- Creating a new page when an existing one should be extended.
- Silently resolving a contradiction.
- Modifying `raw/`.
- Copying normative `docs/` or METHODS inventories into wiki pages.
- Pasting Linear status or acceptance criteria into page prose.
- Leaving a cricket / dashboard / Foxglove start failure only in chat
  instead of appending `.agents/skills/go2-foxglove-view/SKILL.md`.
- Leaving `wiki/` changes uncommitted at the end of a task the user
  asked to commit; leaving them only in chat in any case.
