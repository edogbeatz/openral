---
type: concept
tags: [openral, wiki, workflow]
updated: 2026-09-16
---

# Second brain

The OpenRAL wiki is a Karpathy-style LLM wiki: the model writes and
maintains compiled pages; humans curate sources and ask questions.

## Three layers

1. **Raw** (`raw/`) — immutable dropped sources. Never edit after ingest.
2. **Wiki** (`wiki/`) — compiled markdown the agent owns.
3. **Schema** — `CLAUDE.md` + `.agents/skills/openral-wiki/SKILL.md`.
   `CLAUDE.md` wins on conflict.

In-repo engineering docs (`docs/`, schemas, METHODS) are standing sources
cited in place. They are not copied into `raw/` unless someone asks.

## What compounds

New sources update several pages, strengthen `[[wikilinks]]`, and record
contradictions. That is the point. A chat answer that is not filed
disappears.

## What this is not

- Not the published mkdocs site.
- Not a second `docs/METHODS.md`.
- Not a place to invent DDS topics, ports, or schema fields.
- Not a replacement for tests or ADRs.

Related: [[concepts/wiki-maintenance-workflow]], [[concepts/task-wiki-contract]],
[[entities/openral]].
