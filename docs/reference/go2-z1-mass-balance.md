# Go2 + Z1 mass balance — measured

Where the composite's centre of mass sits, what that does to the shared
rsl-rl locomotion skill, and why the obvious fix does not work.

Produced by [`tools/go2_z1_mass_balance.py`](../../tools/go2_z1_mass_balance.py)
on real menagerie assets, the real composed MJCF, and the real Hub checkpoint
`hf://diasAiMaster/unitree-go2-velocity-flat`. Every number below is a
measurement; none is inferred.

## Why this exists

`robots/go2_z1/robot.yaml` bolts a 4.69 kg Z1 onto a 15.25 kg Go2 at
`mount_pos: [0.18, 0.0, 0.06]` and walks it with
`rskill-rsl_rl_onnx-go2-velocity_flat`, a policy trained on the **bare** dog.
The manifest's standing workaround is
`scene_defaults.composition.arm_mass_scale: 0.01`, which keeps the meshes and
discards ~99 % of the payload.

The intuitive fix is to park the arm so the composite centre of mass returns to
where the bare dog's was. That hypothesis was tested here and **rejected**.

## Statics

Legs at Hub stand; the free base is dropped until the lowest foot sphere rests
on `z=0`, so the support polygon is the one the feet actually make (feet at
x = +0.192 / −0.195, y = ±0.115). `offset` is the horizontal distance from
MuJoCo's whole-model `subtree_com[0]` to the centroid of the four foot contacts.

`arm_mass_scale: 1.0` — 19.90 kg total, 4.69 kg arm:

| arm pose | CoM offset | trot-line margin | nearest polygon edge | CoM height | self-collisions |
|---|---|---|---|---|---|
| `fold` | 23.54 mm | 11.97 mm | 114.86 mm | 0.3201 m | **5** |
| `home` | 37.75 mm | 19.22 mm | 114.86 mm | 0.3427 m | 0 |
| `ready` | 54.82 mm | 27.94 mm | 114.86 mm | 0.3622 m | 0 |

`arm_mass_scale: 0.01` — 15.25 kg total, 0.047 kg arm — collapses the spread to
0.20–0.61 mm, which is the bare dog. That is what the workaround buys: the arm
becomes invisible to the statics.

Two things to read off the table:

* **The four-foot polygon was never the constraint.** `static` is 114.86 mm for
  every pose — the nearest edge is a *side* edge, and the arm only moves the
  centre of mass along x, so the margin does not even change. Nothing here is
  close to statically tipping.
* **`fold` is not a usable pose.** All-zero servos put 5 arm-vs-robot contacts
  in the static pose, whatever its balance.

A joint-space search does find well-centred poses: `(0, 0.20, −1.10, −1.00)`
lands 0.60 mm off the centroid with the centre of mass 10 mm lower than `ready`,
collision-free, every joint ≥ 0.2 rad off its stop. It was **not** shipped — see
below for why.

## The hypothesis, and its rejection

Rollouts use the production path: the composed MJCF stepped through
`Go2Z1MujocoHAL` (same PD law, same sticky arm snap) at the checkpoint's own
`step_dt: 0.02`, with the real ONNX policy in the loop. `vx = 0.5 m/s`.
Because both the policy and MuJoCo are deterministic, each pose is run over
randomised initial conditions (base yaw, leg positions, leg velocities) rather
than once — one rollout per pose is an anecdote, and the first single-rollout
pass drew the opposite conclusion from the one the batteries support.

**8 trials × 20 s, `arm_mass_scale: 1.0`:**

| arm pose | CoM offset | survived | median distance | median speed (0.5 m/s commanded) |
|---|---|---|---|---|
| `ready` | 54.82 mm | 8/8 | 9.92 m | 0.496 m/s |
| `fold` | 23.54 mm | 8/8 | 3.43 m | 0.172 m/s |
| `home` | 37.75 mm | **0/8** | 0.57 m | tips at ~0.7 s |
| *(centred, 0.60 mm)* | 0.60 mm | 8/8 | 7.24 m | 0.362 m/s |

