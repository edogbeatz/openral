---
type: analysis
tags: [openral, acquire, product, backstory]
updated: 2026-09-19
linear: [1-189, 1-195, 1-225]
---

# Creating Acquire — backstory

Filed after reading the sibling Acquire wiki, `acquire-api`, and Linear
project Acquire against this OpenRAL fork. Normative product prose lives
in `edogbeatz/robo-skill-acquire`; this page is the OpenRAL-side belief
about how the two repos fit.

## The gap OpenRAL leaves

[[entities/openral]] is a typed runtime: HAL, sensors, world state,
rSkill loader, reasoner, safety kernel, sim/deploy. Capabilities are
Hugging Face **rSkills**. The reasoner only executes what is already in
the closed palette. Install today is a human/operator step
(`openral rskill install …`).

That is enough to **run** a skill and **refuse** a wrong body. It is not
enough for an agent that hits a task it has no skill for: rank before
download, near-miss fit, keep only after a named scene proves it.

Do not treat OpenRAL's adjacent surfaces as that loop. Same words,
different jobs:

| OpenRAL already does | Not Acquire |
| --- | --- |
| `openral rskill search` / `search_hub_rskills` | Human Hub catalog. Text + facets. No rank-before-download for an agent, no family-near list. |
| `rSkill.check_capabilities` / embodiment tags | Load-time **hard refuse**. Raises `ROSCapabilityMismatch`. No `MismatchReport`, no remap branch. |
| Reasoner `active_search` | Scene-graph hunt for a missing object. Not a skill catalog. |
| HAL near-miss probes | Collision millimeters. Not morphology. |
| `openral rskill install` | Operator step. The reasoner never grows its own palette. |

A Franka skill on a Go2 is already dead in OpenRAL. That is why reject
stays cheap and must stay in the runtime. Acquire exists for the case
OpenRAL cannot finish: **go2 on go2edu** (near) → contract remap →
verify → promote; or **no card at all** → search, install, warrant.

## What Acquire is

[[entities/acquire]] (`edogbeatz/robo-skill-acquire`) owns that missing
loop. Control plane is FastAPI + Postgres (Railway). GPU verify is a
worker on Brev cricket that execs `openral deploy sim` — it does not
reimplement HAL/reasoner/safety. Seeds + a curated Hub card mirror are
the v0.1 catalog. Embodiment is a **request field**, never hardcoded;
default demo is quadruped Go2 (`go2_bench` pipe / `go2_velocity_flat`
loco).

Two lanes:

- **Lane A** — near miss → contract remap fork → must verify before
  promote. On-stage adopt is **go2 → go2_z1** (walk card retargets
  tags; OpenRAL still hold-pads the same 12-D rows + sticky arm
  freeze — remap ≠ a 19-D policy). `go2edu` stays a valid family
  body; it is not on the dual-body stage.
- **Reject** — unladen hop on Go2+Z1. Acquire `check=payload`
  (4.69 kg Z1 vs 0 kg hop budget). Not remappable. OpenRAL can still
  hold-pad hop for the dashboard picker; Acquire will not warrant it.
  See sibling `wiki/analyses/presentation-catalog.md`.
- **Lane B** — exact fit → install; verify when you need the warranty.

Scope lock (Acquire wiki, 2026-09-15): sit atop external train/teleop
stacks. Own **adoption + verify**. No training farm until that wedge is
done. Isaac Lab stays the **train** source for `rsl_rl_onnx`; OpenRAL
verify for the hackathon stays MuJoCo. A native Lab Go2 env is a
sidecar follow-up, not the MVP backend ([[analyses/isaac-lab-with-openral]]).
On-stage walk adopt is tag-fork + 12→19 hold-pad. A payload-aware
gait is mjlab resume, then Lane B on a **new** card — still 12-D
([[analyses/go2-z1-payload-walk-finetune]]).

## How the two repos create it

1. **Substrate (this fork).** Acquire cannot warrant a skill OpenRAL
   cannot load. Pin hooks and fork PRs exist so Hub Go2 rsl-rl weights
   decode, spawn at Hub home, see IMU/gravity, and finish a finite
   horizon without false-promote from stale ROS logs or HAL-up-only.
2. **Acquisition tool (sibling).** `POST /v1/skills/search` ranks cards.
   `POST /v1/skills/acquire` gates, optionally remaps, installs
   `promoted=false`, enqueues verify, promotes only on `skill_ran`.
   MCP `acquire_skill` is the same semantics for S2.
3. **Demo that shows embodiment.** Flat walk is hard to read as the
   product. Scope call 2026-09-18: **Go2 only** — no so101 arm on
   stage. The two bodies are bare [[entities/go2]] and the 19-DoF
   [[entities/go2-z1]], one 12-D walk skill across both (hold-pad
   12→19 + sticky arm hold), which is also the half that is ours
   rather than upstream's. `GET /simple` is that demo: UNIT Bare Go2 /
   Go2+Z1, empty SKILL until chat Acquire proposes (walk fit / adapt-ask
   / hop reject). Arm_ready is out of the presentation catalog this slice.
   Optional SportClient Sit is a weightless card, not a new
   policy family.
