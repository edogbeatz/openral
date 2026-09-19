---
name: go2-foxglove-view
description: >-
  See and drive the Unitree Go2 deploy-sim (operator /simple dashboard +
  Foxglove) from the CLI. Use when the user says start the app, start the
  dashboard, start cricket, open /simple, Go2, Foxglove, foxglove.dev, front
  camera, 3D panel, display frame, meshes, trot, stand, "I don't see the
  robot", cricket dashboard, Start Cricket, WAITING, or a failed start of
  dashboard/Foxglove. When asked to start: run scripts/start-app.sh this
  turn — do not print the command and wait.
argument-hint: 'start | view | layout | open | march | troubleshoot | update <finding>'
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
[[analyses/foxglove-web-meshes-need-package-uri]],
[[analyses/cloud-browser-needs-tunnel]].

## Always do this first

1. Read this file's **Current beliefs**, **Troubleshooting / Start
   failures**, and **Log**.
2. Prefer the scripts in [scripts/](scripts/) over ad-hoc SSH one-liners.
3. After any new finding, append a **Log** line and patch **Current beliefs**.
4. If start failed this turn, append **Troubleshooting / Start failures**
   *before you reply*. Chat is not the runbook.

## When asked to start (mandatory)

Do **not** describe the command and wait. Run it this turn.

```bash
.agents/skills/go2-foxglove-view/scripts/start-app.sh
```

`--dashboard-only` skips cricket. `--no-open` skips the browser.
That script: reuse `http://127.0.0.1:4318/healthz` if live, else
`just dashboard` from repo root (write-controls +
`~/.openral/dashboard.env`); then `POST /api/demo/cricket/start`
(already-running is success); then open `/simple`. Docs:
[`docs/quickstart/dashboard.md`](../../../docs/quickstart/dashboard.md).
Do not steal tunnels. Do not `pkill` the graph. Do not loop
`brev start` on credits. If start failed, append **Troubleshooting /
Start failures** before you reply.

## Operator start (cricket)

1. Live robot is Brev `abundant-turquoise-cricket`, docker
   `openral-jazzy-go2`, `ROS_DOMAIN_ID=77`. The graph is
   `openral deploy sim --dashboard --foxglove` **inside the container**
   with `OPENRAL_DASHBOARD_WRITE_CONTROLS=1`. The laptop collector is
   `just dashboard` (not a bare empty `openral dashboard` without
   Start Cricket — that is WAITING, no robot).
2. One-time: `just dashboard-acquire-env` writes
   `~/.openral/dashboard.env` from Railway. After that, `openral
   dashboard` loads `ACQUIRE_API_URL` + `ACQUIRE_API_KEY` when those
   env vars are empty (no library default; empty URL is still FAULT).
   Laptop Start tunnels Foxglove `:8765` and cricket `:14318` so this
   process keeps `:4318`. Open `http://127.0.0.1:4318/simple`. `GET /`
   307s there; classic root UI is not started. `ws://127.0.0.1:8765`
   — not `localhost` if IPv6 `::1` wedges. Hard-refresh. Do not steal
   tunnels a sibling already holds.
3. **top** always fills leftover viewport (`front` is `sim_render: false`).
   Engine has no pickers. Conn pill is ingest age
   (waiting… / live / stale / dead). Idle follows live ingest /
   `graph_running` — Start engine is not stuck when the twin is up.
   3D dog is **Foxglove** (layout; display frame `base`). Cricket
   attach/reload sets `OPENRAL_CRICKET_IDLE_S=0` so the in-graph
   collector does not auto-End. Laptop idle is still 15 min.
4. **Recalibrate** is the demo on Go2+Z1 (upright + Z1 `ARM_READY`
   sticky hold — this-branch HAL). Apply walk **only after** Recalibrate.
   Picker must be `rsl-rl-onnx-go2-velocity-flat` — never Apply
   `arm_ready` (2 s Hub hold that looks like "doesn't move").
   Hard-refresh for picker fix (`?v=cam8` / `?v=walk1`). **Stop**
   before the 60 s deadline. A second Apply stops the current skill
   first (do not queue behind a 60 s walk).
5. One graph per domain. Character-class `pgrep`; never `pkill` that
   matches `/tmp/openral_demo_relaunch.sh`. Idle auto-End is 15 min —
   do not End Cricket mid-demo. Load Bare/Z1 is 30–90 s cold reload
   (not the reasoner). Laptop **Start Cricket** = `brev start` +
   `docker start` + tunnels + attach.

## Troubleshooting / Start failures

**MUST append.** Symptom → cause → fix, dated, operator-accurate.
Patch **Current beliefs** when live host state changed. Promote durable
lessons to [[concepts/deploy-sim-visualization]].

Do **not** `pkill` the graph, steal tunnels, or fight occupancy to
"fix" a start — a sibling may be restoring video on cricket.

### Catalog (2026-09-17)

- **Bare Go2 hop is gym spring_jump** (2026-09-19)
  Chat Apply hop is `OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32`.
  Cricket must have that rSkill dir **and** this-branch
  `rsl_rl_onnx.py` (frame-major + constants + joystick A). Laptop Load
  copies those paths (`sync_cricket_scripted_hop`) then reloads. Old
  adapter 401s / rejects the YAML. mjlab hop still crouches. Scripted
  zero hop is fallback, not the picker. HTTP 202 is not hop — need
  `skill_built` and feet off the floor. Do not pkill / steal tunnels.

- **Bare Go2 hop 202 then 401 / no jump** (2026-09-19)
  Chat Apply hop is `OpenRAL/rskill-zero-go2-hop-fp32`. Cricket
  `/openral/rskills` had only `rsl-rl-onnx-go2-hop-flat` (mjlab crouch)
  and `mock.py` had no `gait: jump`. Runner accepted then
  `ROSConfigError` HF Hub 401 on the scripted id. Fix: laptop Load
  copies the scripted hop + jump mock (`sync_cricket_scripted_hop`)
  then reloads. HTTP 202 is not hop — need no 401 and feet leave
  the floor. Do not pkill / steal tunnels.

- **`/simple` chat FAULT `ACQUIRE_API_URL is empty`** (2026-09-19)
  Walk / hop on UNIT GO2 after Railway Jev is live. Laptop
  `openral dashboard` was started with write-controls only — no
  `ACQUIRE_API_URL` / `ACQUIRE_API_KEY`. Chat binds the client at
  process start (`client_from_env`); there is no library default.
  Not a Railway Jev miss (`/health` `typesafe:on` is the sibling).
  Fix: `just dashboard-acquire-env` once (writes
  `~/.openral/dashboard.env` from Railway `acquire-api` `API_KEY`),
  then `just dashboard` / restart laptop `:4318`. The file is
  loaded into empty `ACQUIRE_API_*` only. Do not commit the key.
  Hard-refresh `/simple`. Do not pkill / steal tunnels.

- **`/simple` top video not in the viewport / looks like it never started** (2026-09-19)
  Stream was live (`/api/camera/top/stream` 200) but the tile was
  `aspect-square` below the fold, and CSS hid **connecting** because
  `<canvas>` is always in the DOM. Engine also unmounted the tile.
  Fix: `CAM_TOP` always fills leftover viewport (`flex-1` + absolute
  canvas `object-fit: cover`); placeholder until `has-mjpeg` / still.
  Rebuild `simple_ui` + hard-refresh `/simple`. Do not pkill / steal
  tunnels.

- **Hop does not leave the ground / weird shuffle** (2026-09-19)
  The mjlab hop ONNX only crouches (`air_ticks=0`) even with feet
  on z=0. Isaac hop `kp=20` sags calves on this torque HAL.
  Dashboard hop is now `OpenRAL/rskill-zero-go2-hop-fp32` (scripted
  crouch-extend-tuck, walk PD; measured `air_ticks≈45`, foot ≈0.25 m).
  Reload Bare/Z1 so cricket picks up `mock.py` + the hop rSkill YAML.
  HTTP 202 is not a hop. Do not pkill.

- **Hop 202 then stand still** (2026-09-19)
  Cricket `/openral/rskills` had no hop dir. Runner 202'd then
  `ROSConfigError`: HF Hub 401 on
  `OpenRAL/rskill-rsl_rl_onnx-go2-hop_flat-fp32` (repo missing). After
  copying `rskills/rsl-rl-onnx-go2-hop-flat`, the **old** cricket
  `rsl_rl_onnx` still rejected `gait_phase_2` and did not fetch
  `onnx_url`. Fix: copy this-branch adapter + `policy.onnx` (~1.6 MB
  from Renkunzhao raw URL) + reload Bare/Z1. HTTP 202 is not hop
  motion — need `skill_built` + `z_span` ≳ 5 cm. `ros2 topic echo`
  without `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` looks like a dead
  graph (only `transition_event`). Do not pkill.
