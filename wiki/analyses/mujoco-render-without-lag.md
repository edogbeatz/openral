---
type: analysis
tags: [openral, mujoco, go2, visualization, dashboard, foxglove]
updated: 2026-09-19
linear: [1-266, 1-267, 1-268, 1-269]
---

# Render MuJoCo to show the dog without lags

Settled 2026-09-18 as a research answer. Home pages:
[[concepts/deploy-sim-visualization]], [[entities/go2]],
[[entities/openral-foxglove-bringup]]. Constraint:
[[analyses/go2-proprio-freshness-cliff]]. Mesh facts:
[[analyses/foxglove-web-meshes-need-package-uri]]. Remote viewer:
[[analyses/cloud-browser-needs-tunnel]].

## What we believe

**Do not send pixels of the sim over the cricket→laptop tunnel. Send
`qpos` (and the free-base pose already on `/odom`) and render MuJoCo on
the laptop.** That is the only path that is both native-MuJoCo and
lag-free under the Go2 walk's 40 ms proprio cliff.

Shipping another EGL camera, a GLFW window on cricket, X11, VNC, or a
third JPEG stream will either lag or steal ticks from the 200 Hz HAL.

## Why the current surfaces lag

Physics lives on cricket (`abundant-turquoise-cricket` / L40S /
`openral-jazzy-go2`, `MUJOCO_GL=egl`, `xvfb-run`). The operator looks
from a Mac through SSH tunnels (`:4318` dashboard, `:8765` Foxglove).
There is no usable `DISPLAY` on the GPU box.

Three surfaces already try to "show the dog":

