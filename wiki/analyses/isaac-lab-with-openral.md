---
type: analysis
tags: [openral, acquire, isaac, go2, sim]
updated: 2026-09-19
---

# Isaac Lab with OpenRAL — feasible paths

Answer for Acquire / hackathon: **yes, but not as a drop-in MuJoCo
replace for Go2 this week.** Three layers, only the first is MVP-ready.

## 1. Isaac Lab as the *training* source (current path)

`rsl_rl_onnx` skills are Isaac Lab / Unitree rsl-rl policies, exported
to ONNX, run in-process ONNX Runtime against the OpenRAL HAL. First
customer: `diasAiMaster/unitree-go2-velocity-flat` on
[[entities/go2]] / [[entities/go2-z1]] (12→19 hold-pad). Verify physics
is MuJoCo (`go2_walk` / `go2_z1_walk`). That is already how locomotion
lands in this fork.

Hackathon MVP should keep this split: that family trains outside
OpenRAL, OpenRAL warrants on the named MuJoCo scene.

**You do not need Isaac Gym and Isaac Lab together.** Gym Preview is
the old NVIDIA train stack (unitree_rl_gym-era). Isaac Lab replaced it.
This Hub walk was trained with Unitree **mjlab**
(`unitree_rl_mjlab`, task `Mjlab-Velocity-Flat-Unitree-Go2`) — Lab-shaped
rsl-rl on **MuJoCo**, then exported ONNX. Future loco of the same
family: pick **one** recipe (mjlab *or* Isaac Lab + Isaac Sim). Gym is
only if you replay an old Gym checkpoint. SO-101 / SmolVLA train is
LeRobot teleop, not Isaac. Acquire still does not own the farm
([[analyses/creating-acquire]]). If that farm happens later: quadruped
rsl-rl → Isaac Lab **or** mjlab (not Gym+Lab, not OpenRAL-as-trainer).
Arm/VLA → LeRobot. The OpenRAL Lab sidecar is for **running** a PhysX
twin, not for PPO.

## 2. Isaac Sim sidecar (exists, not a Go2 Lab env)

`openral_sim.backends.isaac_sim` drives an out-of-process py3.11
sidecar (`tools/isaac_sidecar.py`). Workspace is py3.12; Isaac Sim
wheels are per-interpreter; Kit + VLA torch cannot share a process.
Scenes today are Isaac Sim **core** (PhysX + RTX), not Isaac Lab
manager-based envs — the PyPI `isaaclab` wheel omits
`isaaclab.sim` / `isaaclab.envs` (need git-source + `isaaclab_assets` /
`isaaclab_tasks`). Layouts: Franka `lift_cube` / `bowl_plate`, plus
robot-agnostic `manifest` URDF import. Normative:
`docs/methods/07-eval-sim.md`.

A Go2 PhysX twin *could* ride `manifest` (URDF already in
`robots/go2/`), but that is not the Isaac Lab velocity-flat MDP the
ONNX was trained in. Do not claim Sim-to-Lab parity.

## 3. Full Isaac Lab manager env (ask OpenRAL, not the hackathon critical path)

Would need a git-source Isaac Lab sidecar scene whose obs/action terms
match `params/deploy.yaml` (history, scales, `velocity_commands`).
Adrian offered to look at Lab support. Useful after MVP, or if it
lands before demo day. Eurekaverse parkour / privileged-teacher jump
was already scoped out of the NVIDIA embodiment demo.

## Honesty

- OpenRAL does **not** currently swap `PhysicsBackend.mujoco` → Isaac
  Lab for Go2 deploy-sim.
- Weight licenses stay with the Hub checkpoint (BSD-3-Clause for the
  first Go2 loco); Acquire remap is embodiment-contract, not a new
  weight family.
- Product layer is [[entities/acquire]]; this repo is the runtime
  substrate ([[analyses/creating-acquire]]).
- A payload-aware Go2+Z1 walk is **mjlab resume** of
  `model_500.pt` with Z1 in the train MJCF, then a new rSkill — not
  Acquire remap, not ONNX finetune
  ([[analyses/go2-z1-payload-walk-finetune]]).