- **UNIT change does not switch the dog** (2026-09-19)
  Laptop `POST /api/demo/load` ran `_spawn_scene_reload` on the Mac
  (nothing to kill; laptop `:4318` never dies). `/simple` then treated
  laptop `/healthz` as the new twin, or snapped UNIT back to cricket
  `robot_id` (occupantRobot: loading + live≠stored → live). Camera
  stayed Go2+Z1. Fix: laptop load `docker exec`s
  `/tmp/openral_demo_relaunch.sh` on cricket; UI waits for
  `/api/config` `robot_id`; loading keeps the target. Restart laptop
  dashboard + hard-refresh `/simple`. Do not pkill / steal tunnels.
  Cold reload is 30–90 s. Do not End Cricket to “switch”.

- **Bare Go2 `/simple` top ~1 Hz while Go2+Z1 looks live** (2026-09-19)
  Not a second encoder. Cricket `/openral/robots/go2/robot.yaml` had
  **only `front`** (no `top`, no `sim_render`). `/simple` shows `top`
  only, so CAM_TOP was a leftover ~0.9 Hz still; `front` ran 9–35 Hz
  (cheap snout). Cricket `go2_z1` yaml already had `front` + `top`.
  Fix: copy this-branch `robots/go2/robot.yaml` + HAL (`read_images`
  skips `sim_render: false`) onto `/openral`, Load Bare Go2. After
  reload: `top` 15–32 fps / 640 px, `front` no thumb. Hard-refresh
  `/simple`. Do not add EGL cameras / do not pkill / do not steal
  tunnels.

- **`/simple` camera hitch / 3 fps slideshow** (2026-09-19)
  `<img src=multipart>` fires spurious `error`; remounting `?r=`
  aborted the live stream. Forever `latest.jpg` poll (and operator
  `/` at 300 ms) shared the HTTP/1.1 pool with MJPEG. Fix: `/simple`
  fetch + canvas keep-latest (`lib/mjpeg.ts`, `createImageBitmap`);
  still poll stops after the first frame. Operator `/` does not
  remount after `naturalWidth > 0`; still interval 1.5 s.
  `dashboard.js?v=cam8`. Rebuild + hard-refresh `/simple`. Do not
  add an EGL camera or steal tunnels.

- **`/simple` cameras stuck on connecting / conn pill waiting…** (2026-09-19)
  Graph was live on cricket (`go2` / `go2mujocohal`, later Go2+Z1;
  MJPEG flowing on `:14318`). Laptop `:4318` is an empty collector.
  Stacked bugs: (1) tiles `GET /api/demo/cricket` every 3 s (SSH
  `pgrep`, ~4 s) before attaching `/stream`; cricket status also
  **lies** `graph_running=false` because hostname is `brev-d4dyyrsd1`
  (not `*cricket*`) and `OPENRAL_CRICKET_ROLE` was unset; (2) laptop
  `/latest.jpg` waited on cricket's Sep 17 **404** `/latest.jpg`
  before the tunneled `/api/state` thumb; MJPEG TTFB over the tunnel
  left a gray tile; stream `error` froze **no signal**; (3) conn pill
  read laptop `/api/state` (`last_ingest=0`); (4) `/api/config`
  `robot_id` was empty so UNIT did not match the live twin. Fix:
  tiles attach `/stream` plus a sibling still; laptop stills use the
  cached state thumb first; MJPEG
  seeds that still then splices cricket `/stream`; overlay ingest +
  `cricket_live_robot_id` on config; occupancy prefers tunneled
  ingest; attach/relaunch export `OPENRAL_CRICKET_ROLE=host`. Restart
  the **laptop** `openral dashboard` only (and hard-refresh `/simple`
  after the simple-ui export). Do not steal `:14318`/`:8765` tunnels
  or pkill the graph. Cricket `app.py` on the box is still Sep 17
  until the next Bare/Z1 reload.
- **`/simple` Calibrate “calibrates a lot” / `demo.reset_to_pose_failed`.** (2026-09-19)
  The UI used `RECAL_WAITS_MS` (6 POSTs). Backend `stand_response` also
  called ResetToPose when cricket was already disconnected. Now: one
  `POST /api/demo/recalibrate`, 503 once (`cricket is disconnected`),
  no ResetToPose on a dead graph. Restart `openral dashboard` after
  the Python fix. Retry is a new Calibrate click.
- **`/simple` Stop OP_FAULT `execute_rskill cancel failed`.** (2026-09-19)
  `POST /api/demo/stop` treated CancelGoal `return_code` 1 as fatal.
  rclpy cancel-all (zero UUID) with nothing cancelable is
  `ERROR_REJECTED`, not `ERROR_UNKNOWN_GOAL_ID`. Apply-while-running
  and Stop after a finished hop/walk then 502'd. Fix: codes 0–3 and
  `ERROR_*` names are success; a broken dump still Hub-stands; dead
  graph is 503 once. Restart laptop `openral dashboard`. Retry is
  Stop (or Apply). No E-STOP / no pkill.

- **`/simple` Calibrate OP_FAULT `ros2` not on PATH.** (2026-09-19)
  Laptop `:4318` is an empty collector — no local ROS. Calibrate /
  Apply used to `shutil.which("ros2")` and return *source the
  workspace*. That PATH hint is wrong on a laptop. Graph/SSH/credits
  down → **cricket is disconnected** (or `start_error`). Graph up →
  SSH `docker exec` `ros2` on cricket. Restart `openral dashboard`
  after the Python fix. Retry is Calibrate.
- **`/simple` Start engine does nothing.** Click must paint
  **Starting…** and `POST /api/demo/cricket/start`. Two backend traps
  (2026-09-19): (1) `GET /api/demo/cricket` used to sync-SSH
  `cricket_graph_running()` on the uvicorn loop (~12s), so the POST
  sat in the queue until that GET finished; (2) idle auto-End left
  `end_in_progress` true forever (idle loop returns after one End),
  and `bootAsync` awaited that slow GET then `paint('idle')` wiped
  connecting. Fix: occupancy SSH is `asyncio.to_thread`; operator
  Start `reset_end_guard()`s; boot probes graph in the background and
  never overwrites connecting. Brev credits/quota/billing and SSH
  failures must show as OP_FAULT — not "failed to schedule". Retry is
  the same CTA.
- **`/simple` green “Start Cricket already in progress” with no credits.**
  (2026-09-19) Live `POST /api/demo/cricket/start` returned 202
  `{detail: "Start Cricket already in progress"}` after `brev start`
  printed `there was issues with your credits You have run out of
  credits visit the settings page to purchase more`, then
  `cricket.laptop_start ssh never came up`. `begin_start` stayed true;
  the UI treated any 202 as kind=ok. Fix: that path is 400 when
  `start_error` is set; 202 in-flight is not painted green; the page
  polls `start_error`. **Restart `openral dashboard`** so the new
  Python loads. Retry is Start engine.
- **`brev start` refused: out of credits.** `brev ls` shows cricket
  STOPPED / SHELL NOT READY; `brev start abundant-turquoise-cricket`
  exits 1 with `there was issues with your credits You have run out of
  credits visit the settings page to purchase more`. No docker, no
  graph, no `:4318`/`:8765`. A laptop collector or `openral viz mujoco`
  cannot substitute — both need cricket OTLP. Buy credits in Brev
  settings, then Start Cricket (do not `brev start` in a loop).
  `/simple` now surfaces that brev text in the Alert.
- **Laptop WAITING / empty collector.** Bare `openral dashboard` (or
  `uv run` local) owns `:4318` → header WAITING, no robot, no cameras.
  Live twin is cricket `deploy sim --dashboard --foxglove`. Stop **only**
  the local collector; tunnel cricket `:4318` + Foxglove `:8765`; open
  `http://127.0.0.1:4318/` (prefer `127.0.0.1` over `localhost` if
  IPv6 wedges); hard-refresh. Wedged tunnel (listen up, HTTP timeout)
  → kill those tunnel PIDs only and re-open (`ControlMaster=no`).
- **`brev ls` RUNNING ≠ dashboard.** VM can be SHELL READY with
  `openral-jazzy-go2` **exited** and no graph. Do not `brev start`
  again and do not start a laptop collector. `docker start` the
  container, attach via `/tmp/openral_demo_relaunch.sh` if present
  (Go2+Z1 last occupant), then tunnel `:4318`+`:8765` (`ControlMaster=no`).
  `:14318` is only for when a local collector already owns `:4318`.
- **Black camera tiles / "waiting".** Main·front + Side·top always
  mount. Two causes: (a) overlay waiting on `img.onload` / multipart
  MJPEG never fires — tiles should start `is-streaming`; (b) JS
  `error` fallback to **dead `:14318`** while cricket is on `:4318`.
  Fix: same-origin retry, no `:14318` bounce on port 4318; cache-bust
  `?v=cam5`; hard-refresh. Proof:
  `/api/camera/top/stream` (dog) and `/api/camera/front/stream`
  (snout checkerboard+sky OK). Foxglove `ws://127.0.0.1:8765`.
