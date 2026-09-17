---
name: go2-foxglove-view
description: >-
  See and drive the Unitree Go2 deploy-sim in Foxglove from the CLI (cricket
  host, layout generator, foxglove:// open, in-place trot). Use when the user
  mentions Go2, Foxglove, foxglove.dev, front camera, 3D panel, display frame,
  meshes, trot, stand, "I don't see the robot", cricket dashboard, Start
  Cricket, WAITING, or a failed start of dashboard/Foxglove.
argument-hint: 'view | layout | open | march | start | troubleshoot | update <finding>'
---

# Go2 Foxglove View

CLI-first playbook for the live Go2 graph on cricket. **Update this file
in the same turn** whenever a command, frame, or viewer fact changes.

**Standing rule — start failures:** every time starting cricket, the
OTel dashboard, or Foxglove fails, **append this SKILL.md in the same
turn** (catalog bullet under **Troubleshooting / Start failures** plus
a **Log** line). Do not leave the lesson only in chat. Do not wait for
the user to say "update the skill". Wiki close-out still applies for
durable (not host-PID) findings.

Normative viz docs stay in `packages/openral_foxglove_bringup/README.md`
and [[concepts/deploy-sim-visualization]]. This skill is the operator
runbook: host-specific, fast-moving state. Durable findings are promoted
to the wiki — [[entities/go2]],
[[analyses/proving-sim-motion-not-a-frozen-stand]],
[[analyses/foxglove-web-meshes-need-package-uri]].

## Always do this first

1. Read this file's **Current beliefs**, **Troubleshooting / Start
   failures**, and **Log**.
2. Prefer the scripts in [scripts/](scripts/) over ad-hoc SSH one-liners.
3. After any new finding, append a **Log** line and patch **Current beliefs**.
4. If start failed this turn, append **Troubleshooting / Start failures**
   *before you reply*. Chat is not the runbook.

## Operator start (cricket)

1. Live robot is Brev `abundant-turquoise-cricket`, docker
   `openral-jazzy-go2`, `ROS_DOMAIN_ID=77`. The graph is
   `openral deploy sim --dashboard --foxglove` **inside the container**
   with `OPENRAL_DASHBOARD_WRITE_CONTROLS=1`. Bare `openral dashboard`
   on the laptop is not the dog.
2. `openral dashboard` is often `command not found`; use
   `uv run openral dashboard` from the repo after `just sync`. That
   local process is an **empty collector** — header WAITING, no robot,
   no cameras. Do not hit **Start Cricket** on that page expecting the
   live twin.
3. If the laptop collector owns `:4318`, the tab **always** says WAITING.
   Stop **only** that `uv run openral dashboard`, then
   `ssh -N -L 4318:127.0.0.1:4318 -F $HOME/.brev/ssh_config abundant-turquoise-cricket`
   (`ControlMaster=no`). Foxglove:
   `-L 8765:127.0.0.1:8765`. Operator URL `http://127.0.0.1:4318/` and
   `ws://127.0.0.1:8765`. Hard-refresh. Do not steal tunnels a sibling
   already holds.
4. The 3D dog is **Foxglove** (import `/tmp/openral_layout_go2.json` or
   the go2_z1 layout; display frame `base`). Dashboard cameras are
   **Main · front** + **Side · top** OTLP thumbs — they used to stay
   hidden until the first span; always mount two panels. Recalibrate is
   the demo (upright + Z1 `ARM_READY` sticky hold). Cricket must run
   this branch's `go2_z1.py`; old HAL Recalibrate 200 while the arm
   flails. Apply walk **only after** Recalibrate. Do **not** Apply
   `arm_ready`. Picker stays on `rsl-rl-onnx-go2-velocity-flat`. **Stop**
   before the 60 s deadline or freeze-fall.
5. One graph per domain. Character-class `pgrep`; never `pkill` that
   matches `/tmp/openral_demo_relaunch.sh`. Idle auto-stop is 15 min
   (`OPENRAL_CRICKET_IDLE_S`) — **End Cricket** if they only watch
   Foxglove. Load Bare/Z1 is 30–90 s cold reload. Laptop **Start Cricket**
   = `brev start` + `docker start` + tunnels + attach; cricket-hosted
   Start **cannot** `brev start` a cold VM.

## Troubleshooting / Start failures

**MUST append.** Symptom → cause → fix, dated, operator-accurate.
Patch **Current beliefs** when live host state changed. Promote durable
lessons to [[concepts/deploy-sim-visualization]].

Do **not** `pkill` the graph, steal tunnels, or fight occupancy to
"fix" a start — a sibling may be restoring video on cricket.

### Catalog (2026-09-17)

- **Operator "still waiting" after cricket restart (2026-09-17
  ~18:25Z).** Header WAITING on Mac while cricket graph was already
  LIVE. Cause: SSH `-L 4318` forward half-wedged (IPv4
  `127.0.0.1:4318` OK; `localhost` → `::1` timed out once; static HTML
  keeps `waiting…` until SSE/`/api/state` paints). Not a laptop
  collector (no `uv run openral dashboard`; listener was `ssh`). Fix:
  kill **only** the `:4318`/`:8765` tunnel PIDs, re-open
  `ssh -fN -L … -o ControlMaster=no` to cricket, hard-refresh
  `http://127.0.0.1:4318/` (prefer `127.0.0.1` over `localhost`).
  Proof: `robot_id=go2_z1`, `last_ingest_ts` age ~0 s, identity
  `go2z1mujocohal`, `safety_status` `latched:false` /
  `kernel activated`, SSE `/api/stream` first event has ingest.
  Graph stayed `go2_z1_walk` (one occupant). Pose upright-ish
  `world→base` z≈0.227 pitch ~−10° — Recalibrate **optional** before
  Apply walk, not required to clear WAITING. Do **not** E-STOP /
  relaunch for header alone.
- **Operator "restart the server" (2026-09-17 ~18:20Z).** Mac
  `http://127.0.0.1:4318/api/state` **timed out** while cricket-local
  `healthz`/`api/state` were fine (SSH listen on `:4318` still up —
  wedged forward). Refresh tunnel (`ControlMaster=no`) or call APIs
  via `docker exec` → `127.0.0.1:4318`. Official reload:
  `POST /api/demo/load` `{"preset":"go2_z1"}` → 200 accepted → cold
  relaunch `scenes/deploy/go2_z1_walk.yaml` (~10 s this time). Then
  `POST /api/demo/recalibrate` → upright z≈0.254 pitch ~−1.7°, arm
  1–6 exact `ARM_READY`, kernel `latched: false`. One graph. Retunnel
  `:4318` + `:8765`. Do **not** Apply walk unless verifying briefly;
  **Stop** before 60 s.
- **Operator "retry" / dog fallen again (2026-09-17 18:15Z).** Immediately
  `POST /api/demo/stop` (200, cancel, no e-stop) then
  `POST /api/demo/recalibrate` (200). Evidence upright:
  `world→base` [−0.05, 0, **0.254**] roll 0 pitch ~−1.8°, arm 1–6 exact
  `ARM_READY` `(0, 1.2, −1.0, −0.4, 0, 0)`, kernel unlatched. Cricket
  already had sticky `_arm_hold_pose` + `preferWalk` force-walk — no HAL
  copy / no relaunch. Short `POST /api/demo/walk` with
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat` → **202** accepted;
  identity stayed rsl-rl (not `arm_ready`); arm held ready; **Stop** then
  Recalibrate again → same upright. One graph (`go2_z1_walk`). Next:
  hard-refresh `:4318`, picker = rsl-rl walk, **Apply**, **Stop** before
  60 s (mid-gait tip risk still real on this twin).
- **`openral dashboard` → command not found.** From the repo:
  `just sync` then `uv run openral dashboard`. That laptop collector is
  **empty** (WAITING, no robot, no cameras). Do not Start Cricket there
  expecting the dog.
- **Live robot is cricket**, not the Mac process. Host
  `abundant-turquoise-cricket`, docker `openral-jazzy-go2`,
  `ROS_DOMAIN_ID=77`. Graph:
  `openral deploy sim --dashboard --foxglove` in-container with
  `OPENRAL_DASHBOARD_WRITE_CONTROLS=1`.
- **`:4318` WAITING while Foxglove is fine.** Laptop collector owns
  `:4318`. Stop only that `uv run openral dashboard` and open
  `ssh -N -L 4318:127.0.0.1:4318 -F $HOME/.brev/ssh_config abundant-turquoise-cricket`
  (`ControlMaster=no`). Foxglove `-L 8765:127.0.0.1:8765`. Then
  `http://127.0.0.1:4318/` + `ws://127.0.0.1:8765`. Hard-refresh. If a
  sibling already holds those tunnels, attach there (`:14318` is the
  cricket UI when the laptop keeps `:4318`).
- **No 3D dog / empty cameras.** 3D is Foxglove (import layout, frame
  `base`). Dashboard tiles are Main·front + Side·top OTLP thumbs — always
  mount two panels even while WAITING; they were `hidden` until the first
  span.
- **Tiles blank while 640×480 JPEGs are live.** Front/top thumbs and
  MJPEG were flowing; an opaque `waiting for camera` overlay waited for
  `img.onload` and multipart MJPEG often never fires that. Tiles now
  start `is-streaming`. Hard-refresh `http://127.0.0.1:4318/`. Direct:
  `/api/camera/top/stream` (side — see the dog) and
  `/api/camera/front/stream` (snout; checkerboard+sky is healthy).
  Cricket hostname `brev-d4dyyrsd1` can lie `graph_running=false` while
  the graph is up — do not End/Start from that. Idle 15 min and the
  60 s walk deadline still kill the demo.
- **Occupancy / reload timed out.** One graph per `ROS_DOMAIN_ID`.
  Character-class `pgrep` (`[o]penral deploy sim`). Never `pkill -f
  'openral deploy sim'` and never match `/tmp/openral_demo_relaunch.sh`.
- **Recalibrate 200, arm flails / Apply looks frozen.** Cricket HAL must
  be this branch's `go2_z1.py` (`_arm_hold_pose`, Recalibrate =
  `GO2_Z1_ARM_READY` joints 1–6 `(0, 1.2, −1.0, −0.4, 0, 0)` not menagerie
  `ARM_HOME` `(0, 0.785, −0.261, −0.523, …)`). Apply walk only after
  Recalibrate. Do not Apply `arm_ready`.
