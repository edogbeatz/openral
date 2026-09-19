---
type: concept
tags: [openral, deploy-sim, foxglove, dashboard, visualization]
updated: 2026-09-19
---

# Deploy-sim visualization

`openral deploy sim` can raise two complementary surfaces. **Foxglove is
always view-only.** The OTel dashboard is view-only by default; with
`OPENRAL_DASHBOARD_WRITE_CONTROLS=1` it also exposes operator writes
on **`GET /`** (the simple dashboard; classic `/` HTML is retired).
Laptop idle auto-End is 15 min; cricket attach/reload sets
`OPENRAL_CRICKET_IDLE_S=0` so the in-graph collector does not End the
twin. Laptop Start ``brev start``s + tunnels.

## Agents: start the app when asked

When the operator says **start the app**, **start the dashboard**,
**start cricket**, or **open `/simple`**: run it this turn. Do not
paste the command and wait. Canonical:

```bash
.agents/skills/go2-foxglove-view/scripts/start-app.sh
```

That reuses `http://127.0.0.1:4318/healthz` if live, else `just
dashboard` from repo root (write-controls), then
`POST /api/demo/cricket/start` (already-running is success), then
opens `/simple`. Normative steps:
[`docs/quickstart/dashboard.md`](../../docs/quickstart/dashboard.md).
Playbook: `.agents/skills/go2-foxglove-view/SKILL.md`. Do not steal
tunnels; do not `pkill` the graph.

| Surface | Flag / URL | Owns |
| --- | --- | --- |
| Operator dashboard | `--dashboard` → `http://127.0.0.1:4318/simple` (`GET /` 307) | Start engine → UNIT (auto-stand after load) → empty SKILL until chat Acquire propose → `#chat-apply` (APPLYING… when stood; STANDING… only if not; STOP while running). Footer RESET is Recalibrate. Classic root UI is not started. Cricket's in-graph collector uses `OPENRAL_CRICKET_IDLE_S=0` so only the laptop page auto-Ends. |
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
   and Apply. Walk is the default after Recalibrate only when the pick
   is empty or `arm_ready`; hop stays hop. That 2 s Hub hold is why Apply
   looked frozen when arm_ready was restored. Arm-ready stays on the
   picker for an explicit retarget on Go2+Z1. Do not Apply
   walk until Recalibrate actually landed upright + ARM_READY
   (`(0, 1.2, −1.0, −0.4, 0, 0)` on joints 1–6). Hard-refresh
   `dashboard.js?v=walk1`. Go2+Z1 walk can tip mid-gait in ~8 s; **Stop**
   before 60 s and Recalibrate if down.
3. **Drive** — Apply while a skill is already running **stops it first**
   (cancel, no e-stop, Hub stand) then dispatches the new pick. Reusing
   the GPU-resident skill without an episode reset used to leave the
   previous `last_action` / horizon in place, so a second walk stood
   still. **Stop** still cancels without e-stop and snaps Hub stand.
   Stand is tip recovery *while the skill still runs*. Recalibrate stays
   available if they tip.
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

## Simple dashboard (`/simple`)

