---
type: analysis
tags: [openral, go2, z1, locomotion, rsl-rl, mass, centre-of-mass, sim, negative-result]
updated: 2026-09-17
linear: none
---

# Arm pose decides the Go2+Z1 walk — centre of mass does not explain it

Settled by measurement, with the mechanism **still open**. Normative numbers
live in `docs/reference/go2-z1-mass-balance.md`; the tool is
`tools/go2_z1_mass_balance.py`.

## The question

The Go2+Z1 carries a 4.69 kg Z1 (with jaw) 0.18 m forward and 0.06 m up on a
15.25 kg dog, driven by `rskill-rsl_rl_onnx-go2-velocity_flat` — trained on the
**bare** dog. The standing workaround is `arm_mass_scale: 0.01`. The intuitive
fix: park the arm so the composite centre of mass returns to where the bare
dog's was.

## What we believe now

**The arm pose determines whether the walk survives, and it is decisive.** At
honest arm mass, over randomised initial conditions, `ARM_READY` walks 9.9 m in
20 s (8/8 trials, 0.496 m/s against 0.5 commanded) and the menagerie `ARM_HOME`
pitches over in ~0.7 s (0/8). Same robot, same policy, same command — only the
arm pose differs.

**Centre-of-mass offset does not predict it.** Across eight collision-free poses
spanning 0.45–54.7 mm of offset, survival is scattered: the best-centred pose in
the set fell 0/6 and the worst-centred walked 6/6. A deliberately centred pose
(0.60 mm, vs 54.8 mm for `ARM_READY`) survives but tracks the velocity command
**27 % slower**. The four-foot support polygon was never the constraint either —
the nearest-edge margin is 114.86 mm for *every* pose and does not even move,
because the arm shifts the centre of mass along x while the nearest edge is a
side edge.

**Pitch inertia does not predict it either.** Interpolating `home → ready` gives
a clean monotone boundary that looks like an inertia threshold, but along that
line inertia and offset are collinear. Breaking the collinearity kills it: two
poses at `I_yy` 1.335 / 1.337 kg m² went 6/6 and 0/6, the highest-inertia pose
in the set went 0/6.

> ⚠️ The mechanism is unexplained. Failures pitch over inside the first second,
> before a steady gait establishes, and arm-vs-world contacts were zero in every
> rollout — so it is not the arm striking the body or the floor. Do not claim a
> pose helps locomotion on statics alone.

## What changed because of it

`GO2_Z1_SPAWN_JOINT_TARGETS` now spawns the arm at `ready`, not the menagerie
`home`. This matters because the locomotion skill emits **12-D leg-only rows**,
and a 12-D row leaves the sticky arm hold alone — on a fresh connect that hold
is the spawn pose. A gait applied before any Recalibrate therefore rode the old
spawn pose, the one measured to fall. On the production path (fresh connect,
12-D rows, no `reset_to_pose`): 5/5 upright and 5.33 m from `ready`, 0/5 and a
0.70 s fall when forced back to `home`.

The fix makes the code's default agree with the operating procedure the live
demo already required by hand — Recalibrate (which parks at `ready`) *before*
applying a gait. Guarded by `tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py`, which
asserts **both** directions so a change making every pose survive cannot pass
silently.

The centred pose was **not** shipped: statics gain, 27 % tracking cost, no
demonstrated locomotion benefit.

## Open

- **`arm_mass_scale: 0.01` may be over-correcting.** Headless at honest mass,
  `ready` survived 8/8 over 20 s. The claim that full arm mass "tips the walk
  skill within a few metres" came from the live `deploy sim` graph, which adds
  ROS jitter and wall-clock idle stepping the rollout lacks. Both can be true,
  but mass alone did not reproduce the tip — so what the workaround compensates
  for is not established. Re-measure on the live graph before changing it. The
  "ROS jitter" half of that guess has since been measured and is **not** it —
  see [[analyses/go2-proprio-freshness-cliff]].
- **`fold`** ships as a selectable pose in `rskill-zero-go2_z1-arm_ready-fp32`
  while putting the arm in 5 self-contacts at Hub stand.
- **One deterministic rollout per pose is an anecdote.** The first pass of this
  work drew the opposite conclusion from single rollouts; the batteries
  overturned it. Randomise initial conditions before believing a locomotion
  comparison.

Related: [[entities/go2-z1]], [[entities/go2]],
[[analyses/proving-sim-motion-not-a-frozen-stand]],
[[analyses/go2-proprio-freshness-cliff]] — the one property of this walk that
*does* have a sharp threshold, and the measurement excluding it from the live
tip.
