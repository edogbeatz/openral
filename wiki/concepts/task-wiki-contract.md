---
type: concept
tags: [openral, wiki, tasks, linear]
updated: 2026-09-17
linear: [1-131]
---

# Task wiki contract

**Tasks reference the second brain.** Linear issues, PR plans, and agent
task lists are pointers into this wiki, not a parallel knowledge base.

The two directions are not symmetric:

| Direction | Strength | Carries |
| --- | --- | --- |
| Task → wiki | Mandatory. No cite, no task. | Grounding: what the task is about |
| Wiki → Linear | Optional. Provenance only. | History: which issue shaped this page |

Tasks are ephemeral and need grounding, so the forward cite is a gate.
The wiki outlives the tasks, so the back-reference is a convenience and
never a requirement.

## Required Wiki block

Every new task includes:

```markdown
## Wiki
- [[concepts/<page>]] — why this task exists
- [[entities/<page>]] — what it touches
```

If the domain has no page, create a thin one in the same change (or as
the first step of the task), add it to [[index]], then cite it.
No cite, no task.

## Lifecycle

| Moment | Agent does |
| --- | --- |
| Create / plan | Cite pages. Link Linear ↔ wiki, not Linear ↔ chat. |
| Start | Read `wiki/index.md` and the cited pages before editing code. |
| Finish | **Mandatory.** Update touched pages, refresh the index if needed, append `wiki/log.md`. No log entry, the task is not done. Do not ask whether to file. |

Durable answers from a task go under `wiki/analyses/` with
`type: analysis` (from [[concepts/wiki-maintenance-workflow]]). The
skill's **Done / finish** is the close-out checklist; log op is `work`
unless the task was ingest / query / lint.

## Referencing Linear from the wiki

An issue reference is a **resolvable handle, not a copy**. An agent
reading this wiki has the Linear MCP, so a bare identifier is enough to
fetch live title, status, and discussion on demand. The same rule already
applies to `docs/` — cite in place, do not restate.

Store the identifier and the title. No `linear.app` URLs: `wiki/` is
committed to a repo that shares an upstream with the public
`OpenRAL/openral`, and bare IDs keep internal planning hostnames out of it.

OpenRAL work lives in the Linear **Acquire** project (team `LaunchPad`,
key `1`), so identifiers look like `1-131`.

Two places carry references:

**1. Log entries** — a `linear:` line on any `wiki/log.md` entry. The log
is append-only and timestamped, so a reference there states what was true
on that date and can never go stale.

**2. Page frontmatter** — an optional `linear:` list naming the issues
that shaped the page. Greppable, and it answers "why does this page claim
this?" when the reasoning never reached an ADR.

```yaml
---
type: concept
tags: [openral, wiki]
updated: 2026-09-16
linear: [1-131]
---
```

### Never put in page prose

Issue **status**, acceptance criteria, assignees, priorities, or "currently
in flight". These rot within days, and a stale claim in the wiki is worse
than no claim because agents read the wiki as settled belief. If a task
needs live state, resolve the identifier through Linear at read time.

Writing status into pages recreates the failure this contract exists to
prevent, just pointed the other way: the wiki becomes a second, worse
issue tracker.

## What stays outside the wiki

Normative API, public symbols, and layer-boundary ADRs stay in schemas,
`docs/METHODS.md`, and the private management decision log. The Wiki
block cites those via source pages when the task is about a contract
change — it does not restate the contract.

## Example

```markdown
## Wiki
- [[entities/openral]] — harness / layer home
- [[concepts/second-brain]] — why we file this back
```

Related: [[concepts/second-brain]], [[entities/openral]].