- **Foxglove Problems: Connection failed `ws://localhost:8765` +
  WebSocket error + Layout sync 400 Invalid ID format.** Three
  separate things, not a dead graph. (1) Tunnel +
  `foxglove_bridge` were up (`foxglove.sdk.v1` → 101; legacy
  `foxglove.websocket.v1` → 400 that Studio reports as "not
  reachable"). Reopen
  `foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765`
  — never `localhost`, never `&layoutId=`. (2) "Invalid ID format"
  is Foxglove **cloud layout sync**, not ROS. A `foxglove://` URL
  with `layoutId=lay_0ecFylVWqq0HLLxN` (or a local UUID) 400s.
  Import `/tmp/openral_layout_go2.json` locally (Layouts → + →
  Import; `⌘⇧G`); do not sync that id. (3) Zombie
  `[foxglove_bridge] <defunct>` leftovers are normal after
  reloads; the live pid is the non-defunct `foxglove_bridge`.
  Do not relaunch the graph to clear the Problems tab.
- **LIVE + age 0 ms + dark crosshair wrap, no picture.** The HAL
  thumbs are fine (`/api/state` `thumbnail_jpeg_b64` shows the dog);
  MJPEG only emitted a part when JPEG *bytes changed*. A standing
  robot is identical JPEGs, so the stream sent **one** `--frame` and
  stalled. Browsers paint `multipart/x-mixed-replace` only after the
  next boundary, so the `<img>` stays empty while SSE paints LIVE /
  fps. **Code:** heartbeat every 0.2 s + sibling `img.camera-still`
  (`ensureCameraPixels` must **not** replace the stream `<img>` —
  that abort is the Bare Go2 3 fps slideshow). Hard-refresh `?v=cam5`.
  Heartbeat Python needs a graph reload. Front snout into an empty
  world is mostly black sky + checkerboard floor — healthy, not dead.
  Side · top is the dog.
- **Bare Go2 camera slideshow (~3 fps) after HAL JPEG fix.**
  `ensureCameraPixels` set `img.src` to a blob at 200 ms, aborting
  MJPEG (TTFB ~2.6 s so the still always won), then polled
  `/latest.jpg` forever; each GET cloned `snapshot()`. Stills now
  overlay; `/stream` stays; `/latest.jpg` uses `camera_thumb`.
  Hard-refresh `?v=cam5`. Python needs reload.
- **Recalibrate is the demo.** Go2+Z1: upright + `ARM_READY`
  `(0, 1.2, −1.0, −0.4, 0, 0)` sticky hold (this-branch `go2_z1.py`).
  Recalibrate 200 + arm flails → old HAL. Apply walk **only after**
  Recalibrate. Tip recovery: **Stop** then Recalibrate (not E-STOP;
  "requantize" = Recalibrate).
- **Apply stands still / "doesn't move".** Two causes: (a) picker
  selected `arm_ready` (`OpenRAL/rskill-zero-go2_z1-arm_ready-fp32`, 2 s
  Hub hold) — not a gait. Must be
  `rsl-rl-onnx-go2-velocity-flat` /
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`. Prefer walk after
  Recalibrate; hard-refresh for preferWalk force. (b) **second skill**
  — Apply while a walk is already running queued behind 60 s, and a
  reused resident skill skipped `activate()` so `last_action` / horizon
  leaked (dog stands). Fix: Apply stops the current skill first; runner
  `reset_resident_episode` on reuse. Hard-refresh `?v=cam6`. Proof walk
  can move metres in ~8 s while arm stays ready.
- **Walk 502 `walk dispatch failed` / `action server rejected the
  goal`.** End Cricket / E-STOP latched the **skill runner**;
  Recalibrate may clear the **kernel** (`latched:false`) but not the
  runner. Fix: **Reset e-stop** / `POST /api/estop_reset` (needs
  persistent `EstopPublisher`), then Apply. Reasoner API key is **not**
  required for walk / load / Recalibrate (configure FAILURE is noise).
- **Long load / idle / deadline.** Bare/Z1 load ~30–90 s cold reload —
  not the reasoner. Do not End Cricket mid-demo. Idle 15 min
  (`OPENRAL_CRICKET_IDLE_S`) auto-Ends. Walk 60 s then freeze-falls —
  **Stop** first. Mid-gait tip on Go2+Z1 can happen well before 60 s.
- **Occupancy / hostname lie.** One graph per `ROS_DOMAIN_ID`.
  Character-class `pgrep` (`[o]penral deploy sim`). Never `pkill -f
  'openral deploy sim'` and never match `/tmp/openral_demo_relaunch.sh`.
  Cricket hostname can lie `graph_running=false` / `role=laptop` while
  the graph is up — do not End/Start from that.
- **Arm "physics" looks soft — expected.** Sticky control hold +
  bare-Go2 rsl-rl policy vs Z1 mass (`arm_mass_scale`); not a broken
  sim. Do **not** add heading lock as the demo path — Recalibrate →
  walk Apply is the path.
- **Dashboard crash, Foxglove still up.** `HERO_CAMERA_KEYS` import
  killed cricket dashboard (`store.py` lagged). Restore dashboard
  modules; do not restart Foxglove first.
- **Start Cricket no-op on a cold VM.** Laptop Start must `brev start`
  + `docker start` + tunnels + attach. Start on cricket cannot
  `brev start` a stopped instance.
- **`brev start` says "ready" before sshd takes connections.** Right
  after the spinner prints *Your instance is ready!*, ssh dies with
  `Connection closed by <gateway> port 56280` — twice, ~70 s apart.
  Not a cert or config fault: `brev ls` still showed `SHELL NOT READY`.
  Wait for `SHELL READY` in `brev ls`, re-mint (`brev mint-cert --env
  d4dyyrsd1 --port <nport> --linux-user ubuntu --out-key
  ~/.brev/ssh-certs/d4dyyrsd1`), then connect. Do not conclude the VM
  is broken and restart it.
- **`/simple` OP_FAULT `Connection closed by <gateway> port 56280`
  while the twin is live.** (2026-09-19) Same sshd race latches
  `start_error`. Graph + `:8765`/`:14318` tunnels can come up after;
  `GET /api/demo/cricket` still returned the close (`graph_running`
  true). `/simple` Start treated any `start_error` as fatal — even a
  `200 already_running` body that still carried the latch — and
  Calibrate preferred `start_error` over occupancy so Apply was
  blocked. Fix: status + demo-block **clear** `start_error` when
  `graph_running`; Start poll / `already_running` prefer the live
  graph. Do **not** `brev start` again and do not steal tunnels.
  Restart laptop `openral dashboard` + hard-refresh `/simple`.
- **`/simple` Start engine (not OP_FAULT) after a live twin.**
  (2026-09-19) Cricket's own `--dashboard` idle clock (15 min,
  `role=host`, `halt_host=True`) End'd the graph while the laptop
  idle remaining was still ~14 min. Tunnel `:14318` still listened;
  HTTP RST; Foxglove TCP can still accept. `/simple` correctly
  paints OP_IDLE / Start engine (`start_error` null). Recovery is
  laptop **Start engine** (docker + attach, reuse tunnels). Do
  **not** `brev start` — VM stayed RUNNING. Do not steal tunnels.
- **Classic `/` vs `/simple` — one operator page.** (2026-09-19)
  `GET /` now serves the simple dashboard (`/simple` alias). Classic
  `index.html` is not served. Cricket attach/reload exports
  `OPENRAL_CRICKET_IDLE_S=0` so the in-graph collector is not a
  second idle End. Laptop still 15 min. Idle playhead follows ingest
  / `graph_running`. Restart laptop dashboard + hard-refresh
  `http://127.0.0.1:4318/`.
- **A healthy graph can look WAITING if you probe the wrong keys.**
  `GET /api/state` has **no** `robot_id` / `hal_kind` at top level —
  those are `/api/config` fields. Liveness is
  `identity["openral.hal.robot.model"]` +
  `identity["openral.hal.adapter"]`, `services[]`, and
  `now_unix - last_ingest_ts` (≈0 when live). Cameras are not a
  `cameras` key either — read `events[]` `sensors.read_latest`
  (`openral.sensors.width/height/age_ms`) or just hit
  `/api/camera/{front,top}/stream`. Probing `d.get("robot_id")` on
  `/api/state` returns `None` on a perfectly live twin.
- **Fresh Go2+Z1 deploy may ship NO `/compressed` topics.** A clean
  relaunch on the cricket bind-mount advertised only raw
  `/openral/cameras/{front,top}/image` — `ros2 topic list | grep
  compressed` empty, `pgrep -af republish` empty. That was the ~18 MB/s
  raw-RGB8 tunnel stutter, and the generated layout points at
  `/compressed`, so Image panels stay blank. **Code fix (this branch):**
  `SimSensorBridge` publishes `/image/compressed` itself (dashboard
  JPEG, one encode) and sim `--foxglove` no longer spawns
  `image_transport republish` (that subscribed the raw topic and forced
  the ~900 KiB GIL copy). A graph started *before* this HAL still needs
  the old manual republish (~11 Hz JPEG): `ros2 run image_transport
  republish raw compressed --ros-args -r
  in:=/openral/cameras/<cam>/image -r
  out/compressed:=/openral/cameras/<cam>/image/compressed`, one per
  cam, `nohup setsid`. Cricket's `/openral` checkout is **not** the
  Mac's until the bind-mount picks this up — reload Bare Go2 / Go2+Z1
  after the HAL lands.
- **Mid-gait tip at ~14 s / ~3.5 m is REPRODUCIBLE and unexplained.** Live
  Go2+Z1 walk (Recalibrate → Apply, `vx=0.35`, `arm_mass_scale: 0.01`)
  tips 3/3 at t=13.2–15.9 s, x≈3.4–3.7 m. Signature every time: `y`
  drifts steadily **negative** (−0.05 → −0.2 → −0.6) for ~13 s, then a
  yaw spike (`/odom` `twist.angular.z` → −1.17, −1.66 rad/s) and a roll
  to 70–104° in under 2 s. Not the 60 s deadline. **Headless the same
  checkpoint never falls** — 8/8 × 30 s at both `arm_mass_scale` 0.01
  and 1.0, at `vx` 0.35 and 0.5. Eliminated by measurement, do not
  re-litigate: arm mass scale; arm pose (headless); the 0.35 vs 0.5
  command; `last_action` reset (adapter resets per *episode*, not per
  step); control-cadence jitter **and** systematic shift (survives 8–40
  ms/tick, 5/5 each); safety clamping (zero clamp/violation events);
  observation fallbacks (zero `_warn_obs_fallback` lines, so
  `base_ang_vel`/`projected_gravity` are being supplied); scene props
  (none in `go2_z1_walk.yaml`); floor edge (staged plane is `size 0 0`
  = infinite); **twist frame mismatch**; **proprio staleness**. The last
  two were the standing leads and both are now dead — see the two
  bullets below. **It is also intermittent, not 3/3:** two walks on
  2026-09-18 ~14:30Z went 34 s / 5.5 m with no tip (same leftward
  signature, `dy≈−1.3 m`). Overall ~3 tips in 5 live walks. Do not
  quote "reproducible 3/3" as if it were deterministic.
- **Twist frame mismatch is NOT the cause (code read, no relaunch).**
  `base_twist` passes **verbatim** through every hop — `Go2MujocoHAL`
  → `/odom` → `_on_odom` → `pose_twist_from_odometry_fields` →
  aggregator → `WorldState` → policy. No transform anywhere. And the
  HAL docstring is explicit that free-joint `qvel[3:6]` is already in
  the **child (base) frame**, i.e. the Isaac Lab `base_ang_vel` term
  the checkpoint trained on. Also: the runner reads
  `aggregator.snapshot()` **in-process** and never subscribes to
  `/openral/world_state_fast`, so `publish_rate_hz_fast` (30 Hz) is
  dashboard-only and is NOT in the policy's observation path.
- **Proprio staleness is real and quantified — but NOT what tips it
  live.** Headless, delaying the whole proprio bundle gives a sharp
  stability cliff for this checkpoint: age 0 ms → 8/8 survive, 20 ms
  (1 tick) → 8/8, **40 ms (2 ticks) → 1/8**, 60 ms → 0/8, 80 ms → 0/8.
  This is the measured justification for `publish_rate_hz: 200.0` /
  `odom_publish_rate_hz: 200.0` in `scenes/deploy/go2_z1_walk.yaml`
  (previously only a comment) — **do not lower those rates.** Measured
  live during a walk, the aggregator's cached proprio age is
  **median 5.1 ms, p90 10.2 ms, max 41.6 ms** (matched externally
  against the 200 Hz `/joint_states` history, n=469), so the live path
  sits in the safe 8/8 band and staleness is excluded. Side
  observation: `/openral/world_state_fast` publishes at **11.2 Hz**
  against its 30 Hz timer while `/odom` runs at 197 Hz — the runtime
  node's publish work is starved, but it does not touch the policy
  path.
- **A tucked arm is NOT the fix for that tip.** Worth knowing because
  the first live trial is misleading: tucked
  `(0, 0.15, −0.365, 0.684)` walked 30 s / 6.09 m once, then tipped in
  2 of the next 3 (24.8 s, 13.2 s). 2/4 is noise, not a fix. Ship
  nothing on one live rollout — the same trap as the headless anecdote.
- **Camera lag = still-poll killing MJPEG, then raw RGB8.** After the HAL
  JPEG path, Bare Go2 tiles were still a slideshow because
  `ensureCameraPixels` replaced the MJPEG `<img src="…/stream">` with a
  blob still at 200 ms (MJPEG TTFB was ~2.6 s, so the still always
  won) and then polled `/latest.jpg` forever at 300 ms — ~3 fps — while
  each GET cloned `snapshot()`. **Fix:** stills paint on a sibling
  `img.camera-still`; the stream `<img>` keeps `/stream`; `/latest.jpg`
  uses `camera_known` / `camera_thumb`; HAL JPEG shrink is BILINEAR +
  Pillow `rotate_180`. Hard-refresh `?v=cam5`. Graph reload picks up
  Python. Do **not** touch `enable_octomap_kernel_check`. RTF can still
  cap fps (physics). Tunnel bandwidth is not the bottleneck
  (MJPEG 0.05–0.17 MB/s).
- **Camera lag used to also be raw RGB8 serialize + extra JPEG.**
  `_rgb8_payload` is a single copy; raw Image publishes only while
  subscribed; sim HAL publishes `/compressed` from the dashboard JPEG
  (one encode). That HAL path still matters after reload.
- **Nested-quote `bash -lc "…python…"` mangles the command.** A
  `docker exec … bash -lc "…"` carrying embedded Python/JSON died with
  `unexpected EOF while looking for matching '"'` and a zsh
  `no such file or directory`. Use the documented
  `docker exec -i openral-jazzy-go2 bash -s` **heredoc** path for
  anything with quotes. Also: `set -u` in such a script breaks ROS
  sourcing (`AMENT_TRACE_SETUP_FILES: unbound variable`) — leave it off.

## Current beliefs (2026-09-19)

- **Start the app when asked:** run `scripts/start-app.sh` this turn
  (reuse `:4318/healthz`, else `just dashboard`, then
  `POST /api/demo/cricket/start`). Do not print the command and wait.
  Docs: `docs/quickstart/dashboard.md`.
- Host **now:** Brev `abundant-turquoise-cricket` **RUNNING** / SHELL
  READY (L40S). Occupant Bare Go2 (`go2mujocohal`). Operator UI is
  **`GET /simple` only** — `GET /` is 307. Laptop Start from STOPPED
  (`POST /api/demo/cricket/start` 202) brought VM + graph + tunnels
  (~70 s, no second `brev start`). Cricket host idle is off
  (`OPENRAL_CRICKET_IDLE_S=0`). Tunnels ssh 88656 (`:8765`+`:14318`)
  — do not steal. Laptop collector `:4318` overlays ingest. Open
  `http://127.0.0.1:4318/simple`. `ros2` CLI needs
  `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`.
-   Native MuJoCo dog on the laptop is `openral viz mujoco --dashboard
  http://127.0.0.1:4318` (polls `GET /api/qpos`, `mj_forward` only).
  Not another cricket EGL camera. Go2+Z1 needs
  `--robot robots/go2_z1/robot.yaml` so composed nq matches. WASM is
  backlog. Durable: [[analyses/mujoco-render-without-lag]].
- Simple dashboard is `http://127.0.0.1:4318/simple` (Next.js 16 + shadcn
  New York, Zappi stack). Start engine → **Load the unit** (empty
  UNIT; live occupant wins over sessionStorage) → Calibrate (one
  POST, **Calibrating…**; no skill on that embodiment yet) → Apply
  selected skill. Failures stay on the
  step (Alert); retry is the same CTA. Never auto-walk. Abort is
  Stop, not End Cricket. `/simple` has no link back to `/`. Engine
  screen has no pickers; **top** fills leftover viewport on every
  step. Live steps add UNIT + SKILL above the tile and overlay LIVE.
  (fetch + canvas MJPEG, not `<img src=multipart>`).
  Start after idle auto-End is recovery, not a no-op.
  Laptop Calibrate/Apply/Stop must SSH `ros2` into cricket; graph down is
  **cricket is disconnected** (503 once, no ResetToPose retry), never
  a local PATH hint. Stop cancel-all is idempotent (`ERROR_REJECTED`
  = nothing to cancel) and still Hub-stands. Header primary is Start /
  Load / Stop only. Load auto-stands so Apply is ready. Footer **RESET** (`#reset`) is
  `POST /api/demo/recalibrate`. `#go2-chat` is a right sidebar (`lg:w-80`), not a
  sticky bottom bar; `POST /api/chat` is Acquire probe/ask (does not
  publish `/openral/prompt`). Waiting on Acquire is `// pulling`
  shimmer; tokens Streamdown `isAnimating` + block caret.   Fit/adapted
  cards have `#chat-apply` (**Apply it** / hop). Click runs the skill
  (APPLYING… when load already stood; STANDING… only if not); the same button is STOP /
  STOPPING… while running (`POST /api/demo/stop`). Adapt-offer has
  **Adapt it**; remap keeps the walk prompt. Chat Apply runs immediately
  when load already stood. Conn `waiting…` shimmers; camera connecting
  is unchanged. 404 is CHAT_FAULT in the pane.
  `/simple` chat on laptop `:4318` loads
  `~/.openral/dashboard.env` (`just dashboard-acquire-env` once).
  Empty URL is FAULT. Railway Jev (`ACQUIRE_TYPESAFE` +
  `TYPESAFE_API_KEY`) is already on (`/health` `typesafe:on`).
  Bare Go2 hop is gym spring_jump
  `OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32`.
  Laptop Load syncs that package + this-branch `rsl_rl_onnx.py` onto
  cricket (old adapter cannot load frame-major / joystick A).
- Host (earlier today, stale until credits): Brev was RUNNING / SHELL READY
  (L40S). Operator "start the dashboard and cricket" (2026-09-18
  ~12:18Z): VM, container, graph, and Mac tunnels were **already up** —
  no `brev start`, no `docker start`, no relaunch, tunnels not stolen
  (`ControlMaster=no` ssh pid 89791, up ~3.4 h, `:4318`+`:8765`). No
  local collector. Live twin is **Bare Go2** (`go2_walk.yaml` /
  `go2mujocohal` / `robot=go2`), ingest age ~0.02 s, write-controls +
  demo-controls on, MJPEG `front`/`top` flowing, Foxglove `:8765` open.
  Open `http://127.0.0.1:4318/?v=cam4` (not `:14318`). `/api/config` cricket
  `role=laptop` is the known hostname lie — do not End/Start from that.
  Did **not** Recalibrate or Apply. Idle auto-End is 15 min; do not End
  Cricket mid-demo.
  Operator "I dont see the cameras" (2026-09-18 ~12:28Z): tiles said
  LIVE / age 0 ms / 10 fps + 1 fps but showed only the dark wrap +
  crosshair. HAL thumbs were live (`/tmp/openral_cam_top.jpg` is the
  dog). Cause: MJPEG emitted one part then stalled on identical JPEGs;
  browser never got the next `--boundary`. Copied `dashboard.js` +
  `index.html` (`?v=cam4`) onto cricket `/openral` (no graph restart).
  Still fallback polls `/api/state` thumbs until heartbeat Python
  lands on reload. Hard-refresh `?v=cam4`. Front is mostly black sky.
  Earlier today the occupant was Go2+Z1; someone since loaded Bare Go2
  (container Up ~3 h, graph argv `go2_walk.yaml`). Cricket's `/openral`
  is still **pre-fix** for Z1 spawn (`_home_targets()` = menagerie
  `home`); if they switch back, Recalibrate before Apply walk.
  `ROS_DOMAIN_ID=77`. Bridge `ws://127.0.0.1:8765`. Prefer
  `http://127.0.0.1:4318/` over `localhost`. Cloud+browser **is** this
  tunnel; there is no public URL. Do not bind dashboard `0.0.0.0` on
  cricket. Durable: [[analyses/cloud-browser-needs-tunnel]].
- Live scene **now:** Bare Go2 `go2_walk` / `go2mujocohal`
  (write-controls on). Dashboard live camera is **`top` only**
  (`front` is `sim_render: false` — no fps / no thumb). Foxglove
  Image on `/compressed`. The "Bare hitch vs Z1 perfect" gap was
  cricket `go2` yaml missing `top` (Z1 yaml already had it).
  The slideshow was Bare Go2 / the 14:51Z graph (1 Hz stills + raw RGB8
  ~18 MB/s saturating the laptop tunnel). **Code fix:** sim HAL publishes
  `/compressed` natively and skips the raw RGB8 copy when Foxglove is
  the only viewer. Loading Bare Go2 on this branch after a graph restart
  should not bring the stutter back; re-import that robot's layout onto
  `/compressed`. **Second skill stood still:** resident reuse skipped
  `activate()` (`last_action` / horizon leak) and Apply queued behind
  the 60 s walk. Runner now `reset_resident_episode` on reuse; dashboard
  Apply stops first. Hard-refresh `?v=cam6`. Graph reload for the runner. "Doesn't move" was
  Apply `arm_ready` (2 s hold), not Bare / not 502. Proved rsl-rl **202**
  → dxy≈4.89 m in ~8 s; arm stayed `ARM_READY`; Stop + Recalibrate →
  upright z≈0.253 unlatched. Hard-refresh `:4318` (`?v=cam3`), picker
  rsl-rl, Recalibrate → Apply → **Stop** before 60 s. Mid-gait tip risk
  still real. Do not End / E-STOP mid-demo. Arm "soft physics" is
  expected (sticky hold + bare-Go2 policy vs Z1 mass). No heading lock
  as the demo path.
- Session traps filed in Catalog: empty laptop collector WAITING;
  black tiles = onload and/or dead `:14318` fallback; walk 502 =
  runner estop latch → `POST /api/estop_reset`; reasoner key not
  needed; load 30–90 s; idle 15 min auto-End; one graph /
  character-class pgrep / never pkill relaunch wrapper.
- Demo controls: Bare Go2 auto-stands after load (no auto-walk);
  Go2+Z1 asks Recalibrate first. Recalibrate =
  `POST /api/demo/recalibrate` → `/openral/go2_z1/reset_to_pose`
  (Bare: `/openral/go2/…`). **Stop** cancels without e-stop then
  Hub-stands. **Start Cricket** (laptop) = brev + docker + tunnels
  (`:8765`, cricket UI `:14318` when local keeps `:4318`). **End
  Cricket** = cancel + kill graph (character-class) + brev stop.
  Healthy stand `world→base` z≈0.27. Walk 60 s then freeze-fall
  unless Stop. Reload via `/tmp/openral_demo_relaunch.sh`.
- Root TF is **`base`**, not `base_link`. Missing follow frame → empty 3D.
  A live identity `base → base_link` alias may be published; do not assume it
  survives a restart.
- `/openral/cameras/front/image` looks **out** from the snout. It cannot
  show the body (black sky / gray floor is a healthy empty world).
- Foxglove **Image** panel ≠ **3D** panel. The dog is only in 3D. `top` is
  the third-person Image. `--foxglove` now publishes `/compressed` from the HAL (sim) and the
  generated layout points there — raw 640×480 RGB8 was ~18 MB/s for two
  cameras over the laptop tunnel. Mac Studio `openral_layout_go2`
  (`lay_0ecFylVWqq0HLLxN`) was rewritten 2026-09-17 to `top` then `front`
  `/compressed`. Live cricket graphs started before this HAL still need
  the two `image_transport republish` nodes. JPEG `/compressed` flowing
  ~7 Hz on those old graphs. Re-import after the next generate.
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
- Official open (desktop): `open "foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765"`
  — no `layoutId` (cloud sync 400 Invalid ID format). `app.foxglove.dev`
  still needs `ws://localhost:8765` (mixed-content exception is localhost-only).
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
# 0. Start the app when asked (laptop collector + cricket attach)
.agents/skills/go2-foxglove-view/scripts/start-app.sh

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

open "foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765"

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

- Print `just dashboard` / `start-app.sh` and wait for the operator
  when they asked to start the app — run it this turn.
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

- 2026-09-19: Operator: update docs so agents start the app when
  asked. Mandatory: run `scripts/start-app.sh` this turn (reuse
  `:4318/healthz`, else `just dashboard`, then cricket Start). Do not
  print the command and wait. Docs:
  `docs/quickstart/dashboard.md`, `CLAUDE.md` pointer. No `brev start`
  / no pkill / tunnels not stolen.

- 2026-09-19: Dashboard hop Apply swapped to gym spring_jump
  (`OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32`). Load Bare/Z1 so
  cricket gets the rSkill + this-branch adapter. Hard-refresh `/simple`
  after simple-ui rebuild. Restart laptop `:4318` for Python. No
  `brev start` / no pkill / tunnels not stolen.

- 2026-09-19: Operator: load should already stand; footer Reset not
  Stand. `/simple` Load waits occupant then `POST /api/demo/recalibrate`
  so Apply is APPLYING… not STANDING…. Footer `#reset` is the same
  Recalibrate (RESETTING…). Hard-refresh `/simple` after simple-ui
  rebuild. No `brev start` / no pkill / tunnels not stolen.

- 2026-09-19: Operator: Apply doesn't work / needs loading.
  `#chat-apply` now calls `onApply`/`onStop` (not only emit press),
  hydrates SKILL, paints APPLYING… (STANDING… only if not already
  stood) then STOP /
  STOPPING…. Remap task is the walk prompt. Hard-refresh `/simple`.
  Restart laptop `:4318` for Python. No `brev start` / no pkill /
  tunnels not stolen.

- 2026-09-19: Operator: hop skill doesn't work for bare Go2.
  Apply hop 202 then Hub 401 on `OpenRAL/rskill-zero-go2-hop-fp32`
  — cricket had only the mjlab ONNX hop + old mock (no jump).
  Copied scripted hop + jump mock; Load Bare Go2. Next hop
  `skill_built` (no 401). Laptop Load now syncs those files.
  No `brev start` / no pkill / tunnels not stolen.

- 2026-09-19: Operator: Stand/reset stays, not on top. Header
  `#primary` is Start / Load / Stop only. Footer `#reset` is
  `POST /api/demo/recalibrate`. Load auto-stands. Chat json-render **Apply it**
  runs immediately when stood.
  Hard-refresh `/simple`. No `brev start` / no pkill / tunnels not
  stolen.

- 2026-09-19: Operator: text streaming then shimmer while pulling.
  Streamdown `isAnimating` + block caret after first tokens; `//
  pulling` CSS shimmer (no Magic UI package) while chat waits on
  Acquire and on conn `waiting…`. Camera connecting / CAM_TOP
  unchanged. Hard-refresh `/simple`. Apply-in-chat Button catalog
  is compile-only (chat.py has no CTA patches yet). No `brev start`
  / no pkill / tunnels not stolen.

- 2026-09-19: Operator: automate Acquire env. `openral dashboard`
  loads `~/.openral/dashboard.env` into empty `ACQUIRE_API_*`.
  `just dashboard-acquire-env` seeds it from Railway. `just dashboard`
  is write-controls + collector. No key in git. No `brev start` /
  no pkill / tunnels not stolen.

- 2026-09-19: Operator `/simple` chat FAULT after WALK FORWARD on
  UNIT GO2: `ACQUIRE_API_URL is empty`. Laptop dashboard had
  write-controls only. Restarted `:4318` with Railway
  `acquire-api` origin + `API_KEY`. Jev already on. No key in git.
  Hard-refresh `/simple`. No `brev start` / no pkill graph /
  tunnels not stolen.

- 2026-09-19: Operator: video does not start / put it in the viewport.
  Stream was already 200. Tile was aspect-square below the fold;
  canvas in DOM hid connecting. `CAM_TOP` now always fills leftover
  viewport. Rebuild + hard-refresh `/simple`. No `brev start` / no
  pkill / tunnels not stolen.

- 2026-09-19: Operator: start it. VM was STOPPED / SHELL NOT READY;
  graph down; old tunnel 10738 defunct. One laptop
  `POST /api/demo/cricket/start` 202 (`brev start` + docker +
  tunnels + attach). ~70 s later RUNNING / READY, `graph_running`,
  Bare Go2, tunnels ssh 88656 (`:8765`+`:14318`). No second
  `brev start` / no pkill. Open `/simple`.

- 2026-09-19: Operator: comment root dashboard not to start. `GET /`
  is 307 `/simple`; banner prints `/simple`. Classic HTML not started.
  No `brev start` / no pkill.

- 2026-09-19: Operator: turn off the first dashboard; `/` is final.
  `GET /` == `/simple`. Classic HTML not served. Attach/reload
  `OPENRAL_CRICKET_IDLE_S=0`. Idle playhead follows ingest. No
  `brev start` / no pkill / tunnels not stolen. Restart laptop
  dashboard + hard-refresh `http://127.0.0.1:4318/`.

- 2026-09-19: Browser verify `/simple` after the 56280 latch fix.
  First paint was OP_IDLE / Start engine — cricket-host idle End
  had already SIGINT'd deploy-sim (`halt_host=True`); `:14318` RST;
  VM still RUNNING. Laptop Start attached Bare Go2; tunnels 10738
  reused. `/simple` then OP_UNIT / LIVE, UNIT Bare Go2, SKILL
  empty, Calibrate. Recalibrate POST 200. No OP_FAULT / no
  `brev start` / no pkill / tunnels not stolen.

- 2026-09-19: Operator OP_FAULT `Connection closed by 75.2.122.140
  port 56280`. Host RUNNING / SHELL READY; occupant Bare Go2;
  tunnels pid 10738 (`:8765`+`:14318`) left alone; `:14318` 200;
  `graph_running=true` with latched `start_error`. Known sshd race,
  not a dead VM. Status/demo-block now clear the latch when the
  graph is up; Start prefers `graph_running`. No `brev start` / no
  pkill / tunnels not stolen. Restart laptop dashboard +
  hard-refresh `/simple`.

- 2026-09-19: Operator "connect to cricket". VM STOPPED; laptop
  `:4318` up; idle `end_in_progress` was latched. POST Start 202
  then `start_error` credits. No tunnels. Did not loop `brev start`.
  Catalog: buy Brev credits, then Start engine.

- 2026-09-19: Operator "armed dog moves perfectly, bare has
  performance issues". Cricket `robots/go2/robot.yaml` had only
  `front` — `/simple` CAM_TOP was leftover ~0.9 Hz; Z1 yaml already
  had `top`. Synced this-branch yaml + HAL; Load Bare Go2. After
  reload: `top` 15–32 fps, `front` dead. Hard-refresh `/simple`.
  No extra EGL cam / no pkill / tunnels not stolen.

- 2026-09-19: Operator "go2 doesnt jump" / "not enough power".
  mjlab ONNX is a crouch; Isaac kp=20 sags calves. Dashboard hop
  is now scripted `rskill-zero-go2-hop-fp32` + walk PD. Reload
  Bare/Z1. No E-STOP / no pkill.

- 2026-09-19: Operator "start the app". Cricket already RUNNING /
  SHELL READY; occupant Bare Go2 (`go2mujocohal`); tunnels pid 21349
  (`:8765`+`:14318`) left alone; laptop `:4318` already serving
  write+demo (`/simple` 200, `graph_running=true`). Opened
  `http://127.0.0.1:4318/simple`. No `brev start` / no E-STOP / no
  pkill / tunnels not stolen. Earlier same-session `brev start` on
  a stopped VM still failed credits — credits are fine now (VM was
  already up). Cricket `/simple` 404 (old tree).

- 2026-09-19: `/simple` Stop OP_FAULT was `execute_rskill cancel
  failed`. Cancel-all with nothing cancelable is rclpy
  `ERROR_REJECTED` (1); the parser only allowed 0/2/3. Stop now
  treats 0–3 as success and still Hub-stands on a broken dump.
  Restart laptop dashboard. Retry is Stop. No E-STOP / no pkill.

- 2026-09-19: UNIT switch on laptop now SSHes cricket reload and
  waits for the new `robot_id`. Loading keeps the target. Restart
  laptop dashboard + hard-refresh `/simple`. No E-STOP / no pkill.

- 2026-09-19: Operator stopped the dogs-skills loop. Heartbeat
  sleeper 214135 (`sleep 600`) already completed ~13:00 UTC+4;
  healthz watcher 214131 completed; replacement 214136 was
  terminated_by_user. No leftover `sleep 600` / `14318/healthz`
  PIDs. Tunnel `ssh` pid 21349 (`:8765`+`:14318`) left alone. Last
  matrix tick 7 (Bare walk 4/7, Z1 good). Occupant Go2+Z1. `/simple`
  empty copy is Load the unit; UNIT follows live occupant. Did **not**
  re-arm a watcher or start tick 8. No E-STOP / no pkill.

- 2026-09-19: `/simple` top tile is fetch + canvas keep-latest
  (`lib/mjpeg.ts`). Do not remount `<img src=mjpeg>` on `error`.
  Still poll stops after the first frame. Operator `/` still interval
  1.5 s; `dashboard.js?v=cam8`. Hard-refresh `/simple` after export.
  Do not steal tunnels / do not pkill.

- 2026-09-19: Laptop camera pipeline: seed MJPEG from cricket
  `/api/state` thumb, sibling still on `/simple`, `/api/config`
  `robot_id` from tunneled identity. Do not steal tunnels / do not
  pkill. Restart laptop dashboard + hard-refresh `/simple`.

- 2026-09-19: Tick 7. Bare walk recovered 2.59 m upright — 4/7. Hop
  0.09 m. Z1 walk 1.62 m arm ready; hop 0.09 m; arm hold (Stop cancel
  timed out, Recalibrate stand OK). Left Go2+Z1. Watcher stayed up.
  No E-STOP / no pkill.

- 2026-09-19: Tick 6. Z1 walk 1.46 m upright arm ready; hop 0.08 m;
  arm hold. Bare walk started already down (z 0.059, dxy 0) after
  Recalibrate 200 — 3/6. Hop after Stop+Recalibrate 0.09 m upright.
  Left Bare Go2. Watcher fired on our Bare load — ignored. No E-STOP
  / no pkill.

- 2026-09-19: Tick 5. Bare walk upright again (1.73 m, z 0.35) —
  3/5. Hop 0.08 m. Z1 walk recovered (1.24 m, z held 0.355, arm
  ready); hop 0.09 m; arm hold. Left Go2+Z1 standing. Watcher stayed
  up through the Z1 reload. No E-STOP / no pkill.

- 2026-09-19: Tick 4. Bare walk **did not tip** (1.73 m, z 0.35) —
  so 2/4 upright. Hop 0.07 m. Z1 walk 1.00 m but z sagged 0.35→0.15
  (near-tip); hop 0.09 m; arm hold. Left Bare Go2. No E-STOP / no pkill.

- 2026-09-19: Third loop tick. Bare move tipped again (z→0.06,
  dxy 0.30 m) — 2/2 since the first 2.4 m pass. Bare hop
  z_span≈0.07 m upright. Z1 move 1.38 m arm ready; hop 0.09 m;
  arm hold. Left Go2+Z1. Watcher fired on our Z1 reload (healthz
  dip) — ignored, not a second matrix. No E-STOP / no pkill.

- 2026-09-19: 10 min loop retest. Z1 still good (move dxy≈2.13 m
  arm ready; hop z_span≈0.09 m; arm hold). Bare hop still
  z_span≈0.10 m. **Bare move tipped** this tick (z 0.32→0.06,
  dxy≈0.43 m / 8 s) — first pass had been 2.40 m upright. Stop +
  Recalibrate recovered; hop after that was clean. Occupant left
  Bare Go2. No E-STOP / no pkill / tunnels not stolen.

- 2026-09-19: Live both-dogs move/hop/arm on cricket `:14318`. Jev
  routed the three prompts. Hop needed in-tree copy + `policy.onnx` +
  this-branch adapter (Hub 401, then `gait_phase_2` reject). Bare
  move Δx≈2.40 m; hop z_span≈0.10 m. Z1 move 1.21 m arm ready; hop
  z_span≈0.08 m; arm held ready. Stop before 60 s. No E-STOP / no
  pkill / tunnels not stolen.

- 2026-09-19: `/simple` cameras stuck connecting / pill waiting…
  while cricket MJPEG was live. Tiles waited on SSH occupancy;
  laptop stills did not proxy; cricket `/latest.jpg` 404 (Sep 17
  dashboard). Laptop overlay + attach-stream-now. Restart laptop
  dashboard only. No E-STOP / no pkill / tunnels not stolen.

- 2026-09-19: `/simple` Calibrate OP_FAULT was `ros2` not on PATH on
  the laptop collector. Graph was down (credits / no signal). Laptop
  Calibrate/Apply now SSH `ros2` or fail **cricket is disconnected**.
  Restart dashboard. No E-STOP / no pkill.

- 2026-09-19: `/simple` showed green “Start Cricket already in progress”
  with no Brev credits. Live POST 202; brev stderr was out of credits
  then SSH never came up. 202 in-flight is not kind=ok; credits → 400
  OP_FAULT. Restart the dashboard process. No E-STOP / no pkill.

- 2026-09-19: `/simple` Start was a silent no-op after idle auto-End.
  GET cricket blocked the event loop (sync SSH); bootAsync painted
  idle over connecting; `_end_started` stayed true. Fix: to_thread
  occupancy, reset_end_guard on Start, fail-in-place credits/SSH,
  cameras only on live steps (both front + top). No E-STOP / no pkill.

- 2026-09-19: `/simple` dropped the Operator dashboard button. Start
  engine shows Loader2 + Starting…. No E-STOP / no pkill.

- 2026-09-19: `/simple` fails in place (Alert). 403 write-controls,
  unreachable dashboard, load/calibrate/walk/stop keep the step. Retry
  is the same button. No E-STOP / no pkill.

- 2026-09-19: `GET /simple` is a simple dashboard, not auto-play. Start
  engine → Bare Go2 / Go2+Z1 cards → Calibrate → Apply. Stop is Hub
  stand. No auto-walk. No E-STOP / no pkill.

- 2026-09-18: `GET /simple` rebuilt on Zappi's stack (Next.js 16,
  React 19, Tailwind v4, Geist, shadcn New York, `pnpm`). Static
  export under `/static/simple-ui/_next/`. No E-STOP / no pkill.

