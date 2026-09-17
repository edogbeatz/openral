# `go2_z1` — Robot description

Canonical `RobotDescription` for the **Unitree Go2 + Z1** composite —
a 19-DoF sim-only mobile manipulator (12 Go2 legs + 6 Z1 arm joints +
jaw). The arm is part of this robot, not scenery: MJCF composition lives
under `scene_defaults.composition` →
`openral_sim.scene_composers:compose_mounted_arm_mjcf`.

## Why the joint order matters

Legs occupy indices **0–11**, byte-identical to [`robots/go2`](../go2/).
The Z1 follows. That is why the same 12-DoF rsl-rl locomotion skill
(`OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32`) runs on both bare
Go2 and this composite: the runner hold-pads the arm from proprio, and
`Go2Z1MujocoHAL.send_action` accepts a 12-D row as defense in depth.
A 19-D row is an explicit arm command (see
`rskills/rskill-zero-go2_z1-arm_ready-fp32`).

Embodiment tags include `go2` so the skill capability gate intersects.

## Locomotion vs arm mass

The shared rsl-rl Go2 velocity skill was trained on the bare dog. Full Z1
menagerie mass (~4.4 kg high on the torso) tips that policy within a few
metres even with the arm frozen at home. `arm_mass_scale: 0.01` on
`scene_defaults.composition` keeps meshes and joint kinematics, shrinks
arm inertias for walk demos. Set `1.0` when you want honest payload
dynamics (and expect a tip unless the skill is retrained). Recalibrate
parks the arm at `GO2_Z1_ARM_READY`; the HAL qpos-snaps that sticky hold
on every locomotion chunk and idle tick so gait cannot wave the Z1.

## Deploy

Gravity-on walk bench (arm held at Recalibrate / arm-ready while the dog walks):

```bash
openral deploy sim --config scenes/deploy/go2_z1_walk.yaml --dashboard --foxglove
ros2 action send_goal /openral/execute_rskill openral_msgs/action/ExecuteRskill \
  "{rskill_id: 'OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32', \
    goal_params_json: '{\"velocity_commands\": [0.5, 0.0, 0.0]}', \
    deadline_s: 30.0}"
```

Side-by-side with bare Go2: `scenes/deploy/go2_walk.yaml` + the same
`rskill_id`.

Park the Z1 (turns the position servos on; default pose is `ready`):

```bash
ros2 action send_goal /openral/execute_rskill openral_msgs/action/ExecuteRskill \
  "{rskill_id: 'OpenRAL/rskill-zero-go2_z1-arm_ready-fp32', \
    goal_params_json: '{\"pose\": \"ready\"}', \
    deadline_s: 10.0}"
```

`hal.real` is null — sim only. Real Unitree mounts the Z1 on a B1, not a
Go2; this is a sim study.

## Control split

| Joints | Actuators | Drive |
|--------|-----------|--------|
| Legs 0–11 | torque `<motor>` | software PD (`Go2MujocoHAL` law) |
| Arm + jaw 12–18 | position servos | ctrl = radians target |

See `openral_hal.go2_z1.Go2Z1MujocoHAL` and
`tests/sim/test_go2_z1_hal_mujoco.py`.
