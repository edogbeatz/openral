---
type: analysis
tags: [openral, go2, deploy-sim, safety, verification, ros2]
updated: 2026-09-16
---

# Proving sim motion, not a frozen stand

Settled 2026-09-16 while driving an in-place trot on the live Go2 graph
(cricket, `ROS_DOMAIN_ID=77`, gravity off, no walking rSkill). Home
pages: [[entities/go2]], [[concepts/deploy-sim-visualization]].

The question "did the robot actually move?" turned out to have four
plausible-but-wrong answers on the wire. This page records which signal
is ground truth and which ones lie.

## Ground truth is the joint span

Sample `/joint_states` for the whole command window and measure the
travel of one leg joint. `.agents/skills/go2-foxglove-view/scripts/march.sh`
prints `FL_thigh_span` and warns under 0.05 rad. A verified trot read
**0.404 rad over 312 samples**; a frozen Hub stand reads ~0.

## What does not prove motion

- **A published action chunk.** Commands go out on
  `/openral/candidate_action` and the kernel forwarded 25 chunks to
  `/openral/safe_action`, yet **`/openral/action_applied` published
  nothing at all** while the dog was trotting. It is not a liveness
  signal. (Never publish `safe_action` by hand — that bypasses the
  kernel.)
- **`ros2 node list` / `ros2 lifecycle get`.** Against a stale ros2cli
  daemon these return empty or `Node not found` while `ros2 topic echo`
  on the same graph works fine. An empty node list is evidence about the
  daemon, not the graph.
- **A latched-safety guess.** Read it: the kernel reported
  `latched: false`, `detail: kernel activated`. The dashboard is the
  surface wired to `/openral/safety_status`.

## Two harness traps that fake a clean run

**`docker exec` without `-i` silently drops a heredoc.** `bash -s` gets
EOF, the entire block is skipped, and the script still **exits 0** in
about five seconds with no output. A green exit code with no stdout is
the signature. `march.sh` now passes `-i` and reads `/joint_states` back
in-process.

**Backgrounding the driver kills it early.** Run `march.sh` in the
foreground: backgrounded, it dies with the shell before its 15 s window
elapses, and a sampler run afterwards reads a frozen Hub stand — which
reads as "the safety kernel is eating my actions" when nothing ever
commanded anything.

> ⚠️ Both failures are silent and both look like a healthy run. Treat any
> remote-exec verification that produced no output as unproven, not as
> passing.

## Why the stand looks frozen even when it is correct

Go2 runs torque actuators, so idle ticks must PD-hold the last target
(`Go2MujocoHAL.idle_step`). That hold is *supposed* to be motionless.
Distinguishing "correctly holding" from "never commanded" is exactly what
the joint-span check is for — see [[entities/go2]].

Related: [[entities/go2]], [[concepts/deploy-sim-visualization]],
[[analyses/foxglove-web-meshes-need-package-uri]].
