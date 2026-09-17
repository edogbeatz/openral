---
type: log
tags: [openral, log]
updated: 2026-09-17
---

Each entry starts with `## [YYYY-MM-DD] <op> | <title>`. Ops: `work` (default close-out), `ingest`, `query`, `lint`, `manual`, `bootstrap`.

## [2026-09-17] work | Retry: Stop+Recalibrate upright; walk is rsl-rl

- summary: .agents/skills/go2-foxglove-view/SKILL.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: none
- linear: none
- notes: Operator "retry". Immediate `POST /api/demo/stop` 200 then
  `POST /api/demo/recalibrate` 200. Evidence: `world→base`
  [−0.05, 0, 0.254] roll 0 pitch ~−1.8°, arm 1–6 exact `ARM_READY`
  `(0, 1.2, −1.0, −0.4, 0, 0)`, kernel unlatched. Sticky HAL +
  preferWalk already on cricket (no copy/relaunch). Short
  `POST /api/demo/walk` 202 identity
  `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat` (not arm_ready); Stop
  + Recalibrate left upright. One `go2_z1_walk` graph. No E-STOP, no
  commit. User next: hard-refresh `:4318`, picker walk, Apply, Stop
  before 60 s.

## [2026-09-17] work | Recalibrated fallen Go2+Z1 after tip

- summary: .agents/skills/go2-foxglove-view/SKILL.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: none
- linear: none
- notes: Operator "requiatize" after dog fell. `POST /api/demo/stop`
  canceled skill (no E-STOP); `POST /api/demo/recalibrate` 200 on
  cricket Go2+Z1. Evidence: `world→base` z≈0.253 roll 0 pitch ~−2°,
  arm 1–6 `(0, 1.2, −1.0, −0.4, 0, 0)`, kernel unlatched. Sticky HAL
  already on cricket (no copy). Picker `?v=walk1` forces walk. Did not
  Apply walk. Catalog + Current beliefs + Log updated in go2-foxglove-view.

## [2026-09-17] work | Dashboard tiles hid live MJPEG under placeholder

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, docs/quickstart/dashboard.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator "i dont see the video". Cricket RUNNING, docker Up,
  one `go2_walk` graph, Mac `:4318`/`8765`/`14318` tunneled (no local
  collector). `/api/state` `topics.perception.cameras.{front,top}`
  640×480 thumbs live (~20 fps front); MJPEG returned JPEG (front
  snout checkerboard, top shows standing Go2). Tiles were covered by
  an opaque `waiting for camera` overlay waiting on `img.onload`
  (multipart often never fires). HTML now starts `is-streaming`; CSS
  hides placeholder on `img[src]`; JS adds the class from src +
  `hasFrame`. Copied static onto cricket bind-mount (`?v=cam2`).
  Hard-refresh `http://127.0.0.1:4318/`. Direct dog picture:
  `http://127.0.0.1:4318/api/camera/top/stream`. Did not Recalibrate
  (upright). Did not Apply walk. Leftover killers: 15 min idle still
  Ends if they only watch Foxglove; 60 s walk still freeze-falls;
  cricket hostname `brev-d4dyyrsd1` makes `/api/demo/cricket` say
  `role=laptop` / `graph_running=false` while the graph is up.

## [2026-09-17] work | File cricket start failures into go2-foxglove-view

- summary: .agents/skills/go2-foxglove-view/SKILL.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, .agents/skills/openral-wiki/SKILL.md, .agents/skills/robot-bring-up-guide/SKILL.md, wiki/concepts/deploy-sim-visualization.md, wiki/concepts/wiki-maintenance-workflow.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Standing rule — every cricket / dashboard / Foxglove start
  failure appends `.agents/skills/go2-foxglove-view/SKILL.md`
  (**Troubleshooting / Start failures**) in the same turn; chat is not
  the runbook. Catalog from this session: `openral dashboard` not on
  PATH / empty laptop collector (WAITING); live graph is cricket
  `deploy sim --dashboard --foxglove` domain 77; `:4318` WAITING if the
  laptop owns the port — stop that collector + tunnel cricket
  (`ControlMaster=no`) `:4318` + Foxglove `:8765`; 3D is Foxglove (frame
  `base`), dashboard always two OTLP thumbs; occupancy character-class
  pgrep never match relaunch.sh; Recalibrate is the demo (this-branch
  HAL sticky ARM_READY, no Apply arm_ready, Stop before 60s); 15 min
  idle auto-End; `HERO_CAMERA_KEYS` dashboard crash left Foxglove up;
  laptop Start = brev+docker+tunnels, cricket Start cannot brev a cold
  VM. Did not pkill the graph or steal tunnels.

