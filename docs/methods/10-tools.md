# Tools

> Part of the OpenRAL [public-symbol inventory](../METHODS.md). Hand-curated; `(LNN)` markers are refreshed by `tools/refresh_methods_linenos.py`.

### `tools/lifecycle_autostart.py`
_Drives a lifecycle node through `configure` → `activate` after `ros2 launch` brings it up. Spawned as an `ExecuteProcess` per node by `packages/openral_rskill_ros/launch/deploy_e2e.launch.py` (HAL, safety kernel, reasoner)._

- `--transition-timeout-s` — per-transition spin budget, **default `300.0`** (`lifecycle_autostart.py:161`). The kernel gets a 120 s literal and the reasoner 300 s; the **HAL's is derived per scene** by `openral_hal.sim_bringup.hal_transition_timeout_s` (`deploy_e2e.launch.py`), not hardcoded. There is still no `openral deploy sim` flag — raise the scene's `backend_options.boot_timeout_s` instead and the lifecycle budget follows.
- `_skip_transition(current, transition_id) -> bool` — True when `current` already satisfies `transition_id` (already `active`, or already `inactive` when the request is CONFIGURE). Re-read immediately before each `change_state`: a racing activator (launch_ros LifecycleEventManager + this script) can land ACTIVE between polls. Sending `TRANSITION_ACTIVATE` (id 3) again on Jazzy raises `RCLError` inside the target node and kills it (go2_bench cricket: reasoner `on_activate: ticking` then exit 1). (L40)
