---
type: entity
tags: [openral, foxglove, visualization, ros2]
updated: 2026-09-16
---

# openral_foxglove_bringup

Read-only live Foxglove surface for an OpenRAL ROS graph. Package:
`packages/openral_foxglove_bringup/`. Normative usage and layout notes live
in that package's `README.md` and `VERIFICATION.md`.

Spawned by `openral deploy sim --foxglove` (default off). Standalone:
`ros2 launch openral_foxglove_bringup foxglove.launch.py`. Bridge binds
`127.0.0.1:8765`. Viewer: `ws://localhost:8765` (port-forward if the graph
is remote).

## What it is not

Not the observability backend. Traces, OTLP metrics, reasoner/safety cards,
and every write path stay on `openral dashboard` (see
[[concepts/deploy-sim-visualization]]). The bridge advertises
`connectionGraph` + `assets` only — no `clientPublish`, no services. Safety
and ACM topics are withheld. View-only.

## Robot meshes (web client)

Foxglove Studio — **browser and desktop** — only *requests* `package://`
meshes from `foxglove_bridge`. `file://` is read off the machine running
Studio, not through the websocket. Confirmed upstream:
[foxglove/ros-foxglove-bridge#264](https://github.com/foxglove/ros-foxglove-bridge/issues/264).

`robot_descriptions` URDFs (Go2 `go2_description`, others) stamp
`package://<name>/…` that is not an ament package on the ROS path. The
bridge then cannot serve the mesh; the 3D panel draws TF axes and a red `!`
on mesh-bearing links.

**Current belief:** leave the URDF on `package://`. Register each resolvable
share on a throwaway ament prefix (`/tmp/openral_foxglove_ament`) and set
`AMENT_PREFIX_PATH` on the **bridge process only**. Helpers:
`openral_foxglove_bringup.mesh_uris` —
`discover_package_mesh_roots`, `install_ament_mesh_overlay`,
`ament_prefix_with_overlay`, `prepare_foxglove_mesh_overlay`. Wired from
`deploy_e2e.launch.py` and `foxglove.launch.py`.

Rewriting `package://` → `file://` (`rewrite_package_mesh_uris`) does
**not** make the web client draw the robot. Desktop Studio on a laptop
also fails when those `file://` paths point at the deploy host.
`ASSET_URI_ALLOWLIST` admits `file://` too (same `..` refusal, same
extension set), but that is only a floor for older URDFs — Studio never
requests the scheme.

Expect: `registered N package:// mesh package(s) (go2_description) on the
Foxglove ament overlay`. Restart `deploy sim --foxglove` after picking up
the overlay; an already-running graph can still be publishing the old
`file://` URDF. **Confirmed working on cricket** — and a bridge that can
serve the meshes still shows nothing if Studio cached the earlier
failure, so reconnect or toggle `/robot_description`.

`docs/methods/14-duplication-watch.md` item 44 keeps this helper separate
from the two other mesh-URI rewriters (`_portable_mesh_refs` for
committed URDFs, `tools/viz_collision.py` for RViz). Three grammars, one
problem family — extend the Foxglove helper, don't import the others.

## Layout generator

`openral_foxglove_bringup.layout` writes the scene-matched JSON. Facts
that are in the file, not in the viewer's defaults:

- `scene.ignoreColladaUpAxis: true` + `meshUpAxis: "z_up"` on both 3D
  panels. `robot_descriptions` COLLADA is authored for RViz, which
  ignores `<up_axis>`; Foxglove honours it and lays the robot on its back.
- Each Image panel pairs `imageTopic` with `calibrationTopic`
  (`camera_info_topic`). The panel refuses a CameraInfo whose
  `header.frame_id` differs from the Image's, so both stamp the manifest
  `SensorSpec.frame_id` (`front_camera`), never the slot name
  (`_rgb_image_frame_id` in `openral_hal.sim_sensor_bridge`).
- `_order_layout_cameras` promotes a `top` slot to the first panel — an
  egocentric camera cannot show the body.

Full session write-up: [[analyses/foxglove-web-meshes-need-package-uri]].

Related: [[concepts/deploy-sim-visualization]], [[entities/go2]],
[[concepts/second-brain]].