- **Apply skill stands still (2026-09-17 18:00Z).** Last
  `ExecuteRskill` was `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` (2 s
  `horizon_s`, `goal_satisfied`) — that is a Hub-stand hold, not a gait.
  `fillSkillSelect(preferWalk)` kept the **currently selected**
  `arm_ready` option (`keep`) so Recalibrate did not switch the dropdown
  to `rsl-rl-onnx-go2-velocity-flat`. Fix: preferWalk now forces the walk
  id (`?v=walk1`). Hard-refresh `http://127.0.0.1:4318/`. Confirm picker
  is the rsl-rl walk, then Apply. **Stop** before 60 s.
- **Walk tips mid-gait on Go2+Z1 (not the 60 s deadline).** 18:05Z
  `POST /api/demo/walk` identity
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`, ~8 s / chunk 370,
  `world→base` [2.96, −1.14, **0.058**] roll **~180°**. Kernel unlatched,
  no e-stop, budget still 60 s. Stop then Recalibrate. Bare-Go2 earlier
  the same hour cancelled at **25.5 s / 748 chunks** (deadline was 60 s)
  and idle-held the last trot waypoint — also not `deadline_missed`.
- **Operator "requantize / recalibrate didn't work / dog fell"
  (2026-09-17 ~18:11Z).** "Requiatize" = **Recalibrate**, not a new
  quantize. Do **not** E-STOP. `POST /api/demo/stop` first (cancel skill,
  no latch), then `POST /api/demo/recalibrate`. Success evidence on
  Go2+Z1: `world→base` z≈0.25 roll≈0 pitch ~−2°, arm 1–6 exact
  `(0, 1.2, −1.0, −0.4, 0, 0)`. If Recalibrate is 200 but the dog is
  still fallen / arm wrong → old cricket HAL (copy this branch
  `go2_z1.py` sticky `_arm_hold_pose`, reload character-class pgrep).
  This recovery: Stop canceled skill, Recalibrate 200, upright +
  ARM_READY, kernel `latched: false` (`estop cleared`). Picker
  `dashboard.js?v=walk1` already forces walk.
- **Idle auto-stop / long reload.** 15 min idle (`OPENRAL_CRICKET_IDLE_S`)
  **End Cricket**s if they only watch Foxglove. Load Bare/Z1 is 30–90 s
  cold reload.
- **Dashboard crash, Foxglove still up, WAITING / no video.**
  `HERO_CAMERA_KEYS` import killed the cricket dashboard (`store.py`
  lagged `app.py`). Restore dashboard modules; do not restart Foxglove
  as the first move.
- **Start Cricket no-op on a cold VM.** Laptop Start must `brev start` +
  `docker start` + tunnels + attach. Start **on cricket** only starts the
  graph and cannot `brev start` a stopped instance.

## Current beliefs (2026-09-17)

- Host: Brev `abundant-turquoise-cricket`. Container: `openral-jazzy-go2`.
  Bind-mount `/openral` ← `/home/ubuntu/workspace/openral-go2`.
  `ROS_DOMAIN_ID=77`. Bridge `ws://127.0.0.1:8765` (port-forward to the Mac).
