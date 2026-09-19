---
type: analysis
tags: [openral, go2, z1, rsl-rl, mjlab, acquire, finetune]
updated: 2026-09-19
---

# Payload-aware Go2+Z1 walk is mjlab resume, not Adapt

Settled 2026-09-19 from how `/simple` **move** actually lands on
[[entities/go2-z1]], then what a real adapt would take. Envelope /
remap: [[analyses/wrapping-third-party-weights]]. Arm pose (not CoM)
already decides whether the *same* net stays up:
[[analyses/go2-z1-arm-pose-decides-the-walk]]. Train vs run:
[[analyses/isaac-lab-with-openral]]. Product: [[entities/acquire]].

## What Adapt does today

Dashboard SKILL label **move** is
`Acquire/rskill-rsl-rl-onnx-go2-velocity-flat` — the Hub 12-D rsl-rl
ONNX. Chat still parses `walk` / `forward`, not the word `move`.

On bare [[entities/go2]] Acquire says **fit**. On Go2+Z1 the seed is
tagged `go2` only, so the first probe (`allow_adapt: false`) rejects
on embodiment and chat asks **Adapt it?**. Yes sends `adapt: "remap"`.
That forks the card (`fork/…→go2_z1`), `rules_applied: [tag_family]`,
`remapped_contracts: {}`. Apply still runs the **same** 12-D ONNX.
OpenRAL hold-pads 12→19 and `Go2Z1MujocoHAL` qpos-snaps the sticky
`ready` arm. The in-tree manifest already lists both tags — the ask
is the demo.

Hop never becomes an offer (`check=payload`, 4.69 kg vs 0 kg budget).
A live mid-gait tip on this twin is the verify miss: `/simple` chats
**the unit fell. this skill needs retraining or finetuning.** (1.0 rad
gate, once until RESET). That line points here — not at Adapt.

## What Adapt does not do

It does not retune `action_scale`, `default_joint_pos`, observation
dim, PD gains, or `velocity_commands`. Sibling `adapt.py` *can*
rewrite IO tables on other families (camera aliases, joint order,
gripper scale). This pair is tag-only.

Changing CoM / `arm_mass_scale` / pitch inertia does not make the
bare-dog net a payload policy. Arm **pose** does (ready walks, home
tips) — that is a hold, not a learned gait.

## What finetune actually is

Still **12-D legs**. The Z1 stays frozen. What changes is the **train
physics**: honest arm mass in the loop so the actor learns to carry
4.69 kg. Not a 19-D policy. Not Acquire remap. Not a dashboard click.

Cannot finetune `policy.onnx`. Resume
`model_500.pt` from `diasAiMaster/unitree-go2-velocity-flat`. OpenRAL
is not the PPO farm. Acquire stays `adapt ≠ train`
([[analyses/creating-acquire]]). Sibling playbook:
`edogbeatz/robo-skill-acquire` `docs/finetune-playbook.md`.

## Recipe (outside this repo)

1. Check out [unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab).
2. Bolt Z1 onto the Go2 train MJCF (honest mass, arm held at `ready`).
3. Resume the parent task at a lower LR:

```bash
python scripts/train.py Mjlab-Velocity-Flat-Unitree-Go2 \
  --agent.resume=True \
  --agent.load-checkpoint=model_500.pt \
  --agent.algorithm.learning-rate=1e-4
```

4. Take the exported `policy.onnx` + `params/deploy.yaml`.
5. Wrap as a **new** `skill_id` (not `fork/…`). Acquire Lane B:
   `adapt: false`, `verify: true`, scene `go2_z1_walk`. Then `/simple`
   Apply can point at that card.

Parent train was ~500 PPO iters / 8192 envs / ~18 min on 10× A4000.
A payload resume is shorter than from-scratch. Still a GPU job.

## Do not wrap m3 as a drop-in

[`m3/go2z1-walking-rsl-rl-v1`](https://huggingface.co/m3/go2z1-walking-rsl-rl-v1)
is Isaac Lab PPO on an 18-DoF Go2+Z1 (12 leg deltas). Obs includes
`lin_vel`; Hub walk is 45-D **without** it. V2 is `.pt` only (no
ONNX). They fold the arm (`startFlat`), which tips this twin
([[analyses/go2-z1-arm-pose-decides-the-walk]]). Closest public
composite walk, not a `rsl_rl_onnx` drop-in. U-turn context:
[[analyses/no-uturn-rskill]].

Related: [[entities/go2]], [[entities/go2-z1]],
[[analyses/wrapping-third-party-weights]].
