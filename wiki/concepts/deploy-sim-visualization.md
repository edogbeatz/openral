---
type: concept
tags: [openral, deploy-sim, foxglove, dashboard, visualization]
updated: 2026-09-17
---

# Deploy-sim visualization

`openral deploy sim` can raise two complementary surfaces. **Foxglove is
always view-only.** The OTel dashboard is view-only by default; with
`OPENRAL_DASHBOARD_WRITE_CONTROLS=1` it also exposes operator writes
(prompt, e-stop reset, and the Go2 **demo** bar — Bare Go2 auto-calibrates
after load then select skill + Apply; Go2+Z1 asks Recalibrate first;
**Start Cricket** / **End Cricket** plus 15 min idle auto-stop; laptop Start ``brev start``s + tunnels).

| Surface | Flag / URL | Owns |
| --- | --- | --- |
| OTel dashboard | `--dashboard` → `http://127.0.0.1:4318` | Traces, metrics, reasoner/safety cards, latched safety state; optional write-controls |
| Foxglove | `--foxglove` → `ws://127.0.0.1:8765` | Live 3D/2D scene (cameras, TF, URDF, map, voxels, ROS telemetry) |

Default is `--no-foxglove`. The hybrid is documented on
[[entities/openral-foxglove-bringup]] (`README.md`). Where the two
disagree, the dashboard is the one wired to `/openral/safety_status`.

## Demo bar (Go2 ↔ Go2+Z1)

Write-controls wizard:

1. **Bare Go2** — cold-reload that twin; the page auto-stands once
   `/healthz` is back (no auto-walk) and lands on **select skill + Apply**
2. **Go2 + Z1** — cold-reload; Recalibrate is the required next step
   (confirm on click). Recalibrate parks the Z1 at arm-ready **and** the
   running HAL must sticky-hold that pose (`_arm_hold_pose`); a 200
   without those files still leaves the arm waving. Walk qpos-snaps
   that pose so the arm stays fixed. After Recalibrate, pick a skill
   and Apply. Walk is the default: Recalibrate must **force** the rsl-rl
   walk id even if `arm_ready` is currently selected (not only skip
   restoring a saved hold). That 2 s Hub hold is why Apply looked frozen.
   Arm-ready stays on the picker for an explicit retarget. Do not Apply
   walk until Recalibrate actually landed upright + ARM_READY
   (`(0, 1.2, −1.0, −0.4, 0, 0)` on joints 1–6). Hard-refresh
   `dashboard.js?v=walk1`. Go2+Z1 walk can tip mid-gait in ~8 s; **Stop**
   before 60 s and Recalibrate if down.
3. **Drive** — **Stop** cancels the in-flight `ExecuteRskill` (no e-stop
   latch) and snaps Hub stand so Apply can run again. Stand is tip recovery
   *while the skill still runs*. Recalibrate stays available if they tip.
   **Start Cricket** from a **laptop** dashboard runs `brev start` if the
   instance is stopped, `docker start`s `openral-jazzy-go2`, opens SSH
   tunnels (Foxglove `ws://127.0.0.1:8765` and cricket's own dashboard at
   `http://127.0.0.1:14318/` so this process can keep `:4318`), and
   attaches `openral deploy sim --dashboard --foxglove` if the graph is
   down. If the graph is already up, Start only ensures tunnels and
   reports already-running — it does not tear down. **Start Cricket**
   from a dashboard **on cricket** still only starts the graph (the box
   is already up). **End Cricket** cancels the skill, stops the graph,
   then `brev stop` / host halt so GPU spend stops — not E-STOP, and not
   Stop (Stop keeps the sim). From a laptop, End still `brev stop`s.
   Idle with no operator action and no running skill auto-Ends after 15 min
   (`OPENRAL_CRICKET_IDLE_S`; the bar shows `auto-stop in mm:ss`).
   **E-STOP** (command band) latches the kernel. Picking the other robot
   confirms. Nothing auto-applies. The separate Run strip is hidden while
   this bar is shown.

Deploy exports `OPENRAL_ROBOT_ID`. See [[entities/go2-z1]].

Cold-reload writes `/tmp/openral_demo_relaunch.sh` and kills by
character-class `pgrep` (`[o]penral deploy sim`). A `bash -c` body plus
`pkill -f 'openral deploy sim'` matches the killer's own argv, so the
new deploy never starts and the UI hits "reload timed out". The page
polls `/healthz` for up to 180 s and waits for a down-gap so a surviving
old dashboard is not treated as the new twin. The launcher sources Jazzy
+ the workspace overlay; a cold `docker exec` without that source fails
with `ros2 not found on PATH`. `ulimit -c 0` is set because a HAL
SIGSEGV on shutdown has dumped multi-GB cores and filled the host root
disk (`docker exec` then fails with `no space left on device`).

## Viewer on a laptop, graph on a host

**Start Cricket** on the laptop dashboard (`http://127.0.0.1:4318`) opens
the tunnels. Foxglove is `ws://127.0.0.1:8765`. Cricket's own dashboard
(live tiles + write-controls) is tunneled to `http://127.0.0.1:14318/`
because this laptop process already owns `:4318`. Open the web client, or
hand the same websocket to desktop Studio from the CLI:

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

`openral deploy sim --foxglove` republishes each RGB topic as
`/compressed` and the generated layout points the Image panels there.
Raw 640×480 RGB8 is ~9 MB/s per camera; two Go2 cams over a laptop
SSH tunnel saturated Foxglove's 10 MB send buffer and the video
stuttered. Re-import `/tmp/openral_layout_<robot>.json` after this
change — an already-imported layout keeps the raw topic. The live Mac
Studio `openral_layout_go2` was rewritten 2026-09-17 to `top` then
`front` `/compressed`.