The centred pose survives but tracks the velocity command **27 % slower** than
`ready`, whose offset is 91× worse. To test the relationship rather than four
hand-picked poses, eight collision-free poses spanning the whole offset range
were run at 6 trials × 15 s:

| CoM offset | 0.45 mm | 4.96 mm | 12.15 mm | 20.11 mm | 27.84 mm | 36.99 mm | 45.43 mm | 54.72 mm |
|---|---|---|---|---|---|---|---|---|
| survived | **0/6** | 6/6 | 6/6 | 4/6 | **0/6** | **0/6** | **0/6** | 6/6 |

Survival is scattered across the axis: the best-centred pose in the set fell
every time and the worst-centred one walked every time. **Centre-of-mass offset
does not predict whether this policy stays upright.** The trot-line margin is
collinear with the offset and predicts no better.

**Pitch inertia was the second candidate, and also fails.** Interpolating
`home → ready` gives a clean monotone boundary that looks like an inertia
threshold (`I_yy` 1.03 → 1.44 kg m², survival 0/5 → 5/5), but along that line
inertia and offset are collinear. Breaking the collinearity kills it: two poses
at `I_yy` 1.335 and 1.337 went 6/6 and 0/6, the highest-inertia pose in the set
(1.528) went 0/6, and a deliberately-chosen low-offset/high-inertia pose managed
only 2/6.

So the arm pose matters enormously and reproducibly, but **the mechanism is not
a bulk mass property and is not identified here.** Arm contacts were zero in
every rollout, so it is not the arm striking the body or the floor; the failures
pitch over inside the first second, before a steady gait establishes. Do not
present a pose as a locomotion improvement on statics alone.

## Observation freshness — the one threshold that is sharp

Every property above is either scattered or unexplained. Observation age is
neither: it produces a clean cliff, and it is the only quantity measured here
that behaves like an engineering limit.

The loop above reads the HAL in-process, so the policy sees proprio of age
zero. A deploy graph cannot offer that. There the HAL snapshots proprio on its
executor thread, a publisher thread emits `/odom` + `/joint_states`, and the
WorldState aggregator caches them until `aggregator.snapshot()`. Delaying the
whole observation bundle — it travels as one `ProprioFrame` live — by whole
policy ticks, 8 trials × 30 s at `arm_mass_scale: 0.01` and `vx = 0.5 m/s`:

| proprio age | survived | median distance | worst lateral drift | tip times |
|---|---|---|---|---|
| 0 ms (0 ticks) | 8/8 | 12.13 m | 5.50 m | — |
| 20 ms (1 tick) | 8/8 | 12.80 m | 6.19 m | — |
| 40 ms (2 ticks) | **1/8** | 8.25 m | 13.96 m | 2.9, 4.2, 4.5, 10.8, 12.4, 13.8, 18.5 s |
| 60 ms (3 ticks) | **0/8** | 1.67 m | 0.98 m | 2.0–4.3 s |
| 80 ms (4 ticks) | **0/8** | 1.82 m | 0.74 m | 1.5–3.3 s |

One tick of age is free; two is fatal. This is the measurement behind
`publish_rate_hz: 200.0` / `odom_publish_rate_hz: 200.0` in
`scenes/deploy/go2_z1_walk.yaml`, which previously carried only a comment
asserting a "proprio freshness cliff" with no numbers. **Do not lower those
rates.** `tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py` brackets the cliff at 1
and 3 ticks so a future change cannot cross it silently.

The 40 ms row is also the only configuration reproduced anywhere that resembles
the live mid-gait tip: late, scattered tip times and roughly double the lateral
drift, versus the immediate collapse at 60 ms and beyond.

### It is not, however, why the live dog tips

Measured on the running deploy graph during a walk, the aggregator's cached
proprio age is **median 5.1 ms, p90 10.2 ms, max 41.6 ms** (n = 469, obtained
externally by matching the joint vector in each `/openral/world_state_fast`
snapshot against the 200 Hz `/joint_states` history). That is inside the 8/8
band even before accounting for the sim running at RTF ≈ 0.62, which only makes
the age smaller in simulated time. Staleness is therefore **excluded** as the
cause of the live tip.

Two related hypotheses were closed at the same time, by reading the path rather
than measuring it:

* **No twist frame mismatch.** `base_twist` passes verbatim from
  `Go2MujocoHAL` through `/odom`, `pose_twist_from_odometry_fields`, the
  aggregator, and `WorldState` to the policy, with no transform at any hop. The
  HAL's free-joint `qvel[3:6]` is already in the child (base) frame — the Isaac
  Lab `base_ang_vel` term the checkpoint trained on.
* **The 30 Hz WorldState publish is not in the policy path.** The skill runner
  calls `aggregator.snapshot()` in-process and never subscribes to
  `/openral/world_state_fast`, so `publish_rate_hz_fast` is an observability
  rate only.

A caveat worth recording, because it weakens an earlier claim: the live tip is
**intermittent**, not deterministic. Two walks measured during this work ran the
full 34 s and 5.5 m without tipping, while showing the same leftward drift
(`dy ≈ −1.3 m`) that precedes the failures. Roughly 3 tips in 5 live walks.

## What was changed as a result

`GO2_Z1_SPAWN_JOINT_TARGETS` spawns the arm at `ready` instead of the menagerie
`home`.

This matters because the locomotion skill emits **12-D leg-only rows**, and a
12-D row leaves the sticky arm hold untouched — on a fresh connect that hold is
the spawn pose. So a walk issued before any Recalibrate walks on the spawn pose,
and the old spawn was the one pose measured to fall. On the production path
(fresh connect, 12-D rows, no `reset_to_pose`), 5 trials × 10 s at honest mass:

| arm hold | survived | median distance |
|---|---|---|
| spawn = `ready` (as shipped) | 5/5 | 5.33 m |
| forced to `home` (the old spawn) | **0/5** | 0.56 m, tips at 0.70 s |

The fix makes the default agree with the procedure the live demo already
required by hand — Recalibrate, which parks at `ready`, *before* applying a gait
(`.agents/skills/go2-foxglove-view/SKILL.md`). Guarded by
`tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py`, which asserts both directions so
a change that makes every pose survive cannot pass silently.

The centred pose was deliberately **not** shipped: its only demonstrated effect
is a statics improvement and a 27 % tracking cost.

## Open

* **The mechanism.** What property of the arm configuration decides the
  first-second pitch-over is unknown. Neither centre-of-mass offset nor pitch
  inertia explains it.
* **`arm_mass_scale: 0.01` may be over-correcting.** In a clean 50 Hz headless
  loop, `ready` at *honest* mass survived 8/8 over 20 s and tracked 0.496 m/s.
  `robots/go2_z1/README.md` reports that full arm mass "tips that policy within
  a few metres"; that was observed on the live `deploy sim` graph, which adds
  ROS transport jitter and wall-clock idle stepping this loop does not have.
  Both observations can be true — but mass alone does not reproduce the tip, so
  what the workaround compensates for is not yet established. Re-measuring on
  the live graph is the next step, not raising the scale on the strength of this
  page.
* **The live mid-gait tip.** Still unexplained, and now with eleven eliminated
  explanations rather than nine: the two closed above join arm mass scale, arm
  pose, the velocity command, `last_action` reset, cadence jitter, systematic
  cadence shift, safety clamping, observation fallbacks, scene props, and floor
  geometry. The catalogue lives in
  `.agents/skills/go2-foxglove-view/SKILL.md`. Its intermittency means any
  future candidate needs a multi-trial live battery, not one rollout.
* **`fold`** ships as a selectable pose in
  `rskills/rskill-zero-go2_z1-arm_ready-fp32` while putting the arm in 5
  self-contacts.

## Reproduce

```bash
uv run python tools/go2_z1_mass_balance.py measure
uv run python tools/go2_z1_mass_balance.py measure --arm-mass-scale 0.01
uv run python tools/go2_z1_mass_balance.py search --steps 13 --top 15
uv run python tools/go2_z1_mass_balance.py walk --pose spawn --pose home --trials 8 --seconds 20
uv run python tools/go2_z1_mass_balance.py stale                # the freshness cliff
uv run python tools/go2_z1_mass_balance.py walk --json          # machine-readable
```

Needs the `sim` group (MuJoCo) plus onnxruntime and Hub access for `walk`.