- 2026-09-18: `GET /simple` auto-play (shadcn New York). Cricket → Bare Go2
  8 s walk → Stop Hub stand → Go2+Z1 Recalibrate + 8 s walk → Stop.
  Abort is Stop, not End Cricket. Operator UI stays `/`. No E-STOP /
  no pkill.

- 2026-09-18 ~17:24Z: Operator "can you start the app". Cricket STOPPED
  / SHELL NOT READY; no tunnels; no local collector. `brev start`
  failed: out of credits. Did not launch laptop dashboard (WAITING).
  Catalog: buy Brev credits then Start Cricket. User terminal had an
  earlier successful `brev start` then later STOPPED; `openral viz
  mujoco` 127 without the venv. No E-STOP / no pkill.

- 2026-09-18: Native MuJoCo without lags is laptop `openral viz mujoco`
  + dashboard `GET /api/qpos` (HAL `ProprioFrame.qpos` on
  `hal.read_state`). Do not add cricket EGL cameras. WASM backlog.
  No E-STOP / no pkill.

- 2026-09-18 ~13:15Z: Operator Foxglove Problems tab (Connection failed
  `ws://localhost:8765`, WebSocket error, Layout sync 400 Invalid ID
  format). Graph was Go2+Z1, tunnel pid 89791 live, bridge
  `foxglove.sdk.v1` 101. Not a dead graph. Reopened
  `ws://127.0.0.1:8765` with no `layoutId`; regenerated
  `/tmp/openral_layout_go2.json`. Cloud layout sync 400 is Studio, not
  ROS — import that JSON locally. `open-viewer.sh` now uses 127.0.0.1.
  No relaunch / no E-STOP.