## [2026-09-17] work | Apply walk was arm_ready; dog now translates

- summary: wiki/entities/go2-z1.md
- touched: wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Live Apply after Recalibrate did not start the rsl-rl walk.
  Dashboard logs 17:30–17:31Z: four `ExecuteRskill` of
  `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` (2 s `horizon_s`,
  `ROSRskillGoalSatisfied`); identity stayed arm_ready; last command was
  Hub stand + ARM_READY. Not a leftover 60 s walk clock — walk never
  dispatched. Picker restored saved arm_ready over preferWalk after
  Recalibrate. HAL `_snap_arm_hold` on cricket was already arm-only;
  `test_recalibrate_then_twelve_dof_walk_moves_legs_and_holds_arm` now
  proves calves/hips move. Tightened snap (skip `_leg_joints` and
  `qpos[0:7]`). Recalibrate then `POST /api/demo/walk` 202
  (`Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`): `world→base` +1.04 m
  xy in 8 s, z≈0.36, arm stayed ready, FL_thigh_span 0.20 rad. **Stop**
  (no e-stop) Hub-stood origin z≈0.26 pitch ~-1.4°, kernel unlatched.
  Refresh the dashboard so the picker fix loads. Graph not relaunched.
  60 s walk still freeze-falls unless Stop runs first.

## [2026-09-17] work | Cricket Recalibrate was old HAL; copied sticky + ARM_READY

- summary: wiki/entities/go2-z1.md
- touched: wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Live Go2+Z1 was circling because Recalibrate on cricket did not
  actually park/hold arm-ready — the container HAL had `GO2_Z1_ARM_READY`
  as a constant but no sticky `_arm_hold_pose`, and dashboard Recalibrate
  still sent menagerie ARM_HOME `(0, 0.785, -0.261, -0.523, …)`. Stop then
  Recalibrate API returned 200 while `world→base` pitched ~13°, z≈0.22,
  arm joints nowhere near ready, Z1 qvel tens of rad/s. Copied this
  branch's `go2_z1.py` into the bind-mount, patched Recalibrate pose to
  ARM_READY, cold-reloaded `go2_z1` via `POST /api/demo/load` (character-
  class pgrep). After Recalibrate: `world→base` [-0.049, 0, 0.254],
  RPY≈[0, -1.8°, 0], arm joints 1–6 exact `(0, 1.2, -1.0, -0.4, 0, 0)`,
  arm qvel 0. Gripper reads 1.0 vs target 0.0 (leftover). No yaw PID /
  heading lock — Recalibrate is the walk gate. Apply walk only after
  Recalibrate. Mac `:4318` was the cricket dashboard this session.

## [2026-09-17] work | Attached live Go2+Z1 (tunnels, no relaunch)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator looking at laptop `http://127.0.0.1:4318` (WAITING,
  no cameras, no robot) — that collector is not the robot. Cricket
  graph was already up as `go2_z1` / `go2_z1_walk` (domain 77,
  write-controls on). Attached only: SSH tunnels Foxglove
  `ws://127.0.0.1:8765` and cricket dashboard
  `http://127.0.0.1:14318/` (did not steal local `:4318`). Recalibrate
  on cricket after a side-lying tip (`world→base` z=0.155, roll ~81°)
  landed upright z≈0.24. Live URLs: cricket dashboard `:14318`,
  Foxglove `foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765`.

## [2026-09-17] work | Dashboard always shows front + side cameras

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Operator on laptop `http://localhost:4318` saw WAITING with
  **zero** camera tiles — empty grid, only safety cards. Cause: `#cell-cameras`
  stayed `hidden` until the first `sensors.read_latest` span, and
  `.main-visual[data-live="0"]` then hid the whole visual column. The
  page now always mounts Go2 HAL keys `front` (Main / snout) and `top`
  (Side / 3/4 view) as labeled placeholders (`waiting for camera`).
  Empty-store `/api/state` still lists those two slots. A laptop
  collector with no local OTLP proxies cricket's tunneled dashboard
  MJPEG at `:14318` so this page can show a picture; on cricket the
  proxy is off (no self-loop). Until this `:4318` process is restarted,
  a hard refresh still mounts the two panels and the JS falls back to
  cricket `:14318` MJPEG on a local stream 404. Tiles remain ~25 Hz
  OTLP JPEG MJPEG, not Foxglove live `/compressed`. Demo-bar wrap is
  leftover, not this change.

