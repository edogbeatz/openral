---
type: concept
tags: [openral, deploy-sim, foxglove, dashboard, visualization]
updated: 2026-09-16
---

# Deploy-sim visualization

`openral deploy sim` can raise two complementary, **view-only** surfaces.
Neither actuates the robot.

| Surface | Flag / URL | Owns |
| --- | --- | --- |
| OTel dashboard | `--dashboard` → `http://127.0.0.1:4318` | Traces, metrics, reasoner/safety cards, latched safety state |
| Foxglove | `--foxglove` → `ws://127.0.0.1:8765` | Live 3D/2D scene (cameras, TF, URDF, map, voxels, ROS telemetry) |

Default is `--no-foxglove`. The hybrid is documented on
[[entities/openral-foxglove-bringup]] (`README.md`). Where the two
disagree, the dashboard is the one wired to `/openral/safety_status`.

## Viewer on a laptop, graph on a host

Port-forward `8765` (and `4318` if you want the dashboard). Open the web
client, or hand the same websocket to desktop Studio from the CLI:

```
https://app.foxglove.dev/?ds=foxglove-websocket&ds.url=ws://localhost:8765
open "foxglove://open?ds=foxglove-websocket&ds.url=ws://localhost:8765"
```

Import the **scene-matched** layout the deploy logs
(`/tmp/openral_layout_<robot>.json`, or a copy at repo root). In the
Layouts sidebar: **+ → Import from file**. On macOS file picker: `⌘⇧G`.
There is no layout-import CLI, and an already-imported layout keeps its
old camera state — re-import after every regenerate.

The browser will never load `file://` meshes through the websocket. The
URDF must stay on `package://` and the bridge must resolve those packages
via the ament overlay. See
[[analyses/foxglove-web-meshes-need-package-uri]].

## The 3D panel needs the right frame, floor, and up-axis

- **Display frame is the follow frame.** It must name a live TF frame:
  Go2's URDF root is `base`, not `base_link`, and a missing follow frame
  draws an empty panel rather than an error. Reset the camera with key `1`.
- **The floor is a viewer layer, not a topic.** A Foxglove **Grid**
  custom layer in frame **`world`** at z=0. Parenting it to `base` lifts
  the floor to chest height. The generated layout ships it.
- **RGB arrows are TF axes, not the robot.** Hide them with
  `scene.transforms.axisScale = 0` (3D settings → Transforms, a sibling
  of Scene, *not* inside it). Never disable `/tf` — that unposes the URDF.
- **Mesh up-axis** must be forced `z_up`, or COLLADA-authored robots lie
  on their back.

## Camera Image panels

The 3D panel is a third-person view of the URDF. An onboard camera
(`front`, `head`) is the robot's eyes: it looks *out*, so the body is
behind the lens and will not appear in that Image panel. Enabling
`/robot_description` in the Image panel's 3D overlay cannot fix that —
the mesh is outside the frustum.

Go2 therefore declares a viz-only `top` camera (menagerie `track` 3/4
pose, no `vla_feature_key`). The generated layout puts `top` first.
Re-import `/tmp/openral_layout_go2.json` after restarting
`deploy sim --foxglove`.

A blank gray rectangle on `front` is the empty staging floor, not zoom.
Staging is an infinite checker + gradient skybox
(`openral_hal._camera_rig`). Restart `deploy sim` so `*_camrig.xml` is
rewritten.

Scroll-wheel on a Foxglove Image panel *does* zoom; reset with the
panel's view-reset control if a real scene still looks cropped.

An Image panel also wants the paired `CameraInfo`, and refuses one whose
`header.frame_id` disagrees with the Image's. Both stamp the manifest
`SensorSpec.frame_id` — Go2 `front_camera`, never the slot name `front`.

## Freshness is measured on the host clock

The dashboard's connection pill is ingest age on the **dashboard host**
(`now_unix - last_ingest_ts` from the snapshot), not "is the page's
EventSource up" and not the browser's clock. A laptop viewing a
port-forwarded remote `:4318` is routinely ≥60 s off the VM, which used
to freeze the pill on `DEAD (1m)` while spans were still landing. The
same host-clock age drives every per-card status dot.

Live-graph liveness has its own traps —
[[analyses/proving-sim-motion-not-a-frozen-stand]].

## Operator runbook

CLI-first playbook for the Go2 graph on cricket (layout generator,
`foxglove://` open, in-place trot, health checks):
`.agents/skills/go2-foxglove-view/SKILL.md`. It carries host-specific and
fast-moving operational state; durable findings get promoted here.

Related: [[entities/openral-foxglove-bringup]], [[entities/go2]].