- Live scene **now (2026-09-17 ~18:25Z):** Same Go2+Z1 `go2_z1_walk`
  occupant (write-controls on). Operator "still waiting" was a **wedged
  Mac SSH tunnel**, not empty collector / not dead OTLP. Retunneled
  `:4318`+`:8765` (`ControlMaster=no`). Proof Mac+cricket:
  `robot_id=go2_z1`, ingest age ~0 s, `go2z1mujocohal`,
  `safety_status` kernel activated / unlatched. Prefer
  `http://127.0.0.1:4318/` over `localhost` (IPv6 `::1` can hang while
  IPv4 is live). Pose `world→base` [−0.11, 0, **0.227**] pitch ~−10°
  upright — Recalibrate optional before Apply. Hard-refresh clears the
  static HTML `waiting…`. No local collector. Do **not** Apply walk
  unless verifying briefly; **Stop** before 60 s. Do **not** Apply
  `arm_ready`. Foxglove `ws://127.0.0.1:8765`.
- Prior ~18:20Z: `go2_z1_walk` after `POST /api/demo/load` `go2_z1`;
  Recalibrate → z≈0.254 pitch ~−1.7°, ARM_READY, kernel unlatched.
  Mac `:4318` HTTP hung while cricket-local was healthy.
- Prior 18:11Z: same recovery after "requantize" (z≈0.253). Prior tip
  ~18:05Z z=0.058 roll ~180°.