4. **Later, same registry.** Seller cards, dual license, settlement.
   Not the MVP face.

## Honesty this wiki must keep

- Scripted `seed/rskill-go2-locomotion-12dof` on gravity-off
  `go2_bench` is **pipe control**, not a learned gait
  ([[entities/go2]]).
- `seed/rskill-rsl-rl-onnx-go2-velocity-flat` is **packaged, not
  `skill_ran`** until SimOps greens cricket on `go2_velocity_flat`.
- SmolVLA LIBERO on Go2 is leftover 12-vs-8 plumbing.
- Capsule ACM extras are home-stand admits, not cert.
- OpenRAL safety is uncertified; weight licenses ≠ seller package.
- Acquire's Go2 / Go2+Z1 / SO-101 beachhead did **not** run
  `quantize_rskill` or ship NF4. Walk is fp32 ONNX; Z1 is a scripted
  fp32 hold; SO-101 eraser_place is a bf16 wrap. In-tree NF4 cards
  (MolmoAct2, Robometer, …) are OpenRAL's, not this wedge.
- OpenRAL does **not** auto-quantize every load. `Skill.configure`
  always calls `on_quantize` (default no-op). Packing (NF4/int8) is
  manifest `quantization.dtype`, or `$OPENRAL_QUANTIZATION_DTYPE` /
  `VLASpec.extra.dtype`. GR00T / RLDX / BEHAVIOR default NF4 on load
  even when the card is named bf16. ONNX Runtime refuses post-load
  quantize — it must be pre-applied. Our three cards declare fp32 /
  bf16, so the hook is a no-op.

## TypeSafe / Jev on Acquire

Yes, as a **judgment sidecar on retrieve**, not as a second runtime.
OpenRAL already uses Jev that way on the installed palette
([[analyses/typesafe-in-openral]]). Acquire's gap is the same shape
one layer earlier: rank a catalog before download, and decide
near-miss vs far-miss in language, while the cheap typed gates stay
code.

Apply it here:

- **Search shortlist.** Replace token-overlap `rank_score` with a
  Choice over already-gated cards (`task` + `embodiment` + card
  blurbs). TypeSafe's skill-suggestion pattern. Highest leverage:
  retrieve is the product face and it is currently bag-of-words.
- **Need-a-skill Noul.** "Does this session already have a promoted
  card that covers the task?" Skip acquire when the palette is enough.
- **Near-miss Noul after the family table.** Only among cards that
  `is_near_morphology` already accepted. Jev picks which near parent
  to remap when `allow_adapt` has several; it does not invent
  go2↔franka.

Do **not** spend Jev on:

- Hard reject (embodiment intersect, capabilities, license) —
  `evaluate_gate` stays the only refuse.
- Family membership — Franka and Go2 both `joint_position` is still
  far. A Noul must not override `DEFAULT_TAG_FAMILIES`.
- Remap rules (tag retarget, aliases, joint order, gripper scale) —
  tables in `adapt.py`.
- Verify / `skill_ran` / promote — OpenRAL `deploy sim`, not Jev.
- Motors, safety, gait quality.

Copy the landed OpenRAL shape in the sibling: one questions file, one
policy file, one `system_one()` call, opt-in
(`ACQUIRE_TYPESAFE=1` + `TYPESAFE_API_KEY`). Fail **open** to today's
ranker if Jev is down. Fail **closed** never: unreachable Jev must
not reject a legal card or mint a family.

**Landed 2026-09-19** in `edogbeatz/robo-skill-acquire`
(`typesafe_questions.py` / `typesafe_policy.py` / `typesafe_gate.py`,
wired from `retrieve.py` + `acquire_skill`). Search returns `ranker`;
acquire can skip when the session palette already covers; `/health`
reports `typesafe`. Railway `acquire-api` `/health` reports
`typesafe:on` after those two vars (2026-09-19). Laptop `/simple` still needs `ACQUIRE_API_URL` + `ACQUIRE_API_KEY`
on the process that serves `:4318`. `just dashboard-acquire-env`
writes `~/.openral/dashboard.env`; `openral dashboard` loads it
into empty `ACQUIRE_API_*`. Empty URL is FAULT, not a Jev miss.
This harness does not import that sidecar.

## One sentence

We are not building a better OpenRAL. We are building the layer that
feeds it skills the current robot did not ship with — ranked, gated,
adapted if near, verified on a named scene, then handed to the reasoner
as a closed palette.

Sibling catalog: `robo-skill-acquire/wiki/index.md`. Start there:
`analyses/system-documentation`, `comparisons/ours-vs-openral`.
