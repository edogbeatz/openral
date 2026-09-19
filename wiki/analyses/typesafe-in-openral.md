---
type: analysis
tags: [openral, typesafe, reasoner, s2]
updated: 2026-09-19
---

# TypeSafe in OpenRAL — advisor, not actuator

Settled 2026-09-18 from [[sources/typesafe-system-one]] plus the live
reasoner path. TypeSafe is a **layer-4 (S2) judgment sidecar**. It does
not become an rSkill, does not publish `ActionChunk`, and does not sit
in the C++ safety kernel.

OpenRAL already has typed *actuation* contracts. What it lacks is typed
*judgment* on natural language: which skill, whether to call the LLM at
all, whether a VLM "yes" is actually yes, which replanning rung to take.
Today those are either LLM-over-closed-palette or regex/token
heuristics. TypeSafe's three primitives (Choice / Score / Noul) fit that
gap because they return values code can branch on.

Copy the zappi-cli shape: one questions file, one policy file that
combines answers in Python, one `system_one()` call, opt-in via env.
Home: [[entities/openral]].

## Name collision

| Name | What it is |
| --- | --- |
| OpenRAL **S1** | Fast rSkill policy, 30–200 Hz, `ActionChunk` |
| OpenRAL **S2** | Event-driven reasoner LLM, typed `ReasonerToolCall` |
| TypeSafe **System One** | Fast structured *judgment* API (Jev) |

Keep TypeSafe inside S2 as a gate/advisor. Never as S1.

## What already exists (do not duplicate)

Deterministic and already typed — leave them:

- Prompt fan-in (`prompt_router` → `/openral/prompt`)
- Palette filter: embodiment, capabilities, role, commercial license
- Pydantic `ReasonerToolCall` decode + palette membership
- Retry cap / attempts cap / human-handoff terminal
- C++ safety kernel, E-stop, `ROSSafetyViolation`
- `rSkill._check_license` / `OPENRAL_ALLOW_NONCOMMERCIAL`

LLM-chosen today, the insertion surface:

- Which `execute_rskill__<id>` to pick (`DEFAULT_SYSTEM_PROMPT` prose)
- Substitute-skill / goal-replan rungs (documented as **partial**)
- `fallback_skill_id` on the manifest — **schema only, no runtime consumer**
- `parse_yes_no` token heuristic on VLM completions
- `is_collective_target` regex for "all the objects"

## How it helps (ranked)

1. **Skill shortlist before the expensive tick.** One Choice over the
   already-filtered palette plus a Noul "does this turn need a skill at
   all?" Shrink the LLM palette to top-k. TypeSafe's skill-suggestion
   cookbook is this pattern. Highest leverage: skill matching is
   currently prompt prose over the full compatible set.
2. **Skip the LLM on obvious commands.** "Walk forward" / "stop" /
   dashboard Apply can be a Choice `handler ∈ {deterministic_skill,
   reasoner, human, refuse}` with a confidence floor. Low-confidence →
   current LLM path. Matches TypeSafe intent-routing.
3. **Finish the replanning ladder.** Noul: "is retrying the same skill
   likely to work?" Choice: which substitute from the palette. Score:
   how much the goal itself needs a replan. Code picks the rung;
   `fallback_skill_id` can finally be consumed as a candidate, not as
   a silent default.
4. **Replace `parse_yes_no`.** Scene VLM still describes the image;
   a Noul on `{vlm_text, goal, world_state}` returns P(complete) plus
   confidence instead of token-matching `"done"` vs `"abandoned"`.
5. **Screen reasoner I/O.** Parallel Nouls for "asks to bypass e-stop",
   "asks to disable safety", "asks to ignore workspace limits" — then
   `human-handoff` / `refuse`. This is a **reasoner-layer** gate, not a
   replacement for the C++ kernel. Fail **closed** on this battery if
   TypeSafe is unreachable.
6. **Collective-goal gate.** Semantic Noul instead of
   `is_collective_target` regex — same seam, fewer false misses.