- Prior 17:50Z occupant was Bare Go2 `go2_walk` (superseded). Mac
  `http://127.0.0.1:4318/` **is** the cricket dashboard (SSH
  `ControlMaster=no` to cricket `:4318`); `:14318` is the same UI;
  Foxglove `ws://127.0.0.1:8765`. No local `uv run openral dashboard`
  on 4318. Camera tiles were covered by an opaque `waiting for camera`
  placeholder (MJPEG `load` never fired) while `/api/state`
  `topics.perception.cameras.{front,top}` had 640×480 thumbs ~20 fps
  and `/api/camera/{front,top}/stream` returned JPEG. Copied
  `is-streaming` HTML/CSS/JS (`?v=cam2`) onto the bind-mount. Dog
  standing in `top` (not tipped — did not Recalibrate). `front` is
  snout-out checkerboard. Hard-refresh `http://127.0.0.1:4318/`.
  Cricket hostname is `brev-d4dyyrsd1` so `GET /api/demo/cricket`
  still reports `role=laptop` / `graph_running=false` while the graph
  is up — do not End/Start from that lie. Idle 15 min still auto-Ends
  if they only watch Foxglove. Walk 60 s still freeze-falls.
  Recalibrate is `POST /api/demo/recalibrate` →
  `/openral/go2_z1/reset_to_pose` (this twin; Bare Go2 uses `/openral/go2/…`).
  Demo wizard: Bare Go2 auto-stands after load (no auto-walk); Go2+Z1 asks
  Recalibrate first — that is the walk gate, not a yaw PID. Picker defaults
  to walk after Recalibrate; a saved `arm_ready` pick is not restored (that
  2 s hold is why Apply looked frozen). Cricket HAL sticky `_arm_hold_pose`
  snaps **arm joints only** (never legs / free base).   Recalibrate pose is
  `GO2_Z1_ARM_READY` not menagerie ARM_HOME. Earlier 17:44Z occupant was
  `go2_z1_walk` (after `/tmp/openral_demo_relaunch.sh`); superseded by
  17:50Z Bare `go2_walk` above. The 17:39Z Bare Go2 graph had no
  dashboard (`HERO_CAMERA_KEYS` missing on cricket `store.py`; copied
  Mac dashboard modules). Recalibrate 202
  `robot_id=go2_z1`: `world→base` z≈0.253 roll 0 pitch ~-1.9°. Mac
  `http://127.0.0.1:4318/` is the cricket UI (SSH `ControlMaster=no`);
  Foxglove `ws://127.0.0.1:8765`. Served `dashboard.js` has `savedIsWalk`.
  Prior Apply walk (`Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`, 202):
  `world→base` translated ~1.04 m in 8 s (dx 0.99, dy -0.33), z≈0.36 upright,
  arm 1–6 stayed `(0, 1.2, -1.0, -0.4, 0, 0)`, FL_thigh_span 0.20 rad. **Stop**
  canceled without e-stop and Hub-stood at origin z≈0.26 pitch ~-1.4°.
  Kernel unlatched. Walk is 60 s then `deadline_missed` freeze-fall unless
  Stop runs first. Gripper joint still reads 1.0 vs target 0.0.
  **Stop** (`POST /api/demo/stop`) cancels `ExecuteRskill` without latching
  e-stop, then Hub-stands so Apply can run again. E-STOP still latches.
  **Start Cricket** (`POST /api/demo/cricket/start`) from a **laptop**
  dashboard `brev start`s if stopped, `docker start`s this container,
  opens SSH tunnels (`ws://127.0.0.1:8765`, cricket dashboard
  `http://127.0.0.1:14318/` — local `:4318` stays the laptop page), and
  attaches the graph if it is down. If the graph is already up, Start
  only ensures tunnels (already-running, no teardown). Start **on this
  host** only starts the graph. **End Cricket** (`POST /api/demo/cricket/end`)
  cancels the skill, kills the graph (character-class pgrep, not
  `pkill -f 'openral deploy sim'`), then `brev stop` / host halt. From a
  laptop, End still `brev stop`s. Idle auto-Ends after 15 min
  (`OPENRAL_CRICKET_IDLE_S`); a running walk is not idle. The bar shows
  `auto-stop in mm:ss`.
  Healthy stand is `world→base` z≈0.27, RPY≈0, xy≈0.
  Stand = Hub `[-0.1, 0.9, -1.8] × 4` (FL/FR/RL/RR hip/thigh/calf).
  Walk Apply is 60 s then `deadline_exceeded`; idle holds the last gait
  pose (not Hub). Gravity on → fall at the end unless the operator hits
  **Stop** first (cancel + Hub stand, no e-stop). Recover a tip with Stand
  / Recalibrate. Last live tip ~17:09Z (Go2+Z1): `world→base`
  [-19.78, 3.95, 0.155], roll 81° — Recalibrate on `:14318` snapped
  upright z≈0.24 roll≈0 (xy not origin). Prior Bare-Go2 tip 15:06Z was
  [12.56, -4.64, 0.154] roll 77°.
  Demo Bare Go2 / Go2+Z1 reload must exec `/tmp/openral_demo_relaunch.sh`
  (character-class pgrep). `pkill -f 'openral deploy sim'` kills the
  relaunch script. Host `/` at 100% (HAL coredumps) makes `docker exec`
  fail with `no space left on device`. Source Jazzy + overlay before
  `openral deploy sim` or it exits `ros2 not found on PATH`.
- Root TF is **`base`**, not `base_link`. Missing follow frame → empty 3D.
  A live identity `base → base_link` alias may be published; do not assume it
  survives a restart.
