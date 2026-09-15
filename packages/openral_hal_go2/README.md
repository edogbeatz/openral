# openral_hal_go2

ROS 2 lifecycle-node wrapper around `openral_hal.Go2MujocoHAL` so the
Unitree Go2 quadruped (12-DoF) can participate in the `openral deploy sim` graph
(`deploy_e2e.launch.py` → C++ safety kernel → HAL).

Spawned by `openral deploy sim --config scenes/deploy/go2_bench.yaml` via
`_ROBOT_HAL_REGISTRY["go2"]` (see
`python/cli/src/openral_cli/deploy_sim.py`).

The HAL is MuJoCo-backed. Sim-only spike: `hal.real` is null, so
`deploy run` raises `ROSCapabilityMismatch`. The bench scene sets
`gravity_enabled: false` so the floating-base twin holds the menagerie
`home` stand without a locomotion controller.
