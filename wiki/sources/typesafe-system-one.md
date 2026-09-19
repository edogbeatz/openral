---
type: source
tags: [openral, typesafe, reasoner]
updated: 2026-09-18
---

# TypeSafe System One (Jev)

External docs for TypeSafe's **System One** API: send a shared *state*
plus many typed *questions*; get structured answers (choice / score /
noul) with probabilities and confidence. No generated text, no parsing.
Questions in one call are evaluated in parallel and in isolation.

- Intro: <https://docs.typesafe.ai/introduction>
- Index: <https://docs.typesafe.ai/llms.txt>
- Python SDK: <https://docs.typesafe.ai/sdk/python> (`typesafe-sdk`, MIT)
- JS SDK: `@typesafe-ai/sdk` (already used in out-of-tree `zappi-cli`)
- Patterns: speculative fan-out, confidence-gated routing, intent
  routing, LLM I/O guardrails, skill suggestion

**Not OpenRAL S1.** TypeSafe's "System One" is Kahneman-style fast
judgment for software. OpenRAL **S1** is the 30–200 Hz rSkill policy
that emits `ActionChunk`. Do not collapse the names.

OpenRAL ships the SDK only as the opt-in `typesafe` group
(`just sync --group typesafe`). Wiring: [[analyses/typesafe-in-openral]].