- `/openral/cameras/front/image` looks **out** from the snout. It cannot
  show the body (black sky / gray floor is a healthy empty world).
- Foxglove **Image** panel ≠ **3D** panel. The dog is only in 3D. `top` is
  the third-person Image. `--foxglove` now publishes `/compressed` and the
  generated layout points there — raw 640×480 RGB8 was ~18 MB/s for two
  cameras over the laptop tunnel. Mac Studio `openral_layout_go2`
  (`lay_0ecFylVWqq0HLLxN`) was rewritten 2026-09-17 to `top` then `front`
  `/compressed`. Live cricket graph lacked those republishers (deploy
  started 14:51Z before the wiring); two `image_transport republish`
  nodes were attached on the running graph. JPEG `/compressed` flowing
  ~7 Hz. Re-import after the next generate.
- Web/desktop Studio only fetches **`package://`** meshes from the bridge.
  Overlay `/tmp/openral_foxglove_ament` must be first on the **bridge**
  `AMENT_PREFIX_PATH`. `file://` rewrite is wrong for a remote viewer.
- Idle ticks must PD-hold Hub stand (`Go2MujocoHAL.idle_step`). Writing
  home angles into torque `ctrl` folds the calves into the stops.
- Remote heredocs need `docker exec -i`. Without `-i`, `bash -s` gets EOF,
  the whole block is skipped, and the script still **exits 0** in ~5 s with
  no output — a silent no-op that looks like a healthy run.
- A published chunk proves nothing. `/openral/action_applied` stays silent
  even while the dog trots, and `ros2 node list` / `ros2 lifecycle get`
  return empty / "Node not found" against a stale ros2cli daemon while
  `ros2 topic echo` works fine. Ground truth is the `/joint_states` span —
  `march.sh` prints `FL_thigh_span` (~0.4 rad for a real trot).
- Run `march.sh` in the **foreground**. Backgrounded, it dies with the
  shell before the 15 s window elapses, and a separate sampler then reads
  a frozen Hub stand and falsely indicts the kernel.
- Foxglove has **no layout-import CLI**. Generate the JSON, then
  `foxglove://open?ds=…`. Operator still imports the JSON once
  (Layouts → + → Import; macOS `⌘⇧G`).
