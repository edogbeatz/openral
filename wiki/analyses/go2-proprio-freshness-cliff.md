---
type: analysis
tags: [openral, go2, z1, locomotion, rsl-rl, world-state, hal, sim, deploy]
updated: 2026-09-18
linear: none
---

# The Go2 walk has a proprio freshness cliff at 40 ms — and it is not why the live dog tips

Two findings, deliberately in one page because they are easy to conflate: a
**real, sharp stability threshold** on observation age, and the **measurement
that rules it out** as the cause of the live mid-gait tip.

Normative numbers live in `docs/reference/go2-z1-mass-balance.md`; the tool is
`tools/go2_z1_mass_balance.py stale`. Home: [[entities/go2-z1]].

## What we believe now

**`rsl_rl_onnx` locomotion dies on stale proprio, and it is a cliff, not a
slope.** Delaying the policy's whole observation bundle by whole 20 ms policy
ticks, 8 randomised 30 s trials each at the deploy scene's `arm_mass_scale:
0.01` and `vx = 0.5 m/s`:

| proprio age | survived | median distance | tip times |
| --- | --- | --- | --- |
| 0 ms | 8/8 | 12.13 m | — |
| 20 ms (1 tick) | 8/8 | 12.80 m | — |
| **40 ms (2 ticks)** | **1/8** | 8.25 m | 2.9–18.5 s, scattered |
| 60 ms (3 ticks) | 0/8 | 1.67 m | 2.0–4.3 s |
| 80 ms (4 ticks) | 0/8 | 1.82 m | 1.5–3.3 s |

One tick of age is free; two is fatal. This was already known on the bare dog —
`scenes/deploy/go2_walk.yaml` has carried `publish_rate_hz: 200.0` with a
"freshness cliff" comment since before this work — but it had no numbers behind
it and had never been reproduced on the composite over randomised trials. It
now has both, and the rates are guarded by
`tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py`, which brackets the cliff at 1 and
3 ticks.

> ⚠️ **Do not lower `publish_rate_hz` / `odom_publish_rate_hz` on a Go2
> locomotion scene.** The default 30 Hz is 33 ms between samples, which is the
> wrong side of the cliff. This is the one number in Go2 locomotion that behaves
> like a hard engineering limit.

**The live graph is nowhere near the cliff, so staleness is not the tip.**
Measured during a live walk on cricket, the aggregator's cached proprio age is
**median 5.1 ms, p90 10.2 ms, max 41.6 ms** (n = 469). Method: match the joint
vector carried in each `/openral/world_state_fast` snapshot against the 200 Hz
`/joint_states` history and take the time difference — an external measurement
needing no graph relaunch and no code change. RTF ≈ 0.62 only shrinks that age
further in simulated time.

## Why the obvious wiring worry is wrong

The live proprio path is **not** two publish hops. Worth writing down because
the node layout invites the opposite guess:

- The HAL snapshots proprio on its executor thread and a dedicated publisher
  thread emits `/odom` + `/joint_states` at `publish_rate_hz` (200 Hz here).
- The WorldState node caches those in a `WorldStateAggregator`.
- The skill runner calls `aggregator.snapshot()` **in-process** — the aggregator
  is shared by `compose_*_runtime` — and never subscribes to
  `/openral/world_state_fast`.

So `publish_rate_hz_fast` (30 Hz) is an **observability** rate only. It is not
in the policy's observation path and raising it would not make a walk safer.

Related: `/openral/world_state_fast` was measured publishing at **11.2 Hz**
against that 30 Hz timer while `/odom` sustained 197 Hz. The runtime node's
publish work is starved. Real, but not the policy path.

## Also closed: no twist frame mismatch

`WorldState.base_twist` is an untagged `tuple[float × 6]` with no frame in the
type, so a world-frame vs body-frame mix-up would pass `mypy --strict` — which
made it a live suspect. It is not happening: the twist passes **verbatim** from
`Go2MujocoHAL` through `/odom`, `pose_twist_from_odometry_fields`, the
aggregator and `WorldState` to the policy, with no transform at any hop, and the
HAL's free-joint `qvel[3:6]` is already in the child (base) frame — the Isaac
Lab `base_ang_vel` term the checkpoint trained on.

The type hole is still a hole. Frame-tagging the twist would be an
`openral_core` schema change with a `schema_version` story, so it is worth an
ADR rather than a drive-by.

## Open

- **The live mid-gait tip is still unexplained**, now with eleven eliminated
  explanations. Catalogue in `.agents/skills/go2-foxglove-view/SKILL.md`.
- **It is intermittent, not deterministic.** Two live walks during this work ran
  34 s / 5.5 m without tipping while showing the same leftward drift
  (`dy ≈ −1.3 m`) that precedes the failures; roughly 3 tips in 5 walks. Any
  future candidate fix needs a multi-trial **live** battery — one good rollout
  already misled this investigation once (the tucked arm).
- **Frame-tagged twist types** — would turn a whole class of silent bug into a
  type error. Needs an ADR.

Related: [[analyses/go2-z1-arm-pose-decides-the-walk]], [[entities/go2-z1]],
[[entities/go2]], [[concepts/deploy-sim-visualization]].