Dashboard tiles are MJPEG of OTLP JPEGs, not the ROS topic. The HAL
used to emit those JPEGs at 1 Hz (leftover from still-card polling);
they now track the camera timer, capped at 25 Hz. The EventSource no
longer re-ships the JPEG on every telemetry tick.

The laptop `:4318` page **always** shows two camera panels, even while
WAITING / Loading Bare Go2 / no OTLP: **Main · `front`** (snout — empty
checkerboard + black sky is a healthy empty world, not a dead feed)
and **Side · `top`** (3/4 view of the dog — the HAL key is `top`, not
an invented `side`). They used to stay `hidden` until the first
`sensors.read_latest` span, which is why a WAITING screenshot was an
empty grid. The `<img>` src is `/api/camera/{front,top}/stream` from
first paint. An opaque `waiting for camera` placeholder used to sit on
top until `img.onload`; multipart MJPEG often never fires that, so the
tiles looked blank while the streams were live. Tiles now start
`is-streaming`, CSS hides the placeholder as soon as `img[src]` is
set, and telemetry `hasFrame` re-adds the class. When this process has
no local thumbs (laptop collector) it proxies cricket's tunneled
dashboard MJPEG at
`http://127.0.0.1:14318/api/camera/{front,top}/stream`. Direct proof
URLs on a cricket tunnel: `http://127.0.0.1:4318/api/camera/top/stream`
(dog) and `…/front/stream` (snout). That is not live ROS video — it is
the same ~25 Hz OTLP JPEG MJPEG Foxglove's `/compressed` Image panels
beat.

## Freshness is measured on the host clock

The dashboard's connection pill is ingest age on the **dashboard host**
(`now_unix - last_ingest_ts` from the snapshot), not "is the page's
EventSource up" and not the browser's clock. A laptop viewing a
port-forwarded remote `:4318` is routinely ≥60 s off the VM, which used
to freeze the pill on `DEAD (1m)` while spans were still landing. The
same host-clock age drives every per-card status dot.

## Command-band counters are session totals

The four (five with skill-failures) numbers next to the prompt are
**session totals** on the dashboard process. They do not reset on
**Recalibrate**, **Stand**, or **Reset e-stop**. Recalibrate / Stand
clear a latched kernel (`/openral/estop_reset`) and snap Hub home; they
do not wipe the tally. A new `deploy sim` (or a Bare Go2 / Go2+Z1
cold-reload that actually restarts uvicorn) is what zeroes them.

| Counter | Counts | Colour when >0 |
| --- | --- | --- |
| safety violations | kernel `safety.check` with severity `violation` (self-collision, workspace, …) | red |
| e-stops | each `/openral/estop` the HAL actually latched (`openral.event.estop_requested`) | red |
| deadline misses | a skill hit `max_execution_s` (`openral.event.deadline_missed`) | yellow |
| sensor-stale | a sensor older than its age budget | yellow |

An **external** e-stop is not a safety violation. The rsl-rl Go2 walk
resolves a missing action deadline to the manifest **60 s**; one yellow
after a minute of trot is the skill ending on budget, not a tick overrun.
That end does **not** stand the dog up: idle PD-holds the last gait
waypoint with gravity on, so a freeze mid-stride (or an already-tipped
policy) falls. Kernel stays unlatched. **Stand** / **Recalibrate** snaps
Hub home. See [[entities/go2]].
Red e-stops with `safety violations = 0` means someone hit **E-STOP** (or
another `/openral/estop` publisher), not that the kernel collided.

The latch (robot frozen) is independent of the tally. After an e-stop
the button flips to **Reset e-stop**; click that first, then
**Recalibrate**, then Apply. Recalibrate while still latched will try
the same reset, but the red number stays.

## Event log: locomotion is debug, not empty

Headline `info` rows are an allow-list (`deploy.bringup`, `reasoner.tick`,
…). A Go2 walk has no reasoner, so every live span
(`rskill.execute`, `hal.read_state`, `sensors.read_latest`,
`safety.check`) lands in `debug`. The Debug chip stays **off** so 30 Hz
cannot cycle the 60-row pane. While it is off the UI still paints **one
live row per stream** (cameras keyed by `openral.sensors.source`). Toggle
Debug for the full per-tick flood. Do not promote `rskill.execute` to
headline — `rSkillBase.step()` emits it every tick.

Live-graph liveness has its own traps —
[[analyses/proving-sim-motion-not-a-frozen-stand]].

## Operator runbook

CLI-first playbook for the Go2 graph on cricket (layout generator,
`foxglove://` open, in-place trot, health checks, **start failures**):
`.agents/skills/go2-foxglove-view/SKILL.md`. It carries host-specific and
fast-moving operational state; durable findings get promoted here.
**Every start failure** (WAITING, command not found, tunnel conflict,
occupancy, Recalibrate 200/arm flails, idle auto-stop, dashboard crash,
Start Cricket no-op) is appended to that skill in the same turn — do
not leave it only in chat.

Laptop `openral dashboard` (`uv run` after `just sync`; bare `openral`
is often not on PATH) is an **empty collector**: header WAITING, no
robot, no cameras. The live twin is cricket
(`abundant-turquoise-cricket` / `openral-jazzy-go2` / domain 77)
`deploy sim --dashboard --foxglove` with write-controls on. If the
laptop collector owns `:4318`, stop **only** that process and tunnel
cricket's `:4318` (`ControlMaster=no`) plus Foxglove `:8765`; operator
URL is then `http://127.0.0.1:4318/`. Do not `pkill` a sibling's graph
or steal tunnels to "fix" WAITING.

Related: [[entities/openral-foxglove-bringup]], [[entities/go2]].