Do **not** spend TypeSafe on: license posture, embodiment matching,
`is_walk_skill_id` dashboard substring, span name→family telemetry,
whether a locomotion skill will *balance* (Jev has no physics), or
anything at >1 Hz. Hop vs walk is a palette Choice, not a Score of
gait quality.

Acquire is a second, legal Jev surface — catalog rank and near-parent
pick **after** the family table, never the hard gate or remap. Landed
in the sibling (`ACQUIRE_TYPESAFE=1`). See [[analyses/creating-acquire]]
§ TypeSafe / Jev on Acquire. Do not duplicate the Go2 walk/hop/arm
battery there; that is this reasoner gate over an already-installed
palette.

## Wiring (no layer crossing)

Stay in `python/reasoner/` (layer 4). Prompt router stays a fan-in.
Safety kernel stays C++.

**Landed 2026-09-18 (opt-in):** `openral_reasoner.typesafe_questions` /
`typesafe_policy` / `typesafe_gate`. `ReasonerNode` LLM worker calls
`apply_typesafe_to_tick` when `OPENRAL_TYPESAFE=1` and
`TYPESAFE_API_KEY` are set (`just sync --group typesafe`). Off by
default. Walk/arm extras are keyed off `goal_params_schema` so Nav2
does not get Go2 joystick params. Colloquial **go left** / **left** /
**walk left** is `walk_command=turn_left` (yaw) and
`handler=deterministic_skill` — not strafe, not an S2 plan. Strafe
only when the operator said strafe or sidestep. Hop
(`rskills/rsl-rl-onnx-go2-spring-jump`) is the dashboard hop skill on
`go2_z1` (no `velocity_commands` schema; YAML `jump_trigger` 1.0); live Jev 2026-09-19 splits
"hop" / "walk forward" / "park the arm" and leaves YAML hop zeros when
`walk_command=none`. Not yet landed: substitute-skill rung,
`parse_yes_no` replacement, collective-goal Noul, a post-LLM veto.

```
prompt_in → PromptRouter (unchanged)
         → ReasonerNode._on_prompt
              → ReasonerCore.prepare_tick
              → LLM worker:
                   TypeSafeGate.assess          # parallel questions
                   handler=deterministic → ExecuteRskill, skip LLM
                   handler=human/refuse  → WaitTool, skip LLM
                   handler=reasoner      → shrink palette, ## TYPESAFE
                                         → ReasonerCore.run_prepared_llm
              → _finish_llm_tick → _dispatch (existing)
              → ExecuteRskill → C++ safety (untouched)
```

State sent today: operator prompt + palette rows (id, description,
actions, objects, scenes). No pixels, no tensors, no `ActionChunk`.

Package:

- Opt-in group: `typesafe-sdk` (MIT). Not in default `just sync`.
- Env: `TYPESAFE_API_KEY` + `OPENRAL_TYPESAFE=1`. No hidden default.
- Questions as constants; thresholds in `typesafe_policy.py`.
- Own Pydantic result types in `openral_reasoner`; SDK types do not
  leak into `openral_core`.
- Missing SDK / failed API call: **fail open to the LLM**. A high
  `asks_bypass_safety` noul (when TypeSafe *did* answer): **fail
  closed** to `WaitTool`. Unreachable TypeSafe does not invent a
  safety refuse — that would halt every prompt when the sidecar is
  down.
- Tests: `tests/unit/test_reasoner_typesafe.py` with a network-boundary
  `_StaticAsker` and real `rskills/*/rskill.yaml` fixtures.

A thin client in the reasoner is **not** a layer-boundary move. Giving
TypeSafe `ActionChunk` authority, or putting it inside
`openral_safety_kernel`, **is** — do not.

## What we would not get

Jev does not see cameras. It cannot replace locate_in_view, query_scene,
or any S1 policy. It cannot make a walk skill balance. It cannot be the
safety kernel. It is a calibrated classifier sitting next to the S2 LLM
so OpenRAL stops asking a text model to pretend it is an enum.
