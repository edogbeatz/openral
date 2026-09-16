---
type: analysis
tags: [openral, foxglove, go2, urdf, meshes, deploy-sim]
updated: 2026-09-16
---

# Foxglove web meshes need package:// + ament overlay

Settled 2026-09-16 from a live Go2 `openral deploy sim --dashboard --foxglove`
on cricket (`ROS_DOMAIN_ID=77`) with the viewer on a Mac. Home pages:
[[entities/openral-foxglove-bringup]], [[concepts/deploy-sim-visualization]].

## What was on the wire (cricket)

- Image + CameraInfo both stamp `frame_id=front_camera` (manifest TF frame in
  `robots/go2/robot.yaml`, not sensor name `front`). 640×480 rgb8, real
  pixels. That stamp lives in
  `python/hal/src/openral_hal/sim_sensor_bridge.py` (`_rgb_image_frame_id`)
  and is a **separate** change from the mesh overlay.
- `/robot_description` had 17 `file://` meshes after an earlier
  `rewrite_package_mesh_uris` pass. TF tree live; 42 URDF links parse in
  Foxglove.

## What the Mac viewer did

- `ws://localhost:8765` port-forwarded into
  `https://app.foxglove.dev/?ds=foxglove-websocket&ds.url=ws://localhost:8765`.
- Layout: `/tmp/openral_layout_go2.json` (or repo-root
  `openral_layout_go2.json`) via Layouts → + → Import from file. macOS
  picker: `⌘⇧G`.
- 3D panel: TF axes only. `/robot_description` enabled. Red `!` on
  mesh-bearing links (`base`, `FL_hip`, …). Rotor / primitive links clean.
- Foxglove Studio (web **and** desktop) only *requests* `package://` from
  `foxglove_bridge`. `file://` is desktop-local — read off the machine
  running Studio. Upstream:
  [foxglove/ros-foxglove-bridge#264](https://github.com/foxglove/ros-foxglove-bridge/issues/264)
  (“Foxglove Studio currently only requests package:// URL meshes from
  foxglove bridge.”).
- Downloading Foxglove desktop on the Mac does **not** load the quadruped:
  those `file://` paths are cricket (`/home/ubuntu/…`), not this disk.
- The browser will never load `file://` meshes through the websocket.

## What we believe now

Rewriting `package://` → `file://` is the wrong fix for a remote / web
viewer. Keep the URDF on `package://`. Register each resolvable
`robot_descriptions` package on a throwaway ament prefix and hand
`AMENT_PREFIX_PATH` to **foxglove_bridge only**.

Local working tree (uncommitted as of this filing; do not revert):

- `packages/openral_foxglove_bringup/openral_foxglove_bringup/mesh_uris.py`
  — `discover_package_mesh_roots`, `install_ament_mesh_overlay`,
  `ament_prefix_with_overlay`, `prepare_foxglove_mesh_overlay`. Default
  overlay `/tmp/openral_foxglove_ament`.
- `packages/openral_rskill_ros/launch/deploy_e2e.launch.py` reads the URDF
  unchanged and sets `additional_env` on the bridge.
- `packages/openral_foxglove_bringup/launch/foxglove.launch.py` does the
  same via `SetEnvironmentVariable` when a URDF path is given.
- Docs: package `README.md`, `VERIFICATION.md`,
  `docs/methods/11-ros2-nodes.md`, `docs/methods/14-duplication-watch.md`
  item 44.

Safety / ACM left alone.

`ASSET_URI_ALLOWLIST` in `topics.py` now also admits `file://` (same
traversal refusal, same extension set) so an older `file://` URDF is at
least servable. That is a compatibility floor, **not** the fix: Studio
still does not ask for `file://`.

## Confirmed on cricket (same day, after the overlay landed)

The overlay works. `foxglove_bridge`'s `AMENT_PREFIX_PATH` starts with
`/tmp/openral_foxglove_ament`, the DAEs are on disk, and
`/robot_description` carries 17 `package://go2_description/dae/*.dae`
visuals with zero `file://`. A restart of `deploy sim --foxglove` is
required to stop republishing the old URDF.

Two things still stood between that and a visible dog.

**1. Studio caches the failure.** The bridge process serving the working
overlay logged **zero** asset fetches, while an earlier pid had logged
`Package [go2_description] does not exist`. Studio kept showing the old
result and a red `!` on `/robot_description` ("12 links have errors").
Reconnect the websocket, or toggle `/robot_description` off and on, so
Studio retries. A red `!` is a fetch/link error — it is not the TF axis
control, and not the overlay.

**2. COLLADA up-axis.** `go2_description` DAEs are authored for RViz,
which ignores `<up_axis>`. Foxglove honours it and draws the quadruped on
its back. The generated layout now sets
`scene.ignoreColladaUpAxis: true` and `scene.meshUpAxis: "z_up"` on both
3D panels (`layout.py`), matching RViz.

Not every link has a mesh: `Head_upper` / `Head_lower` are
collision-only (no snout geometry) and 12 inertial rotor links have no
geometry at all. Those are expected, not failures.

## How to see the quadruped

1. `app.foxglove.dev` or desktop → the forwarded websocket → import the
   Go2 layout (re-import after every regenerate: camera orbit, axis
   scale, and the floor layer live in the JSON).
2. 3D **Display frame** must be `base`, the Go2 URDF root.
3. Expect the bridge log line:
   `registered N package:// mesh package(s) (go2_description) on the Foxglove ament overlay`.
4. Dashboard still `http://127.0.0.1:4318`. View-only.

Related: [[entities/openral-foxglove-bringup]],
[[concepts/deploy-sim-visualization]], [[entities/go2]],
[[analyses/proving-sim-motion-not-a-frozen-stand]].