- 2026-09-18 ~16:50Z: Operator "the dog doesnt move on second skill".
  Two stacked bugs: resident walk reuse skipped `activate()` (leaked
  `last_action` / horizon — stand still or tick-1 complete), and Apply
  queued behind the 60 s walk. Fix: `reset_resident_episode` on reuse;
  demo Apply POSTs `/api/demo/stop` first. Hard-refresh `?v=cam6`.
  No E-STOP / no pkill.

- 2026-09-18 ~16:46Z: Operator "still issues with image performance".
  After the HAL JPEG path, tiles were still a slideshow: cam4
  `ensureCameraPixels` replaced `/stream` with a blob still at 200 ms
  (MJPEG TTFB ~2.6 s) and polled `/latest.jpg` forever (~3 fps), each
  GET cloning `snapshot()`. Fix: sibling `img.camera-still`, keep
  `/stream`, `camera_known` + `camera_thumb`, BILINEAR + Pillow
  `rotate_180`. Hard-refresh `?v=cam5`. Graph reload for Python.
  No E-STOP / no pkill.

- 2026-09-18 ~12:40Z: Operator "make the cameras visible / i dont see
  nothing". LIVE + age 0 + dark wrap, not WAITING. `/api/state` JPEGs
  were the dog (front checkerboard+sky, top Go2). MJPEG wire: one
  `--frame` then stall (identical standing-robot thumbs). Browsers
  wait for the next boundary. Fix: `_MJPEG_HEARTBEAT_S` 0.2 s +
  `/latest.jpg` + `ensureCameraPixels` still poll; cache `?v=cam4`.
  Copied JS/HTML onto cricket workspace (uvicorn serves that tree);
  did **not** relaunch. Hard-refresh `http://127.0.0.1:4318/?v=cam4`.
  Heartbeat Python needs a later graph reload. No E-STOP / no pkill.