A separate Next.js 16 + shadcn New York page at `GET /simple` (header
link on `/`), built from `python/observability/simple_ui/` (Zappi's
stack: React 19, Tailwind v4, Geist, `Button` / `Badge` / `Card`;
industrial HMI chrome — square buttons, camera inner ticks, `//` labels, no corner radii).
**Start engine** (`POST /api/demo/cricket/start`) paints **Starting…**
before any await (same idle heading; reserved button + status slots so
the column does not jump). Live steps put a full-width OP_CAL + conn row
(`justify-between`). Header primary is Start / Load / Stop only —
Calibrate / Apply are not the top CTA. Load auto-stands
(`POST /api/demo/recalibrate`) so Apply is ready. Footer **RESET** is
the same Recalibrate (tip recovery). Chat owns Apply. Then UNIT + SKILL
dropdowns above a full-width **top** tile, then LIVE.
Empty / no live twin is **Load the unit** (heading, UNIT placeholder,
disabled primary) — never a pretent Bare Go2 pick. A live or loading
twin labels **Bare Go2** or **Go2 + Z1** from cricket
`GET /api/config` `robot_id` / HAL identity; `sessionStorage`
`openral.simple.play` cannot override a live occupant with a stale
Bare Go2 pick (the loop ticks left Go2+Z1 loaded while the browser
still remembered `go2`). Switching UNIT on a laptop
`POST /api/demo/load`s the cricket container (same
`/tmp/openral_demo_relaunch.sh` + character-class `pgrep` as on-host
load) and waits for `/api/config` `robot_id` to become the new twin —
laptop `/healthz` never drops, so a healthz-gap poll left the dog
unchanged. While loading, UNIT keeps the *target* (do not snap back
to the old occupant). UNIT options are Bare Go2 / Go2+Z1. SKILL stays **empty** after load
until `/simple` chat proposes via sibling Acquire (walk fit on Go2,
adapt-ask on Go2+Z1, hop payload-reject on Z1). The dropdown lists
only the proposed execute id. Apply walk uses
`POST /api/demo/walk` (chat `walk_command` joystick — `go left` is
`turn_left` yaw, not strafe; else
`[0.35,0,0]`); hop on bare Go2 uses scripted
`OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32`. Recalibrate
does not rewrite hop to walk. Selecting a skill does not start motion.
Camera HMI marks (`CAM_TOP` / `01`) are white
text on a transparent badge. Live tiles attach `/api/camera/top/stream`
immediately (do **not** wait on `GET /api/demo/cricket` — that SSH
occupancy check left the overlay on **connecting** while MJPEG was
already flowing). `/simple` paints that stream with fetch + canvas
(`lib/mjpeg.ts`): parse `--frame` / `Content-Length`, decode with
`createImageBitmap`, keep only the latest JPEG if paint falls behind.
Do **not** use `<img src=multipart>` — browsers fire spurious `error`
and remounting the src aborts the connection (3 fps slideshow). A
sibling `latest.jpg` still is only until the canvas has a frame;
stop polling once pixels land (the still share of the HTTP/1.1 pool
starved the stream). `latest.jpg` 204 is **no signal** only when the
stream has never painted; a 404 (old cricket, no still route) keeps
the stream. Laptop `:4318` seeds MJPEG from the tunneled `/api/state`
thumb first (old cricket 404s `/latest.jpg` — do not wait on that 404),
then splices cricket MJPEG. Operator `/` still uses an `<img>` stream
but must not remount it after `naturalWidth > 0`; still poll is 1.5 s
(`dashboard.js?v=cam8`). The conn pill overlays cricket
ingest onto empty `/api/state`; `GET /api/config` `robot_id` is the
tunneled cricket identity when `OPENRAL_ROBOT_ID` is unset so UNIT
follows the live twin. No occupant → **Load the unit**. After
load there is no skill on that embodiment. Header primary is
**Start engine**, **Load the unit** (disabled until UNIT is picked),
or **Stop** while running. Load waits for the occupant then auto-stands
so the playhead lands on Apply. Footer **RESET** is one
`POST /api/demo/recalibrate` (**RESETTING…** while in flight).
Chat json-render **Apply it** runs the skill when already stood
(STANDING… only if the playhead is still Calibrate).
Dead cricket is 503 once (`cricket is disconnected`) — no
`RECAL_WAITS_MS` ladder and no backend `ResetToPose` retry.
**Stop** is Hub stand, not End Cricket.
Cancel-all with nothing in flight is success (rclpy
`ERROR_REJECTED`); a broken cancel dump still stands. OP_FAULT
`execute_rskill cancel failed` was the old strict `{0,2,3}` parser.
Failures stay on the current step (Alert + the same CTA retries) —
write-controls 403, unreachable dashboard, Brev credits/billing
(never a green “already in progress”), cricket SSH, start timeout,
laptop attach, load / calibrate / walk / stop errors. Laptop
Calibrate / Apply / Stop SSH `ros2` into cricket; graph down / no credits /
SSH down is OP_FAULT **cricket is disconnected** (or `start_error`),
never `ros2` not on PATH. A `202` Start
is in-flight only; the page polls `start_error` and fails as OP_FAULT
as soon as Brev reports credits/quota/billing. A live graph
**clears** a stale sshd-race latch (`Connection closed by <gateway>
port 56280` after `brev start` prints ready); Start treats
`graph_running` / `already_running` as success and Calibrate does
not prefer that leftover over occupancy. It never auto-walks. Walk's last 3 s command stand (`coast_to_stand_s`)
so the goal can end upright; **Stop** still snaps Hub stand and does not
wait the 60 s abort (see [[entities/go2]]). Playhead is `sessionStorage` `openral.simple.play`
(`step`, `robot`, `skill`). First paint does **not** restore a stored
UNIT — empty is **Load the unit** until live identity confirms.
Then `GET /api/config` + `GET /api/demo/cricket`: graph up
keeps the live wizard (not idle Start) and UNIT is the live occupant;
`skill_running` is Stop;
stored apply or stored calibrate is Apply (Reset if tipped); a loading
playhead still stands when the occupant is back.
Connecting resumes Start. Never auto-walk. There is no link back to
operator `/`. No top OPENRAL/SIMPLE header or centered logo — branding
is a footer `powered by openral`. The ingest connection pill sits on
the same row as the step mark (`// OP_LOAD`) and uses
the same 4-state ingest-age contract as operator `/` (waiting… / live /
stale / dead; host `now_unix - last_ingest_ts`, EventSource `/api/stream`).
No reconnect button: EventSource already retries every 1.5 s plus a
5 s `/api/state` poll; `reconnecting…` is transport; `stale` / `dead`
are ingest age and a click cannot move `last_ingest_ts`. Graph down
is **Start engine** (or the same CTA retry on OP_FAULT), not a second
chrome control. Cricket's in-graph dashboard has its **own** 15 min
idle End (`role=host`); that can kill deploy-sim while a laptop
`/simple` idle remaining is still counting. Laptop Start attaches
again — do not `brev start` if the VM is still RUNNING.
Engine screens (idle / connecting)
have no UNIT/SKILL pickers; **top** (`CAM_TOP`) fills the leftover
viewport on every step. Live steps add the dropdowns above the tile
and overlay LIVE. A right **Go2 chat sidebar** (`lg:w-80`; stacks under the
play column on narrow viewports) talks to sibling Acquire via
`POST /api/chat` (probe `allow_adapt: false`, ask before remap; does
**not** publish `/openral/prompt`). Laptop `:4318` loads
`~/.openral/dashboard.env` (`just dashboard-acquire-env` once) into
empty `ACQUIRE_API_*`; empty URL is FAULT. It does not overlay cameras or footer RESET.
Waiting on Acquire is `// pulling` CSS shimmer until the first
tokens; then Streamdown line-streams with `isAnimating` and a block
caret. Fit/adapted cards carry `#chat-apply` (**Apply it** / **Apply hop**).
Click dispatches the skill directly (not only json-render
`emit('press')`) and paints APPLYING… from live play (STANDING…
only if load did not already stand); while `step === running` the same id becomes STOP /
STOPPING… (`POST /api/demo/stop`). Adapt-offer carries **Adapt it**
(`#chat-adapt`); remap uses the original walk prompt, not `yes`. Switching
UNIT (Bare Go2 ↔ Go2 + Z1) appends **unit changed.** in chat only when
the occupant actually changes (not reselect, not first Load). A base
tip past 1.0 rad (same gate as the mass-balance tool) appends **the
unit fell. this skill needs retraining or finetuning.** once until
RESET stands it — verify miss, not Adapt. Conn
`waiting…` uses the same shimmer; camera `connecting` is unchanged
(CAM_TOP still fills leftover viewport). A 404 stays **CHAT_FAULT** in
the pane. Boot does
not wait on `GET /api/demo/cricket` (that SSH is off the event loop)
and must not wipe an in-flight Start. Operator Start after idle
auto-End re-arms the end guard.

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
the tunnels. Foxglove is `ws://127.0.0.1:8765`. If a local collector
already owns `:4318`, cricket's live tiles are tunneled to
`http://127.0.0.1:14318/`. If the laptop has **no** local collector
(the usual "start the dashboard" path), tunnel cricket `:4318` to
laptop `:4318` and open `http://127.0.0.1:4318/` — `:14318` will be
empty. `brev ls` RUNNING / SHELL READY is not occupancy: the VM can
be up with `openral-jazzy-go2` exited and no graph; `docker start` +
attach, not another `brev start`. Open the web client, or
hand the same websocket to desktop Studio from the CLI:

```
https://app.foxglove.dev/?ds=foxglove-websocket&ds.url=ws://localhost:8765
open "foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765"
```

Desktop Studio should use `127.0.0.1` (IPv6 `localhost`/`::1` can wedge;
do not pass `&layoutId=` — Foxglove cloud layout sync 400s with
"Invalid ID format" on a local or stale `lay_*`). The HTTPS web client
still needs `ws://localhost` (mixed-content exception is localhost-only).
Import `/tmp/openral_layout_go2.json` locally rather than syncing an
org layout id.

Import the **scene-matched** layout the deploy logs
(`/tmp/openral_layout_<robot>.json`, or a copy at repo root). In the
Layouts sidebar: **+ → Import from file**. On macOS file picker: `⌘⇧G`.
There is no layout-import CLI, and an already-imported layout keeps its
old camera state — re-import after every regenerate.

The browser will never load `file://` meshes through the websocket. The
URDF must stay on `package://` and the bridge must resolve those packages
via the ament overlay. See
[[analyses/foxglove-web-meshes-need-package-uri]].

**Cloud compute + a browser is already the path.** The twin runs on cricket
(`abundant-turquoise-cricket` / `openral-jazzy-go2`); the laptop only
forwards `:4318` / `:8765` (or `:14318` when a local collector already owns
`:4318`). There is **no public URL** to hand someone. The dashboard has no
auth (`server.py` `_exposure_warning`; issue #44 — localhost-only). A
non-loopback bind prints a warning rather than refusing, so `--host 0.0.0.0`
on a routable Brev IP would let anyone POST prompts and, with
`OPENRAL_DASHBOARD_WRITE_CONTROLS=1`, reach actuation config. Do not.
`app.foxglove.dev` is HTTPS and browsers block mixed-content `ws://` except
for `localhost`; a remote bridge would need `wss://` behind TLS + real auth.
That is a layer-boundary product change, not a flag. See
[[analyses/cloud-browser-needs-tunnel]].

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

## Native MuJoCo (the dog, without lags)

Do not add EGL cameras or a GLFW window on cricket. Stream `qpos` and
render kinematically on the laptop
([[analyses/mujoco-render-without-lag]]). First cut is shipped:
`GET /api/qpos` on the dashboard plus `openral viz mujoco --dashboard
http://127.0.0.1:4318` (`mj_forward` only, never `mj_step`). A dashboard
tab player is the same pose stream through official `@mujoco/mujoco`
WASM + Three.js — there is no better pixel-stream web player
([[analyses/mujoco-render-without-lag]] § Web player survey). Dashboard
`top` is a native MuJoCo still (proof); Foxglove 3D is a URDF stand-in.
Extra `mjr_readPixels` on the HAL executor collides with the 40 ms
proprio cliff ([[analyses/go2-proprio-freshness-cliff]]).

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

`openral deploy sim --foxglove` publishes each RGB camera as
`/compressed` **from the HAL** (the same JPEG the dashboard tiles
already encode). The generated layout points Image panels there.
Raw 640×480 RGB8 is ~9 MB/s per camera; two Go2 cams over a laptop
SSH tunnel saturated Foxglove's 10 MB send buffer and the video
stuttered. Sim no longer spawns `image_transport republish` for
those siblings — that node subscribed the raw topic and forced a
~900 KiB GIL copy per camera, which is why Bare Go2's tiles lagged
the second robot. Real cells still use the republishers. Re-import
`/tmp/openral_layout_<robot>.json` after this change — an
already-imported layout keeps the raw topic. The live Mac Studio
`openral_layout_go2` was rewritten 2026-09-17 to `top` then
`front` `/compressed`.

Dashboard tiles are MJPEG of OTLP JPEGs, not the ROS topic. The HAL
used to emit those JPEGs at 1 Hz (leftover from still-card polling);
they now track the camera timer, capped at 25 Hz. The EventSource no
longer re-ships the JPEG on every telemetry tick, and the MJPEG
endpoint reads the thumb without cloning the whole snapshot. After
a Bare Go2 / Go2+Z1 reload that picks up this HAL, both twins share
that path.

## Why Bare Go2 video looks worse than Go2+Z1

It is **not** a different encoder. This-branch manifests declare the
same two 640×480 RGB cameras at 15 Hz (`front` snout
`sim_render: false`, `top` track EGL). Both HALs call
`MujocoArmHAL.read_images`. Both publish the same OTLP JPEG. `/simple`
shows **`top` only**.

The live 2026-09-19 gap was a **stale cricket checkout**, not gait
physics. Cricket `/openral/robots/go2/robot.yaml` had **only `front`**
(no `top`, no `sim_render`). `/simple` CAM_TOP was a leftover ~0.9 Hz
still while `front` ran 9–35 Hz (cheap snout JPEG). Cricket
`go2_z1/robot.yaml` already had `front` + `top`, so the armed dog's
`top` tile was a real EGL camera and "moved perfectly." Sync this-branch
yaml + HAL (`read_images` skips `sim_render: false`) and Load Bare Go2.
After reload (2026-09-19): Bare `top` 15–32 fps / 640 px, `front` no
thumb. Hard-refresh `/simple`.

Older pixel-tax bugs also hit Bare first (raw RGB8 + republish, LANCZOS
hitch, `<img src=multipart>` remount ~3 fps). Those are fixed on this
branch. An old graph or a Foxglove layout still on `/image` instead of
`/compressed` re-creates the slideshow.

What can still differ after a clean reload:

- **Wall-clock gait.** The armed twin is heavier (extra DoF, contacts,
  arm snap). Live Go2+Z1 RTF was ~0.62. Bare Go2 steps cheaper, so
  15 Hz tiles show more sim-metres per frame — the trot looks jumpy
  at the same camera Hz. Physics RTF still caps fps
  ([[analyses/mujoco-render-without-lag]]).
- **What's in the picture.** `front` looks +X out of the snout: Bare
  Go2 is checker floor + sky; Go2+Z1 can show the arm. `top` of the
  armed dog is a fuller mesh. That is content, not better processing.

Do not add cameras to "fix" Bare Go2. Stream `qpos`.

## Go2 live camera is `top` only

`front` stays on the manifest (`vla_feature_key`, snout pose) with
`sim_render: false`. The camera rig does not splice it;
`MujocoArmHAL.read_images` does not `mjr_readPixels` it. Dashboard
`HERO_CAMERA_KEYS` is `top`; `/simple` mounts one tile. Foxglove layout
generation skips `sim_render: false`. 200 Hz proprio is unchanged.

The laptop `:4318` page **always** shows the **Side · `top`** panel, even while
WAITING / Loading Bare Go2 / no OTLP: **Main · `front`** (snout — empty
checkerboard + black sky is a healthy empty world, not a dead feed)
and **Side · `top`** (3/4 view of the dog — the HAL key is `top`, not
an invented `side`). They used to stay `hidden` until the first
`sensors.read_latest` span, which is why a WAITING screenshot was an
empty grid. The `<img>` src is `/api/camera/top/stream` from
first paint. An opaque `waiting for camera` placeholder used to sit on
top until `img.onload`; multipart MJPEG often never fires that, so the
tiles looked blank while the streams were live. Tiles now start
`is-streaming`, CSS hides the placeholder as soon as `img[src]` is
set, and telemetry `hasFrame` re-adds the class. When this process has
no local thumbs (laptop collector) it seeds one JPEG from the tunneled
`/api/state` thumb, then splices cricket MJPEG at
`http://127.0.0.1:14318/api/camera/top/stream`. Old cricket graphs
404 `/latest.jpg` — do not wait on that 404. Laptop `/api/state`
overlays cricket ingest when the collector is empty so `/simple` is
not stuck `waiting…`; `/api/config` `robot_id` is the tunneled
identity when env is unset. Direct proof
URLs on a cricket tunnel: `http://127.0.0.1:4318/api/camera/top/stream`
(dog). That is not live ROS video — it is
the same ~25 Hz OTLP JPEG MJPEG Foxglove's `/compressed` Image panels
beat. Do **not** bounce a failed MJPEG `img` to `:14318` when the page
is already served from cricket on `:4318` — that port has no listener
and leaves tiles black forever; retry same-origin. A standing robot
emits identical OTLP JPEGs; MJPEG used to send **one** part and then
stall, and browsers only paint a `multipart/x-mixed-replace` frame
after the next `--boundary` — LIVE / fps / age 0 with a dark
crosshair wrap is that bug, not a dead HAL (proof: `/api/state`
`thumbnail_jpeg_b64` still shows the dog). The stream now heartbeats
the current JPEG every 0.2 s; tiles poll
`/api/camera/{source}/latest.jpg` onto a sibling `img.camera-still`
until the MJPEG `<img>` has `naturalWidth`. The still poll must
**never** replace the stream `src` — that abort turned Bare Go2 into
a 3 fps slideshow (MJPEG TTFB was ~2.6 s, so the 200 ms still always
won). `/latest.jpg` and `/stream` 404-check `camera_known` rather than
cloning `snapshot()`. Prefer
`http://127.0.0.1:4318/` over `localhost` (IPv6 `::1` can wedge while
IPv4 is fine). Cache-bust `dashboard.js?v=cam8`.

## Freshness is measured on the host clock

The dashboard's connection pill is ingest age on the **dashboard host**
(`now_unix - last_ingest_ts` from the snapshot), not "is the page's
EventSource up" and not the browser's clock. `GET /simple` uses the
same pill (color-coded circle, same 10 s live / 60 s dead thresholds).
A laptop viewing a
port-forwarded remote `:4318` is routinely ≥60 s off the VM, which used
to freeze the pill on `DEAD (1m)` while spans were still landing. The
same host-clock age drives every per-card status dot.

## Command-band counters are session totals

The four (five with skill-failures) numbers next to the prompt are
**session totals** on the dashboard process. They do not reset on
**Recalibrate**, **Stand**, or **Reset e-stop**. Recalibrate / Stand
clear a latched kernel (`/openral/estop_reset`) and snap Hub home; they
must also broadcast `/openral/estop_cleared` via the dashboard's
persistent `EstopPublisher` so the **skill runner** un-latches. A
shell-out-only clear can leave Apply returning
`action server rejected the goal` while `/openral/safety_status` shows
`latched:false`. They do not wipe the tally. A new `deploy sim` (or a
Bare Go2 / Go2+Z1 cold-reload that actually restarts uvicorn) is what
zeroes them.

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
URL is then `http://127.0.0.1:4318/` (prefer `127.0.0.1` over
`localhost`). Hard-refresh after retunnel. Do not `pkill` a sibling's
graph or steal tunnels to "fix" WAITING. Cricket hostname can lie
`graph_running=false` while the graph is up — trust `/healthz` /
`/api/state`, not that flag. Reasoner API key is **not** required for
demo walk / load / Recalibrate.

Related: [[entities/openral-foxglove-bringup]], [[entities/go2]],
[[entities/go2-z1]].
