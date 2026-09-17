# `openral dashboard` — live debugging UI

A single-page, read-only debug pane over the OpenRAL OTel stream.
Renders the most recent `rskill.execute`, `skill.chunk_inference`,
and `safety.check` spans, rolling metric histograms, and an event
log — live, no Jaeger required.

The dashboard runs as an embedded OTLP receiver rather than an in-process
exporter, so instrumented workloads stay decoupled from the debug UI.

## Run it

The dashboard is a `openral` subcommand. The HTTP port serves the UI, the
SSE event stream, **and** an embedded OTLP/HTTP receiver. The default
port is **4318** (the OTLP/HTTP standard) — `8000` collided with
`mkdocs serve` (`just docs`) and most FastAPI demos (issue #132).

```bash
openral dashboard            # binds 127.0.0.1:4318 by default
# → stderr prints: OpenRAL dashboard: http://localhost:4318/ …
```

Then point any OpenRAL workload at it. **Sim does not emit OTel by
default** — you opt in via the env vars below; an unconfigured
`openral sim run` is silent on the dashboard side:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
  openral sim run --config scenes/sim/libero_spatial.yaml --rskill smolvla-libero
```

Open `http://localhost:4318` in a browser. The connection indicator
in the top right turns green within a few hundred ms. That pill is
OTLP ingest age on the **dashboard host** (`now_unix - last_ingest_ts`),
not "is the page's EventSource up" and not the browser's clock — a
laptop viewing a port-forwarded remote `:4318` is often ≥60 s off the
VM, which used to freeze the pill on `DEAD (1m)` while spans were still
landing.

## One-keystroke demo — two options

### Dashboard → sim (`--inprocess`)
The dashboard spawns the workload as a child with the OTLP env vars
already configured. Pass the whole command as **one shell-quoted
string** (shlex-tokenised):

```bash
openral dashboard \
  --inprocess "openral sim run --config scenes/benchmark/pusht.yaml --rskill diffusion-pusht"
```

### Workload → dashboard (`--dashboard` on sim / deploy / benchmark)
Inverse path: the workload spawns the dashboard as a child on `4318`
(override with `--dashboard-port`) and shuts it down on exit. Best
when you already have the workload command memorised. All three
entry points carry the same flag:

```bash
openral sim run --dashboard \
  --config scenes/benchmark/pusht.yaml \
  --rskill diffusion-pusht

openral deploy run --dashboard --config scenes/deploy/so101_bench.yaml

openral benchmark run --dashboard \
  --suite libero_spatial \
  --rskill smolvla-libero
```

The workload prints `OpenRAL dashboard attached: http://localhost:4318/`
once the child reports healthy, then routes traces+metrics to it for
the rest of the run. The child is SIGINT'd at exit after OTel finishes
draining (no `Connection refused` retries on the way down).

## What you see

The page only shows what the running deploy can actually feed — with one
exception. **Perception · cameras** is always on screen: two Go2 HAL
slots, **Main · `front`** (snout) and **Side · `top`** (3/4 view). The
`<img>` tags point at `/api/camera/{front,top}/stream` from first paint
and start in `is-streaming` so the opaque `waiting for camera`
placeholder cannot cover a live MJPEG (multipart often never fires
`img.onload`). Direct proof: `http://127.0.0.1:4318/api/camera/top/stream`
shows the dog; `front` is snout-out (checkerboard floor + black sky is
healthy). A laptop collector with no local thumbs still proxies cricket
`:14318`. Other optional cards still start hidden and reveal themselves
the first time their producer emits — so
`scenes/deploy/go2_bench.yaml`, which runs with SLAM, octomap, object
detection, the reward monitor and spatial memory all off, comes up as
cameras + running skill + joints + safety rather than a page of
"waiting for …" placeholders. Revealing is one-way: a producer that stops
leaves its last reading on screen instead of making the card vanish
mid-mission. The safety **counters** in the command band are never hidden,
so a trip is always on screen (the more detailed *Safety · current state*
card may be one rail-scroll away on a deploy with every leg live).

The identity strip prunes the same way — a quadruped with no VLA engine or
action-chunk size shows seven readouts, not twelve em-dashes.

- **Top bar** — service name, run mode (`sim` / `hardware` /
  `benchmark` once PR #108 lands), short run id, connection status.
- **Reasoner · mission** — the reasoner's active task queue,
  rendered from `reasoner.mission_json` as an ordered checklist: each
  subtask shows its status (done ✓ / active ▶ / verifying ? / abandoned ✗
  / pending), a reward bar coloured by a three-tier verdict
  band (green at/above the success threshold, amber in the VLM-adjudicated
  ambiguous band, red below the check floor / unverified), the per-task
  verdict text (the *why* behind done/abandoned, e.g.
  `unverified after 3 attempt(s) (success=0.42)`), and the attempts/cap
  ladder. **Failed (abandoned) tasks are called out loudly** — a red wash,
  strikethrough, and bold ✗ rather than dimmed — and the header tallies
  them (`5 tasks · 1 done · 1 failed · on 3/5`). A mission that finishes
  with ≥1 abandoned task gets a red **mission failed** banner above the
  checklist. Subdivided children from a replan (`#123`: a blocked task
  `t2` spliced into `t2.1`, `t2.2`, …) are indented under their parent
  with a dim id badge — depth is read from the dot-path task id, so the
  flat queue still reads as a hierarchy. The latest tick (tool / model /
  error) is a footer line beneath it. The card is absent until the
  `reasoner_node` is ACTIVE and ticking.
- **Live signal · running skill** — one card for the active `rSkill`: skill id
  (headline), role, action-applied, tick idx, and a `step Xms · forward Yms`
  latency line. `step` is the full `rskill.execute` call; `forward` is the model
  forward pass inside it (`rskill.chunk_inference`) — the gap between them is the
  pre/post-processing cost. The former separate `Inference` card was folded in
  here (its engine is already in Identity, its only unique datum was the
  forward-pass latency); the redundant one-line `Safety` live-signal card was
  removed (Safety has its own zone above). Card border turns red on
  `Status.ERROR`.
- **Safety** — the **Safety · current state** card, running counters of
  `safety_violation`, `estop_requested`, `deadline_missed`, `sensor_stale`,
  and `skill_failure` span events, and the **Safety check ledger** (per-check
  pass/fail from `safety.check` spans).

  *Safety · current state* (ADR-0096) is the only card on the page that is
  **not** fed by OTel: it subscribes the latched `/openral/safety_status`
  topic (`openral_msgs/SafetyStatus`, RELIABLE + TRANSIENT_LOCAL +
  KEEP_LAST=1) that the C++ safety kernel and `SafetyPassthroughNode` both
  publish. It shows `latched` / `clear` / `stale`, the typed `drop_reason`
  (e.g. `kind_collision`, `drop_envelope_unconfigured`), the publisher's
  `detail`, the `rskill` in flight, and the **age of the last transition**.
  Because the topic is durable, a dashboard opened *mid-mission* shows the
  correct state immediately instead of "unknown until the next fault" — the
  span-inferred latch under it can only move while command chunks are
  flowing, and a latched kernel is exactly the state in which they stop.
  The age matters: publishers re-stamp at 1 Hz, so an age past ~3 s renders
  the card `stale` and the state is to be read as **unknown, not safe**
  (the safety publisher may be gone). With no ROS workspace sourced the card
  reads *waiting* — never a fabricated "clear". The **skill failures** counter
  tallies every Reasoner-published `/openral/failure/rskill` event
  (mirrored onto the OTLP `openral.event.skill_failure` span event) and
  shows the latest failure state under it (e.g. `latest: vram_insufficient`).
- **Embodiment** — robot joints, **World state** (now also carrying the
  durable scene-object spatial-memory table, merged from the former
  standalone `World · scene objects` card), and system health. The
  separate `Commands · next action` card was removed; the commanded joint
  values still render as the second trace on the joints card.
- **Metrics** — every histogram, counter, and gauge that comes over
  the wire, with p50/p95 (for histograms) and a sparkline of the
  last ~600 samples. The whole panel is absent until a workload emits its
  first metric; PR #108
  adds `openral.tick.duration`, `openral.inference.duration`,
  `openral.hal.*.duration`, etc. Hover any sparkline for the exact
  value + clock time of the nearest sample (a white-ringed marker
  snaps to the point); each graph carries its own min/max Y labels and
  shares one bottom time axis with dotted gridlines so every row reads
  on the same clock. Metrics whose producer emits a contractual
  threshold (`openral.metric.threshold_ms` — the runner latency budget
  on `tick.duration`, the world-state staleness deadline on
  `world_state.staleness_ms`) draw a dashed budget/deadline line and
  redden the trace once the latest sample breaches it (`*_dir` set to
  `lower` flips the test for floor-style metrics where dropping below is
  the fault). Warn/error events appear as severity-coloured vertical
  markers aligned across all graphs. **Click any point** to focus the
  whole column on that instant — a line is drawn across every graph and
  the event log scopes to a window around it (clear with the ✕).
  **Scroll** over a graph to zoom the shared time window in/out (centred
  on the cursor, bounded by the retained buffer; "reset zoom" restores
  the full view), and Y rescales to whatever is visible. The **freeze**
  toggle pauses live updates so you can inspect a moment.
- **Event log** — chronological feed of the last 60 events (spans,
  span events, and real log lines bridged from structlog over OTLP);
  ESTOP / safety violation rows render in red. Filter chips toggle the
  `info` / `warn` / `error` buckets (on by default) and a `debug` bucket
  (off by default — high-rate DEBUG such as `world_state` ~30 Hz would
  otherwise flood the bounded view; toggle it on when you need every
  tick). While Debug is off the log still shows **one live row per
  stream** (latest `rskill.execute`, each camera, `hal.read_state`,
  `safety.check`, …) so a locomotion-only run is not an empty pane.
  Log lines are bucketed by OTLP `severity_number`
  (DEBUG→`debug`, INFO→`info`, WARN→`warn`, ERROR/FATAL→`error`).

## Running a skill from the page

With `OPENRAL_DASHBOARD_WRITE_CONTROLS=1` the command band grows a **demo**
wizard under the prompt. There is one Apply button — not a separate **Run
skill** strip. **Bare Go2** auto-calibrates after load, then pick a skill and
Apply. **Go2 + Z1** asks you to Recalibrate first (confirm on click), then
pick a skill and Apply. Neither story auto-walks. Apply POSTs
`/api/skill/execute` (or `/api/demo/walk` when the rsl-rl velocity walk skill
is selected), which sends one `ExecuteRskill` action goal and returns **202**
the moment the action server accepts — the safety kernel still disposes of
every chunk the dispatched policy proposes, and E-STOP still latches it.
Without the env var the bar is absent, because the endpoints behind it would
answer 403.

The picker is filled from `GET /api/skills` (the in-tree `rskills/` index) and
narrowed to the running robot's `capabilities.embodiment_tags`, so on a Go2
or Go2+Z1 deploy it offers `rsl-rl-onnx-go2-velocity-flat` (default) and any
other matching skill (for example `rskill-zero-go2_z1-arm_ready-fp32` on the
armed twin). The ids it sends are manifest `name` values — the same keys the
skill_runner's in-tree resolver indexes from its `rskill_search_paths`. A
blank goal is omitted, so Apply on a non-walk skill means "whatever the
manifest's own defaults say". The walk skill keeps the demo jog
`velocity_commands: [0.35, 0, 0]`.

End to end on the quadruped **walk** bench (gravity on — `go2_bench` is the
gravity-off pipe proof and will not locomote):

```bash
OPENRAL_DASHBOARD_WRITE_CONTROLS=1 openral dashboard
openral deploy sim --config scenes/deploy/go2_walk.yaml --dashboard --foxglove
# → page shows: cameras · running skill · 12 joints · safety
# → demo: Bare Go2 → auto-calibrate → rsl-rl-onnx-go2-velocity-flat → Apply skill
```

The same skill on the 19-DoF composite is `scenes/deploy/go2_z1_walk.yaml`
(runner hold-pads 12→19).

### Demo bar (Go2 walk wizard)

Stepped strip (write-controls on). **Bare Go2** auto-calibrates after reload
and lands on **select skill + Apply**. **Go2 + Z1** highlights Recalibrate as
the required next step (confirm on click). Switching robots never auto-walks.
The last selected skill id is remembered per robot in `sessionStorage`.
**Stop** cancels the in-flight `ExecuteRskill` goal (runner drain + idle-hold)
then snaps Hub stand — it does **not** latch e-stop, so Apply can run again.
**Start Cricket** from a laptop dashboard (`OPENRAL_DASHBOARD_WRITE_CONTROLS=1
uv run openral dashboard` on `:4318`) is the operator start path: `brev start
abundant-turquoise-cricket` if the instance is stopped, `docker start
openral-jazzy-go2`, SSH tunnels with `ControlMaster=no` (Foxglove
`ws://127.0.0.1:8765` and cricket's own dashboard at
`http://127.0.0.1:14318/` so this process can keep `:4318`), then
`openral deploy sim --dashboard --foxglove` inside the container if the
graph is down (`ROS_DOMAIN_ID=77`, `OPENRAL_DASHBOARD_WRITE_CONTROLS=1`).
If the graph is already up, Start only ensures tunnels and reports
already-running — it does not tear down. Start from a dashboard **served
on cricket** still only starts the local graph (the box is already up).
**End Cricket** cancels the skill (no e-stop latch), stops the graph, then
`brev stop` / host halt so GPU billing stops. From a laptop, End still
`brev stop`s. That is not **Stop** (Stop keeps the sim) and not **E-STOP**
(E-STOP latches the kernel). Idle with no Recalibrate / Apply / Stand / Walk / Load,
no running `ExecuteRskill`, and no dashboard interaction auto-Ends after
`OPENRAL_CRICKET_IDLE_S` (default **15 minutes**); the bar shows
`auto-stop in mm:ss`. Recalibrate stays available for tip recovery; **Stand**
is the drive-time snap *while the skill is still running*. **E-STOP**
(command band) latches the kernel. The fallback **Run skill** strip stays in
the page but hidden while this bar is shown.

| Control | Endpoint | Effect |
| --- | --- | --- |
| Bare Go2 | `POST /api/demo/load` `{"preset":"go2"}` | Cold-reload `go2_walk` (~30-90 s), then auto-stand |
| Go2 + Z1 | `POST /api/demo/load` `{"preset":"go2_z1"}` | Cold-reload `go2_z1_walk` (~30-90 s); Recalibrate next |
| Recalibrate | `POST /api/demo/recalibrate` | E-stop clear + free-base upright; Go2+Z1 parks the Z1 at arm-ready so Walk holds that pose |
| Skill picker + Apply skill | walk → `POST /api/demo/walk`; else `POST /api/skill/execute` | Walk default `[0.35, 0, 0]`; other skills omit blank goal params |
| Stop | `POST /api/demo/stop` | Cancel `ExecuteRskill` (no e-stop latch) + Hub stand; Apply again |
| Stand | `POST /api/demo/stand` | Tip recovery while driving (skill keeps running) |
| Start Cricket | `POST /api/demo/cricket/start` | Laptop: `brev start` + docker + tunnels + attach (no-op success if graph up). On cricket: start graph if down |
| End Cricket | `POST /api/demo/cricket/end` | Cancel skill, stop graph, `brev stop` the Brev instance (billing) |
| (idle countdown) | `GET /api/demo/cricket` | Remaining auto-stop time; GET does not reset the timer |

After a laptop Start, the dog is at **Foxglove** `ws://127.0.0.1:8765` (open
`foxglove://open?ds=foxglove-websocket&ds.url=ws://127.0.0.1:8765`). This
laptop page (`:4318`) keeps the two camera tiles and proxies cricket's
MJPEG (`front` + `top`) from **http://127.0.0.1:14318/** so the operator
does not have to leave this window for a picture. Cricket's own dashboard
and demo bar remain at `:14318`. A fully stopped box is the same button:

```bash
OPENRAL_DASHBOARD_WRITE_CONTROLS=1 uv run openral dashboard
# → Start Cricket
# → Foxglove ws://127.0.0.1:8765
# → cricket dashboard http://127.0.0.1:14318/
```

`openral deploy sim` exports `OPENRAL_ROBOT_ID` so Recalibrate hits the running
twin. The picker intersects skill `embodiment_tags` with the robot's
`capabilities.embodiment_tags`, so the Go2 walk skill stays offered on
`go2_z1`.

Discovery (`GET /api/robots`) and `POST /api/param/set` remain available for
operator tooling without a card of their own.

## Endpoints

| Path           | What it serves                                       |
|----------------|------------------------------------------------------|
| `GET /`        | Single-page UI (vanilla JS + SSE, no npm)            |
| `GET /healthz` | `{"status": "ok"}` for compose healthchecks          |
| `GET /api/state`  | One-shot JSON snapshot of the current store       |
| `GET /api/stream` | Server-Sent Events — every state update           |
| `GET /api/camera/{source}/stream` | MJPEG of OTLP thumbs; `front`/`top` always known; laptop proxies cricket `:14318` |
| `POST /api/demo/stand` | Tip recovery upright snap (write-controls) |
| `POST /api/demo/recalibrate` | Required after Go2+Z1 load; parks the Z1 at arm-ready; also tip recovery (Bare Go2 auto-stands after load) |
| `POST /api/demo/walk` | Apply Go2 rsl-rl walk skill (`velocity_commands` `[0.35,0,0]`) |
| `POST /api/demo/stop` | Cancel in-flight `ExecuteRskill` (no e-stop latch) + Hub stand |
| `POST /api/skill/execute` | Dispatch `ExecuteRskill` (write-controls; demo Apply for non-walk picks) |
| `POST /api/demo/load` | Cold-reload Bare Go2 or Go2+Z1 (`{"preset":…}`) |
| `GET /api/demo/cricket` | Cricket occupancy + idle remaining (does not reset the timer) |
| `POST /api/demo/cricket/touch` | Operator interaction — reset idle |
| `POST /api/demo/cricket/start` | Laptop: `brev start` + docker + tunnels + attach; on cricket: start graph if down |
| `POST /api/demo/cricket/end` | Cancel skill, stop graph, `brev stop` the Brev host |
| `POST /v1/traces`  | OTLP/HTTP receiver — `application/x-protobuf`    |
| `POST /v1/metrics` | OTLP/HTTP receiver — `application/x-protobuf`    |
| `POST /v1/logs`    | OTLP/HTTP receiver — log lines into the event log |

## Running alongside Jaeger + Prometheus

The dashboard is fine on its own. For post-hoc trace analysis or
Prometheus-style metric history, also bring up the dev compose stack:

```bash
docker compose -f docker-compose.dev.yml up -d otelcol jaeger prometheus
```

Point your workload at `http://localhost:4317` (the OTel Collector)
to fan out: traces → Jaeger UI at `http://localhost:16686`, metrics →
Prometheus at `http://localhost:9090`. The dashboard can still be
attached on a different port for the live pane:

```bash
openral dashboard --port 4318
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
  openral sim run ...   # → otelcol → jaeger + prometheus
```

(Pointing at both the dashboard *and* otelcol simultaneously is a
v2 feature — the OTel SDK supports it via multiple exporters; v1
of the dashboard expects one endpoint at a time.)

## Why this exists

OpenRAL emits all the right OTel spans and metrics by design — the
inference runner carries its own tracing contract, and PR #108 added
the metric surface — and Jaeger renders them beautifully — **after** the run.
For the Day 30 demo and for on-robot debugging, the operator wants
a *live* pane that updates as the robot moves. `openral dashboard` is
that pane; it does not replace Jaeger for post-hoc analysis.

## Relationship to the Foxglove surface

`openral deploy sim --foxglove` brings up a second, read-only pane
(`packages/openral_foxglove_bringup`) that owns the **live ROS scene**: the
robot's URDF posed by TF inside the occupancy grid and voxel map, one Image
panel per camera slot, plus the ROS-side telemetry plane — `/rosout`,
`/diagnostics`, `WorldStateStamped`, episode transitions, reward scores,
detected objects.

The two are complementary, not alternatives, and **nothing here has been
retired in favour of Foxglove**. This dashboard remains the only surface for:

- traces (the trace chip, `/api/traces`, the Jaeger deep link) and OTLP metric
  histograms — Foxglove has no span or histogram model;
- `openral sim run` and `openral benchmark run`, which run HAL-only with no ROS
  graph for a bridge to bridge;
- every write path — E-stop, prompt (text + voice), skill execute, param set.
  The bridge advertises no `clientPublish`, and the e-stop deliberately uses
  this dashboard's launch-time, pre-matched publisher;
- the latched safety state, since `/openral/safety_status` is withheld from the
  bridge pending safety-WG sign-off.