## [2026-09-17] work | Laptop Start Cricket attaches (brev + tunnels)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Operator hit Start Cricket on the Mac local dashboard
  (`http://localhost:4318`) and nothing happened. Previous Start only
  spawned the graph if this process was already on cricket — laptop Start
  was a silent no-op and could not `brev start`. Laptop Start now
  `brev start`s `abundant-turquoise-cricket` if stopped, `docker start`s
  `openral-jazzy-go2`, opens SSH tunnels (`ControlMaster=no`, Foxglove
  `ws://127.0.0.1:8765`, cricket dashboard `http://127.0.0.1:14318/` so
  local `:4318` stays this page), and attaches `openral deploy sim
  --dashboard --foxglove` only if occupancy is empty. If the graph is
  already up, Start is already-running: tunnels + Foxglove, no teardown.
  End / 15 min idle from the laptop still `brev stop`. Occupancy uses
  character-class pgrep (never `pkill -f 'openral deploy sim'`).
  > ⚠️ Contradicts the earlier same-day log that Start cannot `brev start`
  from this page — that was the on-cricket-only implementation.

## [2026-09-17] work | Demo Start/End Cricket + idle auto-stop

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Operator asked for start/end cricket buttons and auto-stop on idle.
  Cricket is Brev `abundant-turquoise-cricket` + docker `openral-jazzy-go2`.
  Today the graph is started with `brev start` (laptop), `docker start
  openral-jazzy-go2`, then `openral deploy sim --dashboard --foxglove` inside
  the container (`ROS_DOMAIN_ID=77`). The dashboard is served from that
  host, so **Start Cricket** can only start docker/sim while the instance is
  already up — it cannot `brev start` a fully stopped box from that page.
  **End Cricket** cancels `ExecuteRskill` (no e-stop latch), kills the graph
  with character-class pgrep (same self-match trap as reload), then
  `brev stop` / host halt. Distinct from **Stop** (keeps sim) and **E-STOP**
  (latches). Idle default 15 min (`OPENRAL_CRICKET_IDLE_S`); running a walk
  is not idle; the bar shows `auto-stop in mm:ss`. Host PIDs stay in the
  go2-foxglove-view skill.

## [2026-09-17] work | Go2+Z1 Walk holds Recalibrate arm-ready pose

- summary: wiki/entities/go2-z1.md
- touched: wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Operator: arm waved during Walk after Recalibrate. HAL had pinned
  every `send_action` (including 19-D `arm_ready`) to spawn home, and
  `idle_step` did not qpos-snap — wall-time idle physics left the Z1
  servos soft under gait. Sticky `_arm_hold_pose` now updates on Hub-stand
  19-D (Recalibrate / arm_ready) and snaps on locomotion + idle. Dashboard
  Recalibrate pose is `GO2_Z1_ARM_READY`, not menagerie home. Domain-mismatch
  spin/fall is out of scope.

## [2026-09-17] work | Demo Stop cancels ExecuteRskill without e-stop

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Demo bar had E-STOP (latch), Recalibrate (clear latch + Hub stand),
  and Stand (snap while the skill still runs) — no way to stop a walk
  without latching the kernel. Added **Stop** → `POST /api/demo/stop`:
  `CancelGoal` on `/openral/execute_rskill` (Jazzy `goal_info` zero UUID
  = all goals), wait the runner drain, then `ResetToPose` Hub home. Does
  not publish `/openral/estop`. After Stop, Apply can dispatch again.
  This is also the operator answer to the 60 s walk `deadline_missed`
  fall: cancel before idle freezes a mid-gait pose.

## [2026-09-17] query | Go2 fell when the 60 s walk ended

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Apply walk 15:05:11Z → `deadline_missed` 15:06:11Z (elapsed=budget=60 s,
  1800 chunks). Kernel unlatched. Last `safe_action` already a crouched
  gait, then idle froze it. Live `world→base` [12.56, -4.64, 0.154], roll
  77° — on its side after ~12.6 m. `_drain_and_idle_hold` does not snap
  Hub stand. Not an e-stop.