- 2026-09-18 ~12:18Z: Operator "start the dashboard and cricket".
  `brev ls` already RUNNING/SHELL READY; `openral-jazzy-go2` Up ~3 h;
  graph already `go2_walk.yaml` (Bare Go2, not Go2+Z1). Mac tunnels
  `:4318`+`:8765` already held (ssh pid 89791, `ControlMaster=no`) —
  reused, not stolen. No local collector. Proof: healthz 200, identity
  `go2`/`go2mujocohal`, ingest 0.02 s, MJPEG `front`/`top` 200
  multipart, write-controls on, Foxglove listen ok. Opened
  `http://127.0.0.1:4318/` and `foxglove://…8765`. Did not Recalibrate /
  Apply / End / relaunch. Catalog already has brev RUNNING ≠ graph;
  this time RUNNING **was** the graph.

- 2026-09-18 ~15:24Z: Operator "performance issue in image camera of the
  bare dog". Root cause was the HAL copying two 640×480 RGB8 frames
  through rclpy (`bytes(arr.astype().tobytes())`, ~900 KiB GIL each)
  plus `image_transport` JPEG of that raw topic, while the dashboard
  MJPEG cloned the whole snapshot to read one thumb. Sim HAL now
  publishes `/image/compressed` from the dashboard JPEG (one encode),
  skips raw Image when nothing is subscribed, and MJPEG uses
  `store.camera_thumb`. Sim `--foxglove` no longer spawns republishers
  (they *were* the subscriber that forced the copy). Reload Bare Go2
  after this HAL lands on cricket; re-import layout onto `/compressed`.
  No safety check touched.