| Surface | What it actually draws | Why it lags / lies |
| --- | --- | --- |
| Dashboard `top` MJPEG | Native MuJoCo EGL (`mujoco.Renderer` in `MujocoArmHAL.read_images`) | One 640×480 camera @ 15 Hz on the **same single-threaded HAL executor** as 200 Hz proprio. Go2 `front` is `sim_render: false` (no second `mjr_readPixels`). `mjr_readPixels` is the known 30–55 ms stall (upstream [discussion #2222](https://github.com/google-deepmind/mujoco/discussions/2222)). JPEG + SSH is extra. RTF then caps fps. |
| Foxglove Image `/compressed` | The same JPEG | Same render tax. Raw RGB8 used to add ~900 KiB GIL copy per cam; that tax is removed on this branch. Remaining cap is physics + EGL readback. |
| Foxglove 3D URDF | Client-side meshes posed by TF / JointState | Not MuJoCo lighting or geomgroups. Mesh fetch is the reliability bug (`package://` + overlay; Studio caches the miss). Once meshes load, pose traffic is tiny (~200 Hz `/joint_states`) — this path is lag-free *motion* of a **URDF stand-in**, not the sim. |

`SimSensorBridge._setup_viewer` already calls
`mujoco.viewer.launch_passive`. On cricket it fails closed
(`MUJOCO_GL=egl`, no DISPLAY) and the HAL continues headless. That is
correct. Forcing GLFW so a window exists on the VM does not put pixels
on the Mac; X11-forwarding that window is the laggiest option of all.

`OPENRAL_CINECAM_DIR` is the same EGL renderer writing JPEGs to disk
for website clips. It is not a live viewer, and turning it on during a
walk is a third `mjr_readPixels` on the actuation thread.

## Would a second GPU help the video?

**No.** Cricket already has an L40S. 640×480 MuJoCo offscreen is not
fill-rate limited. The dashboard MJPEG stalls on **CPU-side GPU
readback** (`renderer.render()` → `mjr_readPixels`, 30–55 ms), then
JPEG, then the SSH tunnel, on the **same single-threaded HAL
executor** as 200 Hz proprio. A second GPU does not move that work
unless we rewrite the HAL to pin cameras to another process and
another EGL context — and even then the Mac still receives JPEGs.

That rewrite is the wrong architecture. Splitting pose to a second
process is what `openral viz mujoco` already does, without a second
GPU and without pixels. EGL contexts are thread-affine
(`MujocoArmHAL.read_images`); a dual-GPU Brev box also costs credits
we already exhausted.

A GPU on the Mac does not touch the cricket JPEG path. GLFW on the
laptop already uses the local GPU for the kinematic twin.

## Would a cloud deploy help the video?

**No — it is already in the cloud.** Cricket is a Brev L40S. The
dashboard MJPEG and Foxglove Image panels are that box's pixels
tunneled to the Mac
([[analyses/cloud-browser-needs-tunnel]]). Putting the same HAL on
another cloud GPU, or serving `/` over HTTPS instead of SSH, does not
remove `mjr_readPixels` from the walk thread.

SSH multiplexing can add jitter on the JPEG hop. A TLS reverse proxy
might make tiles a bit less bursty on a fat path. That is still a
pixel pipe: the 30–55 ms readback and the 40 ms proprio cliff stay.
A public URL also needs auth + `wss://` (dashboard has none today;
`app.foxglove.dev` blocks remote `ws://`). That is a product ADR, not
a smoothness knob.

A cloud-hosted WASM tab on `GET /api/qpos` is the same kinematic
architecture as `openral viz mujoco`. Pose bytes are tiny; HTTPS vs
SSH is not the fps limiter. The product win is "open a URL," not
smoother video.

## The load-bearing constraint

Go2 locomotion dies on stale proprio. Measured
([[analyses/go2-proprio-freshness-cliff]]): 20 ms age 8/8 survive,
**40 ms 1/8**, 60 ms 0/8. Live age is median 5.1 ms only because
`publish_rate_hz: 200` shares the HAL with cameras. Every extra
offscreen render on that executor pushes age toward the cliff. A
"smoother dog" that tips the walk is not smoother.

EGL contexts are thread-affine (`read_images` docstring). Splitting
cameras onto a second thread is possible but is a HAL change with a
shared `MjData` lock — do not treat it as a viz-only patch.

## Options (ranked)

### 1. Client-side MuJoCo, kinematic `qpos` (recommend)

Physics stays on cricket. The laptop (or the dashboard tab) loads the
same MJCF, applies the live `qpos`, calls `mj_forward`, never
`mj_step`. Native lighting, geomgroups, shadows, mouse orbit. Wire
size is ~100–200 floats at 50–100 Hz (kilobytes), not 640×480 JPEGs.

Two implementations of the same architecture:

- **Local `mujoco.viewer.launch_passive` on the Mac** (most reliable
  today). `MUJOCO_GL=glfw`, `sync(state_only=True)` after each pose.
  Assets from menagerie already on the laptop checkout. Feed from a
  tiny websocket the dashboard already can carry (OTLP already has
  `openral.hal.joint.positions` + `/odom` for the free joint). This is
  the official passive-viewer contract
  ([Python bindings](https://mujoco.readthedocs.io/en/stable/python.html)).
- **`@mujoco/mujoco` WASM in the dashboard** (product-shaped, still
  WIP). DeepMind npm package 3.11.0, Apache-2.0, Chrome+macOS tested.
  TorchRL already ships `send_mujoco_wasm_qpos` /
  `play_mujoco_wasm_trajectory` for this exact "pause=True kinematic"
  mode. Do not `mj_step` in the browser.

Layer: observability (7) consuming joint state the HAL already
publishes. The client model is a visualizer, not a second HAL. Do not
cross into actuation.

### 2. Foxglove URDF driven by `/joint_states` (already in-tree; not native MJ)

Foxglove 2.48 can FK from `sensor_msgs/JointState` without a TF per
link. `/joint_states` is already 200 Hz. Once `package://` meshes
actually fetch, the 3D panel will track the dog without a video
stream. Keep this for ROS telemetry (TF, floor grid, Image overlay).
Do not expect it to look like `simulate`. Head/snout meshes are
collision-only in the URDF (`Head_upper` / `Head_lower`).

### 3. Keep `top` as a proof camera, do not add more (near-term only)

`top` is already the native MuJoCo picture of the dog (menagerie
`track` pose). After the `/compressed` + skip-raw HAL, it is the least
wrong pixel path. Remaining fps is RTF + one EGL readback. Acceptable
as a dashboard tile. **Do not** add a follow-cam, cinecam, or GLFW
viewer on cricket to "fix" it — that is more `mjr_readPixels` on the
walk thread. Shipped cheapen: HAL `front` is `sim_render: false`
(snout cannot show the body). Leave remaining policy cameras alone.
If Bare `/simple` `top` is ~1 Hz while Go2+Z1 is live, the cricket
`go2` yaml is missing `top` — sync + reload, do not add cameras
([[concepts/deploy-sim-visualization]]).

### Reject

- **GLFW on cricket + X11 / VNC / Sunshine.** Extra process, extra
  encode, fights `MUJOCO_GL=egl`, still a pixel pipe. Sunshine/Moonlight
  is a game streamer, not an OpenRAL surface.
- **Foxglove `SceneUpdate` of MuJoCo capsules.** Looks like collision
  geoms. Worse than URDF, still not `simulate`.
- **A third HAL EGL renderer** (cinecam-as-live, "hero cam"). Directly
  taxes the 40 ms cliff.
- **Public `0.0.0.0` dashboard / `wss://` Foxglove** as the way to
  dodge SSH. Auth+TLS is a product ADR ([[analyses/cloud-browser-needs-tunnel]]),
  not a render fix.

## Recommended build (when we implement)

Shipped 2026-09-18 as the first cut (Linear 1-267 / 1-268, parent 1-266):

1. **`openral viz mujoco`** — laptop `mujoco.viewer.launch_passive`,
   `mj_forward` only, `sync(state_only=True)`. Default dashboard
   `http://127.0.0.1:4318`. Pass `--robot robots/go2_z1/robot.yaml`
   (or `--scene`) so composed nq matches the HAL.
2. Pose stream is dashboard-owned: HAL copies `MjData.qpos` onto
   `ProprioFrame` on the sim thread, `record_qpos` on the existing
   `hal.read_state` span (`openral.hal.qpos` / `openral.hal.nq`),
   `GET /api/qpos` polls without cloning the snapshot. Not a camera
   frame and not a new HAL topic.
3. Client never `mj_step`. Gravity, contacts, and the policy stay on
   cricket.
4. `--foxglove` stays the ROS scene. Dashboard `top` stays a proof
   still.
5. `publish_rate_hz: 200` is unchanged.

WASM in the dashboard tab (`@mujoco/mujoco`) reuses the same
`GET /api/qpos` later (Linear 1-269). No layer-boundary ADR: the
client only reads OTLP joints already on `hal.read_state`. An ADR
**is** needed if the HAL grows a new pose-stream topic aimed at a
browser renderer.

## Web player survey (2026-09-19)

There is **no better web player that streams pixels** of cricket's sim.
A browser MuJoCo view is the same architecture as `openral viz mujoco`:
load MJCF locally, write `qpos`, `mj_forward`, never `mj_step`. Poll
`GET /api/qpos` (already on `:4318`). Do not add an EGL camera.

Checked live:

| Candidate | What it is | Verdict |
| --- | --- | --- |
| [`@mujoco/mujoco`](https://www.npmjs.com/package/@mujoco/mujoco) **3.13.0** (Apache-2.0, updated 2026-09-09) | Official DeepMind WASM + JS/TS. Single-thread build needs no COOP/COEP. Demo maps `MjvScene` geoms → Three.js ([`wasm/demo_app/app.ts`](https://github.com/google-deepmind/mujoco/blob/main/wasm/demo_app/app.ts)). Still WIP; Chrome + macOS CI. | **The web engine.** Not a drop-in player — we still write the canvas + pose loop. Matches OpenRAL's Apache-2.0. |
| [TorchRL `mujoco_wasm`](https://docs.pytorch.org/rl/stable/reference/generated/torchrl.render.send_mujoco_wasm_qpos.html) | Generated Vite iframe; `postMessage` `torchrl:mujoco_wasm:setQpos` with `pause=True` then `mj_forward`. MIT. Needs Node. | Closest *streaming* player. Do **not** vendor TorchRL/Vite into the dashboard. Copy the pause+set-qpos pattern onto `/api/qpos`. |
| [zalo/mujoco_wasm](https://zalo.github.io/mujoco_wasm/) | Used to ship community WASM; now a Three.js demo on the official bindings. | Look-and-feel reference. Not a dependency. |
| [`@likang233/mujoco-viewer`](https://www.npmjs.com/package/@likang233/mujoco-viewer) | Thin Three.js mount wrapper around official WASM. | Skip — 3-commit wrapper, not a stream protocol. |
| [julien-blanchon/mujoco-viewer](https://github.com/julien-blanchon/mujoco-viewer) | VS Code MJCF preview (MIT). | Editor, not a live twin. |
| MuJoCo Studio Filament WASM ([PR #3227](https://github.com/google-deepmind/mujoco/pull/3227), `GraphicsMode::FilamentWebGl`) | Experimental native-look simulate in the browser, no Three.js. | Too early (Filament host tools / not an npm player). Revisit later. |

**Web cut (1-269):** dashboard `/` or `/simple` canvas, `@mujoco/mujoco` single-thread + the official Three.js geom sync, poll `GET /api/qpos`, `mj_forward` only. Serve the same composed MJCF + meshes the HAL uses (that asset FS is the hard part, not the player). Keep `openral viz mujoco` for native lighting. Do not stream JPEG. Do not `mj_step` in the tab. Multi-thread `/mt` is for in-browser physics, not our kinematic pose stream.