## [2026-09-17] work | Demo wizard: Bare Go2 auto-calibrates; Go2+Z1 asks Recalibrate

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Bare Go2 (`resume=stand`) auto-calls Recalibrate once `/healthz`
  is back and lands on select skill + Apply. Go2+Z1 confirms
  "needs Recalibrate before you can apply a skill"; after that the last
  selected skill id is remembered per robot. Neither story auto-walks.
  Recalibrate stays available for tips; Stand is drive-time recovery.

## [2026-09-17] work | Reimported Go2 Foxglove layout onto /compressed

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Operator asked to reimport after Image panels stayed on raw
  `/openral/cameras/front/image`. Regenerated
  `/tmp/openral_layout_go2.json` (`top` then `front` `/compressed`) and
  wrote it into Studio `openral_layout_go2` (`lay_0ecFylVWqq0HLLxN`)
  working+baseline, then opened
  `foxglove://…&layoutId=lay_0ecFylVWqq0HLLxN`. Host-specific store
  rewrite lives in the go2-foxglove-view skill. Cricket's running
  deploy (14:51Z) had not spawned republishers; two `image_transport
  republish raw compressed` nodes were started on the live graph for
  `top` and `front`. `/compressed` is `sensor_msgs/CompressedImage`
  JPEG and flowing (~7 Hz).

## [2026-09-17] work | Demo reload pkill matched itself; disk-full hid it

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Bare Go2 / Go2+Z1 click scheduled `demo.load_preset` then
  `pkill -f 'openral deploy sim'`, which matched the `bash -c` killer
  (and pkill itself). Relaunch never ran; JS 45×2s poll showed
  "reload timed out". HAL SIGSEGV on shutdown dumped multi-GB cores and
  filled cricket `/` (100%); `docker exec` failed until coredumps and
  exited containers were removed. Reload now writes
  `/tmp/openral_demo_relaunch.sh`, kills via character-class pgrep,
  sources Jazzy, `ulimit -c 0`; UI waits for a healthz down-gap up to
  180s.

## [2026-09-17] work | Camera tiles and Foxglove images were a slideshow

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/openral-foxglove-bringup.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: HAL `sensors.read_latest` thumbs were 1 Hz leftover from still-card
  polling; SSE re-shipped those JPEGs on every telemetry tick; Foxglove
  `--foxglove` sent raw 640×480 RGB8 (~18 MB/s for Go2 front+top) over the
  laptop tunnel. Thumbs now 25 Hz cap, SSE omits `thumbnail_jpeg_b64`
  (MJPEG is the video), deploy spawns `image_transport` republishers and
  the generated layout points at `/compressed`. Re-import the JSON; graph
  restart required.

## [2026-09-17] query | Bare-Go2 dashboard 0 / 3 / 1 / 0 counters

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: operator screenshot was session totals, not live latch.
  Walk `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat` (goal
  dfbf7e97…) ran 60 s / 1800 chunks then
  `deadline_exceeded` at 14:17:48Z. Three
  `safety.external_estop_received` at 14:18:00 / :02 / :06Z; first two
  cleared, third left latched; then `demo.load_preset go2`. Kernel never
  emitted a safety-violation span. Recalibrate does not zero counters.

## [2026-09-17] work | Demo bar: select skill then Apply (no separate Run)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: write-controls demo bar is now choose robot → Recalibrate →
  pick a skill → Apply. The separate Run-skill strip stays hidden while
  the demo bar is shown. Walk still uses `/api/demo/walk`
  (`velocity_commands: [0.35, 0, 0]`); other picks POST
  `/api/skill/execute` with blank goal params. Walk remains the default
  selection for go2 / go2_z1.

## [2026-09-17] work | PoC sequence: Load Go2 → Walk → Adapt → Go2+Z1

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: demo bar was two independent cold-reloads that left the dog idle.
  Load Go2 stays idle so Walk is a beat; Adapt → Go2+Z1 reloads then
  auto-walks the same 12-DoF rsl-rl skill (hold-pad 12→19). Picker now
  intersects robot capability tags, and the walk skill also tags `go2_z1`.

## [2026-09-17] work | Demo bar becomes a choose → recalibrate → apply wizard

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Bare Go2 / Go2+Z1 load no longer auto-walks. UI forces
  Recalibrate then Apply walk skill; switching robots confirms and
  restarts the sequence. Reload script kills dashboard/uvicorn so the
  previous twin cannot linger.