- 2026-09-18 ~14:30Z: Operator "is there a way to test it with
  typesafe?" Answer: TypeSafe (the Jev S2 sidecar) cannot — it is
  layer-4 text judgment, ≤1 Hz, no tensors, and per
  [[analyses/typesafe-in-openral]] "cannot make a walk skill balance";
  the walk is a direct dashboard apply it never sees. Static typing
  *was* the productive reading: `WorldState.base_twist` is an untagged
  `tuple[float × 6]` with no frame in the type, so a world-vs-body
  mix-up would pass `mypy --strict`. Chased that to a conclusion and
  **both remaining leads died.** (1) Frame mismatch: twist passes
  verbatim through every hop, HAL `qvel[3:6]` is already body-frame,
  and the runner reads the aggregator in-process (so the 30 Hz
  `publish_rate_hz_fast` is not in the policy path). (2) Staleness:
  found a real, sharp headless cliff — 20 ms proprio age 8/8, **40 ms
  1/8**, 60 ms 0/8 — whose 40 ms row reproduces the live signature
  (late scattered tips, big lateral drift), which retro-justifies the
  scene's 200 Hz publishers; then measured live age at **median 5.1 ms
  / p90 10.2 ms** (n=469, matched against the 200 Hz `/joint_states`
  history), i.e. inside the 8/8 band. Excluded. Two live walks in this
  session did **not** tip (34 s, 5.5 m, `dy≈−1.3 m`), so the tip is
  **intermittent** (~3 in 5), not the deterministic 3/3 previously
  filed. Probe scripts: `/tmp/openral_staleness.py` (headless sweep),
  `/tmp/ck_age_match.sh` (live age). Left the twin stopped after
  `POST /api/demo/stop`; no safety check touched, no relaunch needed.