- Official open: `open "foxglove://open?ds=foxglove-websocket&ds.url=ws://localhost:8765"`
  ([open via CLI](https://docs.foxglove.dev/docs/visualization/open-via-cli)).
  3D **Display frame** = camera follow frame
  ([3D panel](https://docs.foxglove.dev/docs/visualization/panels/3d)).
  Reset camera: key `1`.
- Default Go2 3D orbit is a **left side** view (`thetaOffset=90`, `phi=75`,
  `distance=2.2`, look-at z=0.15). Re-import the JSON after regenerating —
  an already-imported layout keeps its old camera.
- Floor is a Foxglove **Grid** custom layer in frame **`world`** at z=0
  (`size=8`, 16 divisions). `base` sits at z≈0.27 so the feet read as
  standing on it. Do **not** parent the grid to `base` — that lifts the
  floor to chest height. Live add: 3D settings → Layers → **+** → Grid →
  Frame `world`. Generated layout ships `layers.go2-floor`.
- RGB **arrows** are TF axes, not the robot. Hide live: 3D settings search
  box → type `axis` → **Transforms → Axis scale = 0**. That control is a
  sibling of Scene (after View), not inside Scene. Do **not** disable
  `/tf` — that unposes the URDF. Generated layout ships `axisScale: 0`.
- Red `!` on `/robot_description` = mesh fetch / link errors, not the
  axis slider. Axis scale 0 + Show axis off is already correct. The body
  is 17 `package://go2_description/dae/*.dae` visuals. `Head_upper` /
  `Head_lower` are collision-only (no snout mesh). 12 inertial rotor
  links have no geometry. An older bridge logged
  `Package [go2_description] does not exist`; the live overlay is fine
  but this bridge process has logged **zero** asset fetches — reconnect
  the websocket or toggle `/robot_description` off/on so Studio retries.

## CLI

From the OpenRAL repo on the Mac:

```bash
# 1. Scene-matched layout (follow base, left-side 3D, world-frame floor)
.agents/skills/go2-foxglove-view/scripts/generate-layout.sh

# 2. Open Foxglove desktop on the forwarded websocket
.agents/skills/go2-foxglove-view/scripts/open-viewer.sh

# 3. In-place trot on cricket (15 s, then Hub stand)
.agents/skills/go2-foxglove-view/scripts/march.sh
```

Manual equivalents:

```bash
  PYTHONPATH=packages/openral_foxglove_bringup \
  python -m openral_foxglove_bringup.layout \
  --cameras top front --compressed --follow-frame base -o /tmp/openral_layout_go2.json

open "foxglove://open?ds=foxglove-websocket&ds.url=ws://localhost:8765"

ssh -F "$HOME/.brev/ssh_config" abundant-turquoise-cricket \
  'docker exec openral-jazzy-go2 bash -lc "…"  # see scripts/march.sh
```

## See the dog (after open)

1. Import `/tmp/openral_layout_go2.json` (re-import after every generate —
   camera orbit, axis scale, and the world-frame floor are in the JSON).
2. 3D settings → Display frame `base`. Topics on: `/robot_description`, `/tf`.
3. You should be looking at the **left side**, grid under the feet. Press
   `1` if the view is lost.
4. Image panels: `top` first (third-person), then `front` (looks out). Re-import
   after generate — they now point at `/compressed` siblings.
5. No floor after import: Layers → **+** → Grid, Frame `world` (not `base`).

## Health checks (cricket container)

```bash
export ROS_DOMAIN_ID=77
# source /opt/ros/jazzy/setup.bash && source /openral/install/setup.bash
ros2 topic echo /joint_states --once          # Hub stand
ros2 run tf2_ros tf2_echo world base          # z ≈ 0.27, identity
# /robot_description: 17× package://go2_description, 0× file://
# foxglove_bridge AMENT_PREFIX_PATH starts with /tmp/openral_foxglove_ament
```

## Do not

- Prompt `stand` / `walk` on the Brev **host** (no `rclpy`). Source ROS
  **inside** `openral-jazzy-go2`.
- Expect walking across the floor on `go2_bench` (gravity off, no rSkill).
- Publish to `/openral/safe_action` (bypasses the kernel).
- Restart the whole graph to "show" the robot — fix the viewer first.
- `pkill` the graph, steal `:4318`/`:8765` tunnels, or fight occupancy
  when a sibling is already attached (e.g. restoring cricket video).
- Leave a start failure only in chat — append **Troubleshooting / Start
  failures** this turn.

## Log

- 2026-09-17 ~18:25Z: Operator "still waiting". Cricket OTLP/dashboard
  already live (`go2_z1` / age ~0 s); Mac tunnel half-wedged
  (`localhost`/`::1` timeout, IPv4 OK). No laptop collector. Retunnel
  `:4318`+`:8765` only. Hard-refresh `http://127.0.0.1:4318/`. Pose
  upright z≈0.227 pitch ~−10° — Recalibrate optional for walk, not for
  LIVE header. Did not relaunch / E-STOP / Apply.
- 2026-09-17 ~18:20Z: Operator "restart the server". Mac `:4318` tunnel
  wedged (HTTP timeout; cricket-local healthz OK). Official
  `POST /api/demo/load` `go2_z1` accepted → relaunch
  `go2_z1_walk.yaml`. Recalibrate → upright z≈0.254 pitch ~−1.7°,
  ARM_READY exact, kernel unlatched. Retunnel `:4318`/`:8765`. Live
  `go2_z1` not WAITING. Did not Apply walk. Next: hard-refresh
  dashboard, picker rsl-rl walk, Apply only if wanted, **Stop** before
  60 s.
- 2026-09-17 18:15Z: Operator "retry". Stop 200 + Recalibrate 200 →
  upright z≈0.254 pitch ~−1.8°, arm exact `ARM_READY`. No HAL copy /
  no relaunch. Short walk POST 202 identity
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`; Stop + Recalibrate
  again upright. One graph. Hard-refresh, picker walk, Apply, **Stop**
  before 60 s.
- 2026-09-17 ~18:11Z: Operator "calibration didn't work / dog fall /
  requiatize". Stop (canceled skill, no E-STOP) then Recalibrate 200
  on Go2+Z1. Pose proof: z≈0.253 roll 0 pitch ~−2°, arm exact
  ARM_READY, kernel unlatched. No HAL copy needed this time. Next for
  operator: hard-refresh `:4318`, picker on rsl-rl walk, Apply, **Stop**
  before 60 s.
- 2026-09-17: Apply stood still — last goal
  `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` (2 s hold). Picker
  `fillSkillSelect` kept selected `arm_ready` even with `preferWalk`.
  Forced walk id; cache `?v=walk1`. Arm 1–6 after Recalibrate is
  `ARM_READY` `(0, 1.2, −1.0, −0.4, 0, 0)` not `ARM_HOME`. Walk
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat` translated ~3 m in 8 s
  then tipped z=0.058 roll ~180° (not the 60 s deadline). Stop +
  Recalibrate; graph is Go2+Z1 upright z≈0.254. Hard-refresh, picker
  walk, Apply, **Stop** before 60 s.
- 2026-09-17: Tiles blank with live 640×480 front/top JPEGs. Opaque
  `waiting for camera` waited on `img.onload`; multipart MJPEG often
  never fires. Fix: tiles start `is-streaming`; hard-refresh
  `http://127.0.0.1:4318/`; proof `/api/camera/top/stream` (side, dog)
  and `/api/camera/front/stream` (snout, checkerboard+sky healthy).
  Cricket hostname `brev-d4dyyrsd1` can lie `graph_running=false` while
  the graph is up. Idle 15 min + 60 s walk deadline still kill the demo.
- 2026-09-17: Operator "i dont see the video". Mac `:4318` **is** cricket
  (SSH tunnel; no local collector). Graph up: Bare `go2_walk`, one
  occupant, ingest live, `front`/`top` 640×480 thumbs + MJPEG JPEG
  flowing. Tiles looked blank because an opaque `waiting for camera`
  placeholder covered the `<img>` until `load` (multipart never fires).
  Copied `is-streaming` + `?v=cam2` static onto bind-mount. Dog
  standing in `top` — no Recalibrate. Look **now**:
  `http://127.0.0.1:4318/` (hard-refresh), or
  `http://127.0.0.1:4318/api/camera/top/stream`. Foxglove
  `ws://127.0.0.1:8765`. Cricket hostname `brev-d4dyyrsd1` still lies
  `graph_running=false`. Idle 15 min + 60 s walk deadline leftover.
- 2026-09-17: Operator asked to file every start problem into this skill
  (not only chat) and to keep appending on future start failures.
  Added **Operator start**, **Troubleshooting / Start failures**
  (MUST-append standing rule), and catalog: `openral dashboard` not
  found / empty laptop collector; live graph is cricket
  `deploy sim --dashboard --foxglove`; `:4318` WAITING if laptop owns
  the port — stop that collector + tunnel cricket (`ControlMaster=no`);
  3D is Foxglove / dashboard thumbs always two panels; occupancy
  character-class pgrep never match relaunch.sh; Recalibrate is the
  demo (this-branch HAL, no Apply arm_ready, Stop before 60s); 15 min
  idle auto-End; `HERO_CAMERA_KEYS` dashboard crash; laptop Start =
  brev+docker+tunnels, cricket Start cannot brev a cold VM.
- 2026-09-17: Operator "start the app". Cricket RUNNING, container Up.
  Occupant was Bare `go2_walk` from 17:39Z with Foxglove but dashboard
  dead (`ImportError: HERO_CAMERA_KEYS` — cricket `store.py` lagged
  `app.py`). Copied Mac dashboard modules + `go2_z1.py` onto the bind-mount.
  Official relaunch `go2_z1_walk` via `/tmp/openral_demo_relaunch.sh`
  (character-class pgrep, not `pkill -f`). `GET /api/state` live
  `go2z1mujocohal` / `go2_z1` not WAITING. Recalibrate 202, z≈0.253
  pitch ~-1.9°. Tunnels `:4318` and `:8765` (`ControlMaster=no`). Opened
  `foxglove://…8765`. Did not Apply walk. Hard-refresh then picker
  `rsl-rl-onnx-go2-velocity-flat`, Apply, Stop before 60s.
- 2026-09-17: Apply walk did not move the Go2+Z1. Dashboard logs: four
  `ExecuteRskill` of `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` (2 s
  `horizon_s`, `goal_satisfied`); **zero** rsl-rl goals. Picker restored
  saved arm_ready over preferWalk after Recalibrate. HAL snap was already
  arm-only. Fixed picker (`savedIsWalk`); `_snap_arm_hold` now skips legs
  and `qpos[0:7]`. Recalibrate then `POST /api/demo/walk` 202: identity
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`, +1.04 m xy in 8 s, arm
  stayed ready. Stop (no e-stop) Hub-stood origin z≈0.26. Refresh the
  dashboard so the picker fix loads. Graph not relaunched.
- 2026-09-17: Circling Go2+Z1. Recalibrate API was 200 but cricket HAL
  had no sticky `_arm_hold_pose` and dashboard pose was ARM_HOME. Stop
  then Recalibrate still pitched ~13°, arm qvel huge. Copied this
  branch `go2_z1.py`, patched Recalibrate to ARM_READY, `POST /api/demo/load`
  `go2_z1` (character-class pgrep). Recalibrate after restart: z=0.254
  roll 0 pitch -1.8° yaw 0, arm 1–6 exact ready, qvel 0. Mac `:4318`
  was the cricket UI. Apply walk only after Recalibrate. No heading lock.
- 2026-09-17: Operator on Mac `http://127.0.0.1:4318` saw WAITING / no
  cameras / no robot. That process is the laptop collector
  (`OPENRAL_DASHBOARD_WRITE_CONTROLS=1 uv run openral dashboard`, PID
  62580) — not the graph. Cricket `abundant-turquoise-cricket` was
  already RUNNING; container `openral-jazzy-go2` Up 3h; occupant was
  already `go2_z1_walk` (`healthz` ok, write-controls on). Did **not**
  restart. Opened `ControlMaster=no` tunnels Foxglove `:8765` and
  cricket dashboard `:14318` (left local `:4318` alone). Recalibrate
  on `:14318` (dog was on its side: `world→base` z=0.155 roll ~81°) →
  z≈0.24 roll≈0. MJPEG `front`/`top` JPEG flowing on cricket. Opened
  `foxglove://…8765` + `http://127.0.0.1:14318/`.
- 2026-09-17: Laptop **Start Cricket** was a no-op (this page assumed it
  was already on cricket and could not `brev start`). It now `brev start`s
  if stopped, `docker start`s `openral-jazzy-go2`, opens SSH tunnels
  (`ControlMaster=no`, Foxglove `:8765`, cricket dashboard `:14318`),
  and attaches. Already-running is tunnel + Foxglove, not a relaunch.
  **End Cricket** from the laptop still `brev stop`s.
- 2026-09-17: Demo **Stop** added (`POST /api/demo/stop`). Cancels
  `/openral/execute_rskill` without latching e-stop, then Hub stand so
  Apply can run again. Ends a walk *before* the 60 s deadline freeze-fall.
- 2026-09-17: Walk Apply 15:05:11Z ran the full 60 s / 1800 chunks then
  `deadline_missed`. Kernel unlatched. Last gait waypoint frozen by
  `idle_step`; `world→base` [12.56, -4.64, 0.154] roll 77° (on its side).
  `_drain_and_idle_hold` is a sleep, not a Hub snap. Stand / Recalibrate
  to recover; **Stop** is now the intended early exit.
- 2026-09-17: Demo wizard split. Bare Go2 auto-calibrates after reload
  and lands on select skill + Apply. Go2+Z1 confirms Recalibrate first.
  Neither auto-walks. Recalibrate stays available for tips.
- 2026-09-17: Reimported Mac Studio `openral_layout_go2`
  (`lay_0ecFylVWqq0HLLxN`): Image `cam_0`/`cam_1` now
  `/openral/cameras/{top,front}/image/compressed`. Generated
  `/tmp/openral_layout_go2.json` and reopened
  `foxglove://…&layoutId=lay_0ecFylVWqq0HLLxN`. Foxglove has no import
  CLI; the app was closed so the datastore write stuck. A
  `layouts-local` copy was wiped on launch (org layout is the live one).
  Cricket graph lacked republishers; spawned live
  `image_transport republish raw compressed` for `top` and `front`.
  `/compressed` JPEG flowing (~7 Hz).
- 2026-09-17: Demo "reload timed out" after Bare Go2 / Go2+Z1. `pkill -f
  'openral deploy sim'` matched the `bash -c` killer argv; relaunch never
  started. HAL SIGSEGV cores filled cricket `/` (100%); `docker exec`
  failed until cores + exited containers were removed. Hard-clean +
  relaunch `go2_walk.yaml` with Jazzy sourced. `healthz` ok,
  `robot_id=go2`, Foxglove 8765 open. Mac tunnels still live. Reload
  now writes `/tmp/openral_demo_relaunch.sh`.
- 2026-09-17: Image stutter. Dashboard tiles were 1 Hz OTLP JPEGs *and*
  those JPEGs rode every SSE tick; Foxglove shipped uncompressed 640×480.
  HAL thumbs now 25 Hz cap, SSE omits thumbs (MJPEG is the video), deploy
  `--foxglove` republishes `/compressed` and the layout points there.
- 2026-09-17: Graph died ~14:31Z after a Bare Go2 reload (dashboard + HAL
  clean exit, leftover Xvfb/zombies). Hard-clean + restart on
  `go2_walk.yaml` with write-controls on. `healthz` ok,
  `/api/config` `robot_id=go2`, Recalibrate POST accepted. Mac tunnels
  `4318`/`8765` still live. Reasoner stays unconfigured (no API key).
- 2026-09-17: Restarted on `go2_z1_walk` for arm-command testing. Spawn
  `[-0.05, 0, 0.25]` upright. Dashboard write-controls left **off** this
  session because a Walk POST on reconnect had already knocked it over.
- 2026-09-16: Front Image is empty-world, not a dead camera. 3D follow
  `base_link` with no alias draws TF-only / black. Overlay + `package://`
  confirmed on cricket. Two in-place trots through
  `/openral/candidate_action` (kernel unlatched).
- 2026-09-16: Operator asked for a side view. `generate-layout.sh` now
  writes `thetaOffset=90` (left side, dog faces +X). Front Image still
  cannot show the body.
- 2026-09-16: TF axis arrows off via `scene.transforms.axisScale = 0`.
  Live toggle: 3D settings → Transforms (sibling of Scene) → Axis scale.
  Operator opened Scene; that section has no Axis scale.
- 2026-09-16: Operator screenshot: `/robot_description` red !,
  Show axis off, Axis scale 0, Display Auto, "12 links have errors",
  Head_upper / Head_lower listed. Overlay + `package://` OK on cricket
  (`AMENT_PREFIX_PATH` starts `/tmp/openral_foxglove_ament`, DAEs on
  disk). Current `foxglove_bridge` pid 4490 has no asset-fetch lines.
  Prior pid logged `Package [go2_description] does not exist`. Studio
  is showing stale / unfetched meshes, not a missing axis control.
- 2026-09-16: `march.sh` was a silent no-op — `docker exec` without `-i`
  dropped the heredoc, exit 0, no output. Added `-i` and an in-process
  `/joint_states` readback (`FL_thigh_span`, warns under 0.05 rad).
  Verified trot: span 0.404 rad over 312 samples, kernel unlatched
  (`latched: false`, `detail: kernel activated`), 25 chunks forwarded on
  `/openral/safe_action`. `action_applied` published nothing throughout —
  it is not a liveness signal.
- 2026-09-16: Operator asked for a floor so the stand pose reads against
  ground. `generate-layout.sh` now writes a `foxglove.Grid` layer
  (`go2-floor`) in `world` at z=0, 8 m, 16 divisions. Live path: 3D →
  Layers → + → Grid → Frame `world`. Re-import required.