## [2026-09-17] work | Dashboard demo bar: Stand / Walk / Bare Go2 / Go2+Z1

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: write-controls demo strip — Stand/Recalibrate = e-stop clear +
  ResetToPose with free-base upright snap; Walk = rsl-rl velocity;
  Bare Go2 / Go2+Z1 cold-reload walk scenes. Deploy exports
  `OPENRAL_ROBOT_ID`. Module
  `openral_observability.dashboard.demo_controls`.

## [2026-09-17] work | Wiki close-out is mandatory on every finished task

- summary: wiki/concepts/wiki-maintenance-workflow.md
- touched: wiki/concepts/wiki-maintenance-workflow.md, wiki/concepts/task-wiki-contract.md, wiki/concepts/second-brain.md, wiki/sources/engineering-playbook.md, wiki/index.md, wiki/log.md, .agents/skills/openral-wiki/SKILL.md, CLAUDE.md
- new: none
- linear: none
- notes: skill used to load only for wiki edits and query asked "file
  this back?". Close-out is now the default op (`work`): update home
  pages, append this log, do not ask. CLAUDE.md §4.2 step 10 + §4.4
  checklist so coding agents hit it even when they did not open the
  wiki first. Pages stay sparse; new pages only when the domain has
  no home. Host-specific PIDs stay in operator skills.

## [2026-09-17] query | Z1 arm command module (turn on + pose)

- summary: wiki/entities/go2-z1.md
- touched: wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: the other Go2+Z1 chat froze the arm so locomotion would not
  tip the dog. This change keeps that 12-D freeze and adds
  `OpenRAL/rskill-zero-go2_z1-arm_ready-fp32` (`model_family: zero`) as
  the 19-D command path. Named poses `ready` / `home` / `fold`. HAL
  honours full-width arm slots; 12-D still snaps.

## [2026-09-17] manual | Event log shows collapsed live debug on Go2

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/index.md, wiki/log.md, wiki/concepts/deploy-sim-visualization.md
- new: none
- linear: none
- notes: Go2 walk spans are all `debug` (no reasoner headlines), so the
  Event log looked empty with Debug off. UI now injects one live row per
  stream; do not promote `rskill.execute`.

## [2026-09-17] ingest | Public docs catch up to Go2 walk / Go2+Z1 / Foxglove / dashboard clock

- summary: wiki/entities/go2.md, wiki/entities/go2-z1.md
- touched: wiki/index.md, wiki/entities/go2.md, wiki/log.md
- new: wiki/entities/go2-z1.md
- linear: none
- notes: user-facing docs still described Go2 as a gravity-off contract
  validator with "no gait". That was false once `go2_walk.yaml` +
  rsl-rl ONNX and `robots/go2_z1` landed. Updated robots.md, HAL README,
  go2 README, vla_compatibility §3.12, rskills.md, repo-map, repo-state-map
  Go2 card, Foxglove README/VERIFICATION (COLLADA up-axis + Studio cache),
  dashboard quickstart (walk bench, not bench, for locomotion; host clock
  already there), observability README host-clock section, METHODS 01/06/11/14
  (hold-pad as item 45 — two pads, different layers). Wiki Go2 page now
  distinguishes bench vs walk; Go2+Z1 got its own entity.

## [2026-09-16] ingest | Go2 Foxglove session state + rebuild of the four lost pages

- summary: wiki/entities/go2.md, wiki/analyses/proving-sim-motion-not-a-frozen-stand.md
- touched: wiki/index.md, wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- new: wiki/entities/openral.md, wiki/entities/go2.md, wiki/concepts/wiki-maintenance-workflow.md, wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md, wiki/analyses/proving-sim-motion-not-a-frozen-stand.md
- linear: none
- notes: swept the uncommitted working tree (Go2 HAL, camera rig,
  foxglove bringup, dashboard.js) plus `.agents/skills/go2-foxglove-view/`
  into the wiki. New durable findings the earlier pages predated: the
  ament mesh overlay is **confirmed** on cricket and the remaining blocker
  is Studio caching the earlier fetch failure; COLLADA `<up_axis>` (RViz
  ignores it, Foxglove honours it, so the layout forces `z_up`); Image
  panels need the paired CameraInfo on the *manifest* `frame_id`; the
  dashboard freshness pill ages against the host clock, not the browser's;
  Go2 torque motors need `idle_step` to PD-hold or the calves fold.
  Filed the actuation-verification traps as their own analysis —
  `/joint_states` span is the only ground truth, `action_applied` stayed
  silent through a real trot, and `docker exec` without `-i` drops a
  heredoc and still exits 0.
  Rebuilt the four pages lost on 2026-09-16 from in-repo sources only
  (`CLAUDE.md`, `docs/architecture/repo-map.md`, `README.md`,
  `.agents/skills/openral-wiki/SKILL.md`) — re-derivations, flagged as
  such in the index, no attempt to reproduce the lost wording.
  Every `[[wikilink]]` now resolves; no dangling targets remain.
  Operational host state (cricket container, pids, script invocations)
  deliberately stays in the `go2-foxglove-view` skill, not in wiki prose.