- 2026-09-18 ~09:30Z: Operator "the dog shouldn't fall / first dog's
  image is lagging / arm still in opened position when walking". Three
  complaints, two measured causes, one still open.
  **(a) Fall — reproduced, unexplained.** Live walk tips 3/3 at
  t=13.2–15.9 s, x≈3.5 m: `y` creeps negative for ~13 s, then `/odom`
  `wz` spikes to −1.7 rad/s and it rolls to 70–104°. Headless the same
  checkpoint survives 8/8 × 30 s at both mass scales and both velocity
  commands, so this is **live-path specific**. Eliminated with real
  batteries: mass scale, arm pose, 0.35 vs 0.5 command, `last_action`
  reset, cadence jitter, systematic cadence 8–40 ms/tick, safety
  clamping, obs fallbacks, scene props, floor edge. Next probe is
  `world_state.base_twist` (runner ~L2449) vs `hal.base_twist` via
  `_dump_obs_to_disk` — everything cheaper is already ruled out.
  **(b) Tucked arm is not a fix.** Searched 21 collision-free tucked
  poses (reach ≤0.36 m vs `ready`'s 0.735 m); best is
  `(0, 0.15, −0.365, 0.684)`, 0.320 m, above the leg workspace. Safe
  headless at 1 % mass (6/6 × 30 s, and 6/6 jittered) but **falls 0/8 at
  honest mass**; live it gave 1 good run then tipped in 2 of the next 3.
  Not shipped.
  **(c) Image lag — root-caused.** RTF ≈ 0.62 × `rate_hz: 15` = the 9 Hz
  observed; tiles 6.6 fps / 2.6 s first byte; MJPEG only 0.05–0.17 MB/s
  so the tunnel is innocent; rendering already on the L40S. Cost is ROS
  0.92 MB image serialisation + OTLP JPEG encode inside a 275 % HAL.
  Respawned the `/compressed` republishers (~10.3 Hz). Left the twin
  upright (z≈0.255) and the skill stopped. No safety check touched.
- 2026-09-18 ~08:55Z: Operator "start the dashboard". `brev ls` already
  RUNNING/SHELL READY; Mac had no tunnels and no local collector.
  Container was exited (`docker start` → Up 2s), graph empty, `:4318`
  down. Relaunched Go2+Z1 via `/tmp/openral_demo_relaunch.sh`. Tunneled
  cricket `:4318`+`:8765` (`ControlMaster=no`). Proof: identity
  `go2_z1`/`go2z1mujocohal`, ingest 0.03 s, MJPEG 200 multipart,
  write-controls on. Spawned two `image_transport republish` (no
  `/compressed` on fresh deploy). Opened `http://127.0.0.1:4318/`.
  Filed Catalog: brev RUNNING ≠ graph. Did not Recalibrate / Apply /
  End. Nested-quote `docker exec bash -lc "python…"` still mangles —
  heredoc path used.
- 2026-09-18 ~20:10Z: Operator "start the app and the criket". Cold
  start from STOPPED: `brev start` → `docker start openral-jazzy-go2` →
  `/tmp/openral_demo_relaunch.sh` (go2_z1, script survived the stop) →
  tunnels `:4318`/`:8765` → dashboard + `foxglove://…8765`. Live:
  identity `go2z1mujocohal`/`go2_z1`, ingest age 0.00 s, both MJPEG
  cams, Foxglove subscribing as client 5, dog standing z≈0.240
  pitch ≈−5°. Four frictions filed to Catalog: (1) `brev start` reports
  "ready" ~70 s before sshd accepts (`Connection closed by <gw>`) — wait
  for `brev ls` SHELL READY + re-mint cert; (2) `/api/state` has no
  `robot_id`/`hal_kind`, so probing those made a live twin read WAITING —
  use `identity` + `last_ingest_ts`; (3) zero `/compressed` topics on a
  fresh deploy, fixed by two manual `image_transport republish` nodes
  (~11 Hz); (4) nested-quote `bash -lc "…python…"` mangles — use
  `docker exec -i … bash -s` heredoc, and no `set -u` (breaks ROS
  sourcing). Reasoner `lifecycle_autostart` configure-timeout traceback
  is the known noise. Did **not** Recalibrate or Apply walk. Noted
  cricket's checkout still spawns the arm at menagerie `home` — the pose
  today's rollouts tip 8/8 at honest mass — so Recalibrate before Apply.
- 2026-09-17: Operator `brev stop cricket`.
  `abundant-turquoise-cricket` **STOPPED** (L40S, id `d4dyyrsd1`). Last
  occupant Go2+Z1. Laptop **Start Cricket** to bring it back.

- 2026-09-17: Operator: video slow, then "fixed for the second robot".
  Live `:4318` is Go2+Z1; `front`/`top` 640×480 age 0, thumbs flowing.
  Root cause was not this twin: 1 Hz OTLP stills + SSE JPEG on every
  tick, and Foxglove raw 640×480 RGB8 (~18 MB/s) over the SSH tunnel
  (14:51Z graph lacked `/compressed` republishers). Go2+Z1 reload
  picked up 25 Hz thumbs + `image_transport` JPEG. Bare Go2 can still
  stutter until that graph is relaunched and its layout re-imported.
- 2026-09-17: Cloud+browser Q — cricket + SSH already is that; no
  public URL (dashboard no auth / Foxglove mixed-content `ws://`).
  Filed [[analyses/cloud-browser-needs-tunnel]]. Do not bind `0.0.0.0`.
- 2026-09-17: Condensed Catalog to eight durable operator lessons
  (WAITING/tunnel, cameras/:14318, Recalibrate demo, Apply≠arm_ready,
  502 runner latch, load/idle/deadline, occupancy/hostname,
  arm soft-physics OK / no heading lock). Merged duplicate timed
  narratives. Operator start + Current beliefs tightened. Wiki
  [[concepts/deploy-sim-visualization]] + [[entities/go2-z1]] promoted.
- 2026-09-17 ~18:55Z: "dog doesn't move" = Apply `arm_ready` not gait.
  Walk POST 202 rsl-rl; dxy≈4.89 m / ~8 s; Stop + Recalibrate upright.
  Hard-refresh, picker rsl-rl, Apply, Stop before 60 s. No E-STOP.
- 2026-09-17 ~18:36Z: Operator "walk dispatch failed". 502
  `action server rejected the goal` on all walk ids. Cause: End Cricket
  latched skill_runner; Recalibrate cleared kernel only (no
  EstopPublisher → no `rskill_runner.estop_cleared`). Reasoner
  configure FAILURE irrelevant. Live fix: `POST /api/estop_reset` then
  walk 202 `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`; Stop.
  Code: Recalibrate/Stand pass `estop=`. Bare `go2_walk` upright.
  Hard-refresh, picker walk, Apply, **Stop** before 60 s. No E-STOP.
- 2026-09-17 ~18:28Z: Operator "I dont see the cameras". API
  front/top 640×480 + MJPEG JPEG live (top shows Go2+Z1; front
  snout). Tiles black because `img.error` bounced to dead `:14318`
  (cricket is on `:4318`). Patched fallback + `?v=cam3` onto cricket
  bind-mount. Hard-refresh `http://127.0.0.1:4318/?v=cam3`; proof
  `/api/camera/top/stream`; Foxglove `ws://127.0.0.1:8765`. No
  E-STOP / no graph kill. Leftover: idle 15 min, walk 60 s deadline,
  cricket `graph_running=false` lie.
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