## [2026-09-16] query | Front camera cannot see the robot; add Go2 top cam

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- linear: none
- notes: Foxglove 3D showed Go2; `/openral/cameras/front/image` did not.
  Front cam looks +X from the face. Added viz-only `top` (menagerie
  track pose). Layout leads with `top`; sim layout uses all RGB sensors.

## [2026-09-16] query | Front camera gray slab is empty staging, not zoom

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- linear: none
- notes: Go2 `/openral/cameras/front/image` in Foxglove looked like a
  zoomed-in gray card. Local MuJoCo render was ~70° FoV, official URDF
  pose, black sky over a flat `camrig_floor`. Foxglove's dark panel hid
  the sky. Staging floor is now infinite checker + skybox.

## [2026-09-16] query | Foxglove web meshes need package:// + ament overlay

- summary: wiki/analyses/foxglove-web-meshes-need-package-uri.md
- touched: wiki/index.md, wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- new: wiki/entities/openral-foxglove-bringup.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/foxglove-web-meshes-need-package-uri.md
- linear: none
- notes: filed from a cricket Go2 `deploy sim --foxglove` session (Mac web viewer). Studio requests only `package://` from the bridge; the old `rewrite_package_mesh_uris` (`file://`) cannot feed app.foxglove.dev or a laptop desktop Studio. No older wiki page claimed the file:// rewrite (domain had no home after the 2026-09-16 partial restore). Go2 entity page not created — none existed. `wiki/concepts/wiki-maintenance-workflow.md` still lost; not reconstructed.

## [2026-09-16] manual | Wiki references Linear back (provenance only)

- touched: wiki/concepts/task-wiki-contract.md, .agents/skills/openral-wiki/SKILL.md
- linear: none — decided in chat, filed here
- notes: task→wiki stays a mandatory gate; wiki→Linear is optional provenance.
  Two carriers only — a `linear:` line on log entries, and an optional
  `linear:` frontmatter list on pages. Identifier + title, no linear.app
  URLs, because `wiki/` shares an upstream with the public OpenRAL repo.
  Status / acceptance criteria / assignees are banned from page prose: they
  rot, and agents read the wiki as settled belief. OpenRAL work is the
  Linear **Acquire** project, team `LaunchPad` key `1`, so IDs read `1-131`.

## [2026-09-16] manual | Partial restore after uncommitted wiki was destroyed

- restored: wiki/index.md, wiki/log.md, wiki/concepts/second-brain.md,
  wiki/concepts/task-wiki-contract.md, .agents/skills/openral-wiki/SKILL.md
- lost: wiki/entities/openral.md, wiki/concepts/wiki-maintenance-workflow.md,
  wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md, raw/,
  tests/unit/test_wiki_second_brain.py
- notes: the bootstrap was never committed. A concurrent process in this
  working directory moved HEAD (master → c40e8b8 → 7e5a6de → 1ddc80e →
  7f62992, detached) and removed the untracked files. Nothing was
  recoverable: no stash, no `wiki/` path in any git object, no copy on disk.
  The five restored files are verbatim from an agent session that had read
  them in full; the four lost pages were never read and are NOT
  reconstructed, because inventing them would violate CLAUDE.md §1.2.
  Committing the wiki from now on is the fix — that is why this entry
  exists rather than a silent re-bootstrap.

## [2026-09-16] bootstrap | OpenRAL second brain

- summary: seeded wiki from CareTrace / Karpathy LLM-wiki logic
- new: wiki/index.md, wiki/entities/openral.md, wiki/concepts/second-brain.md, wiki/concepts/task-wiki-contract.md, wiki/concepts/wiki-maintenance-workflow.md, wiki/sources/engineering-playbook.md, wiki/sources/repo-map.md
- notes: docs/ + schemas remain normative; tasks must cite wiki pages; skill at `.agents/skills/openral-wiki/`
