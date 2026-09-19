---
type: log
tags: [openral, log]
updated: 2026-09-19
---

Each entry starts with `## [YYYY-MM-DD] <op> | <title>`. Ops: `work` (default close-out), `ingest`, `query`, `lint`, `manual`, `bootstrap`.

## [2026-09-19] query | Bare Go2 walk path changed; Hub ONNX did not

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/log.md
- new: none
- linear: none
- notes: Operator felt the Bare walk skill broke. Weights are still
  `hf://diasAiMaster/unitree-go2-velocity-flat`. What changed: Load
  tars this-branch `rsl_rl_onnx.py` onto cricket (hop/coast), HAL
  plants feet on z=0, chat Apply `[0.5,0,0]` vs demo `[0.35,0,0]`.
  Live id is Acquire Hub walk; two applies today hit
  `deadline_exceeded` 60.0 s so in-tree `horizon_s: 57` is not
  running. Intermittent tip, not a dead card.

## [2026-09-19] work | Walk coast sim test ticks HAL proprio

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/log.md
- new: tests/sim/test_go2_walk_coast_mujoco.py
- linear: none
- notes: End-of-walk fall fix is in. Sim test now builds
  `joint_pos` / `joint_vel` / `base_twist` / `base_pose` from the HAL
  each tick (empty `{}` obs cannot drive walk ONNX). 2 s walk + 2 s
  `[0,0,0]` + 1 s idle-hold stayed upright. Adapter
  `test_adapter_zeros_joystick_on_the_step_clock` records stand in the
  history frame. Reload cricket before live Apply, or the graph still
  idle-holds a mid-gait waypoint.

## [2026-09-19] query | Bare Go2 live occupant; early fall is the known walk tip

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/log.md
- new: none
- linear: none
- notes: Operator saw Bare Go2 and asked why it walks weird then
  falls after a couple of seconds. Live cricket is `go2` /
  `go2mujocohal`, `go2_walk`, ingest ~10 ms, skill idle at Hub-ish
  stand after cancelled `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`.
  Not a UNIT mixup (Load `go2` at 16:58 after `go2_z1`). Hops before
  that were scripted `rskill-zero-go2-hop-fp32` failing in ~6 s.
  Early fall matches the 2026-09-19 loop (started-down z≈0.06, or
  0.43 m then tip). No fall abort — flailing until Stop. Cricket
  `/api/qpos` 404 / laptop 204 (graph has no `openral.hal.qpos`).

## [2026-09-19] work | Walk coasts to stand so the dogs do not fall at the end

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Walk Apply always dumped them when the goal ended —
  `_drain_and_idle_hold` froze a mid-gait waypoint. Walk now
  `horizon_s: 57` + `coast_to_stand_s: 3` so the last 3 s command
  `[0,0,0]` and the ONNX stands the dog; the goal succeeds standing.
  Unset extras on `rsl_rl_onnx` still default to 3.0 s (Hub Acquire
  walk included). `0` disables. Stop is still Hub ResetToPose.
  Reload cricket so `mock`-adjacent `rsl_rl_onnx.py` + the walk YAML
  land. Mid-gait tip on Go2+Z1 is a different (payload) issue.


## [2026-09-19] work | Agents start the app when asked

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/openral.md, wiki/sources/engineering-playbook.md, wiki/index.md, wiki/log.md
- new: .agents/skills/go2-foxglove-view/scripts/start-app.sh
- linear: none
- notes: When asked to start the app / dashboard / cricket / `/simple`,
  agents must run it this turn (`just dashboard` then cricket Start;
  reuse `:4318/healthz`). Canonical
  `.agents/skills/go2-foxglove-view/scripts/start-app.sh`. Do not print
  the command and wait. Docs: `docs/quickstart/dashboard.md`,
  `CLAUDE.md` pointer, skill **When asked to start**.

## [2026-09-19] work | Dashboard hop is gym spring_jump

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/typesafe-in-openral.md, wiki/index.md, wiki/log.md
- new: rskills/rsl-rl-onnx-go2-spring-jump/
- linear: none
- notes: Public hop bake-off on `Go2MujocoHAL` + walk PD. mjlab hop
  and gym hop stay planted (`air_ticks=0`). Gym `spring_jump` hops
  higher than the scripted bounce (`air_ticks≈15`, foot ≈0.34 m,
  `z_max≈0.53 m` vs scripted 51 / 0.25 / 0.47). Picker/Apply is
  `OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32`. Scripted zero hop
  stays as fallback. Cricket Load must copy the rSkill + this-branch
  `rsl_rl_onnx.py` then reload. Acquire still will not warrant hop on
  Go2+Z1 (`check=payload`).

## [2026-09-19] work | go left is turn left, not an S2 plan

- summary: wiki/entities/acquire.md
- touched: wiki/entities/acquire.md, wiki/analyses/typesafe-in-openral.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: `/simple` `parse_intent` dropped "go left" (no walk/turn
  token), so chat never latched a joystick and TypeSafe criteria
  treated it as unclear → reasoner. Colloquial left/right is now
  `turn_left`/`turn_right` yaw; strafe only when the operator said
  strafe or sidestep. Same mapping in the S2 question battery.

## [2026-09-19] work | /simple chat names a fall as retraining

- summary: wiki/entities/acquire.md
- touched: wiki/entities/acquire.md, wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/analyses/wrapping-third-party-weights.md, wiki/analyses/go2-z1-payload-walk-finetune.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Operator asked whether a live fall is the signal to
  train, and to show it in chat. Yes — Adapt is remap, not a
  second training run. `/simple` now polls `/api/state` `fallen`
  (1.0 rad free-joint gate, same number as the mass-balance tool)
  and chats `the unit fell. this skill needs retraining or
  finetuning.` once until RESET. Payload walk is still mjlab
  resume ([[analyses/go2-z1-payload-walk-finetune]]). Hard-refresh
  `/simple` after export. Cricket overlay copies the bool (or
  computes from cricket qpos if the graph is older).

## [2026-09-19] query | File payload-walk finetune as its own analysis

- summary: wiki/analyses/go2-z1-payload-walk-finetune.md
- touched: wiki/analyses/go2-z1-payload-walk-finetune.md, wiki/analyses/wrapping-third-party-weights.md, wiki/analyses/creating-acquire.md, wiki/analyses/isaac-lab-with-openral.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/entities/acquire.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/go2-z1-payload-walk-finetune.md
- linear: none
- notes: Durable home for: Adapt is tag-fork + hold-pad; finetune is
  mjlab resume of model_500.pt with Z1 mass, new skill_id, still 12-D;
  m3 not a drop-in. Recipe stays outside OpenRAL.

## [2026-09-19] query | Payload walk is mjlab resume, not Adapt

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/analyses/wrapping-third-party-weights.md, wiki/log.md
- new: none
- linear: none
- notes: User asked to implement finetune. Path is resume
  model_500.pt in unitree_rl_mjlab with Z1 in the train MJCF, new
  rSkill, Lane B verify. Still 12-D legs. OpenRAL does not run PPO.
  m3 Go2+Z1 walk is not a drop-in (obs + folded arm).

## [2026-09-19] query | Adapt does not retune walk variables

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/analyses/wrapping-third-party-weights.md, wiki/log.md
- new: none
- linear: none
- notes: Confirming: go2→go2_z1 Adapt is tag_family, remapped_contracts
  {}. No action_scale / default_joint_pos / obs-dim rewrite. Arm pose
  hold is the runtime workaround; a payload-aware gait is train, not
  remap.

## [2026-09-19] work | /simple chat says unit changed. on UNIT switch

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/acquire.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Visible `/simple` chat line on an actual Bare Go2 ↔ Go2+Z1
  occupant change is `unit changed.` (picker cold-reload, and yes/Adapt
  after a latched propose for the old twin). Does not fire on first
  Load, reselecting the live twin, or keystrokes. Main-column Load
  status copy is unchanged.

## [2026-09-19] query | move on Go2+Z1 is tag-fork + 12→19 hold-pad

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/log.md
- new: none
- linear: none
- notes: Dashboard SKILL label `move` is the rsl-rl walk card. Chat
  still parses `walk`/`forward`, not the word `move`. Catalog Adapt
  retags go2→go2_z1; Apply still runs the 12-D ONNX. Joint order
  (legs 0–11) + hold-pad + sticky Z1 is what actually drives the
  armed twin. No page rewrite — same belief as wrapping-third-party-weights.

## [2026-09-19] query | Adapt is tag-fork + hold-pad, not a dummy and not a new policy

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/analyses/wrapping-third-party-weights.md, wiki/log.md
- new: none
- linear: none
- notes: Acquire Adapt remaps catalog tags and Apply runs the same
  12-D walk ONNX. Physics that works is hold-pad + sticky Z1 (sim
  tests). Hop reject is real. Fake Acquire in dashboard tests is
  canned JSON; sibling owns adapt.py.

## [2026-09-19] query | Quantization is packing, not wrap/remap

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/analyses/wrapping-third-party-weights.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Follow-up to wrapping third-party weights. NF4/int8 rewrite
  large Linears to fit 8 GB; manifest-driven; Acquire beachhead is
  fp32/bf16. Not a new policy and not embodiment adapt.

## [2026-09-19] work | Scripted hop extend was too short to hop high

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: `gait: jump` extend was 0.16 s — calves still ~−1.4 at land
  so the dog only bounced (foot ≈0.17 m). Cycle is now
  crouch-extend-tuck-land (0.30 / 0.24 / 0.22 / 0.40 s) with poses
  on `rskill-zero-go2-hop-fp32` `policy_extras.jump_*`. Measured
  `air_ticks≈45`, max foot ≈0.25 m, `z_max≈0.47 m`. Reload so
  cricket gets `mock.py` + the hop YAML. HTTP 202 is not hop height.

## [2026-09-19] work | /simple load auto-stands; footer RESET

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: `/simple` Load waits for the occupant then
  `POST /api/demo/recalibrate` (Go2+Z1 parks arm-ready) so the
  playhead lands on Apply. A stored Calibrate playhead restores to
  Apply (Reset if tipped). Chat `#chat-apply` is APPLYING…, not
  STANDING…. Footer `#reset` is the same Recalibrate (tip recovery).
  Classic demo bar still asks Recalibrate on Go2+Z1. Never auto-walk.

## [2026-09-19] query | How Jev helps Acquire

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/log.md
- new: none
- linear: none
- notes: No belief change. Jev is Acquire retrieve ranker (catalog
  Choice, palette-covers Noul, near-parent after family table). Not
  gate / remap / verify. Railway acquire-api typesafe:on. OpenRAL
  TypeSafeGate is a separate installed-palette sidecar.

## [2026-09-19] query | How we adapt non-OpenRAL weights

- summary: wiki/analyses/wrapping-third-party-weights.md
- touched: wiki/analyses/wrapping-third-party-weights.md, wiki/index.md, wiki/entities/openral.md, wiki/entities/acquire.md, wiki/log.md
- new: wiki/analyses/wrapping-third-party-weights.md
- linear: none
- notes: rSkill envelope + family adapter + IO remap (aliases,
  state_adapter, hold-pad) + Acquire tag remap. Not training. Weight
  license stays upstream.

## [2026-09-19] work | /simple chat Apply was a dead click

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: `#chat-apply` only called json-render `emit('press')` and
  looked idle, so Apply seemed dead. Button now calls `onApply` /
  `onStop` directly, hydrates SKILL from `acquire_propose`, and
  paints STANDING… / APPLYING… then STOP / STOPPING… from live
  play. Remap uses the original walk prompt, not `yes`. Hard-refresh
  `/simple`. Restart laptop dashboard for the Python remap-task.
  No pkill / no tunnel steal / no brev start.

## [2026-09-19] work | Bare Go2 hop was a cricket Hub 401

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Apply hop 202 then 401 — cricket lacked
  `rskill-zero-go2-hop-fp32` and jump `mock.py`. Laptop Load now
  syncs those paths. After reload, hop `skill_built` (no 401).

## [2026-09-19] work | /simple Stand is footer; chat owns Apply

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Header `#primary` is Start / Load / Stop only. Footer
  `#stand` is `POST /api/demo/recalibrate`. Chat json-render Apply/Adapt
  Buttons; Apply stands first if needed. Streamdown `isAnimating` +
  `// pulling` CSS shimmer (no new UI package). Camera connecting /
  CAM_TOP unchanged. Hard-refresh `/simple`. No pkill / no tunnel steal.

## [2026-09-19] work | laptop dashboard loads Acquire env file

- summary: wiki/entities/acquire.md
- touched: wiki/entities/acquire.md, wiki/analyses/creating-acquire.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: `openral dashboard` applies `~/.openral/dashboard.env` into
  empty `ACQUIRE_API_*` only. `just dashboard-acquire-env` seeds it
  from Railway. `just dashboard` is write-controls + collector. No
  library URL default. No key in git.

## [2026-09-19] work | /simple chat needs laptop ACQUIRE_API_* 

- summary: wiki/entities/acquire.md
- touched: wiki/entities/acquire.md, wiki/analyses/creating-acquire.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator FAULT after WALK FORWARD on UNIT GO2 was laptop
  `openral dashboard` missing `ACQUIRE_API_URL` / `ACQUIRE_API_KEY`,
  not Railway Jev (`typesafe:on`). Restarted `:4318` with Railway
  `acquire-api` origin + `API_KEY`. No key in git. Banner now says
  when Acquire is unconfigured.

## [2026-09-19] work | /simple top camera fills leftover viewport

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Stream was already 200; tile was aspect-square below the fold
  and connecting hid because canvas is always in the DOM. CAM_TOP now
  always fills leftover viewport. Hard-refresh /simple.

## [2026-09-19] work | laptop Start from STOPPED brought cricket back

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked to start the twin. Brev was STOPPED.
  One POST /api/demo/cricket/start (no second brev start). Graph
  live as Bare Go2; host idle off; laptop /simple overlays ingest.

## [2026-09-19] work | GET / does not start a dashboard; /simple only

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked to comment the root dashboard not to start.
  GET / is 307 to /simple. Banner prints /simple. Classic HTML unused.

## [2026-09-19] work | GET / is the simple dashboard; classic off

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked to turn off the first/classic dashboard.
  GET / and /simple serve the same simple-ui. Cricket attach/reload
  sets IDLE_S=0 so the in-graph collector is not a second idle End.
  /simple idle now follows ingest/graph_running.

## [2026-09-19] work | cricket-host idle End can drop a live /simple twin

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Browser verify after the 56280 latch fix found /simple
  correctly idle (not OP_FAULT). Cricket's own dashboard idle End
  had torn down deploy-sim; laptop idle remaining was still ~14 min;
  :14318 listened but RST. Laptop Start re-attached Bare Go2. Two
  idle clocks. Host PIDs stay in the skill.

## [2026-09-19] work | /simple OP_FAULT 56280 was a stale sshd latch

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator OP_FAULT `Connection closed by 75.2.122.140 port
  56280` while cricket was RUNNING / SHELL READY, occupant Bare Go2,
  tunnels live, graph_running true. `start_error` stayed latched after
  the known brev-start/sshd race; Start treated any start_error as
  fatal (including already_running 200) and Calibrate preferred the
  latch over occupancy. Status + demo-block now clear start_error when
  the graph is up. Host PIDs stay in the skill, not here. No brev start
  / no pkill / tunnels not stolen.

## [2026-09-19] work | /simple chat probes Acquire, asks, then Apply runs

- summary: wiki/entities/acquire.md
- touched: wiki/entities/acquire.md, wiki/analyses/creating-acquire.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: POST /api/chat no longer publishes /openral/prompt. First
  acquire is allow_adapt=false; walk on go2_z1 asks before remap;
  hop on Z1 is payload reject. SKILL empty until fit/adapted
  propose. Apply uses chat walk_command joystick. No second LLM
  on the dashboard; no AcquireSkillTool this slice.

## [2026-09-19] work | Jev retrieve landed on Acquire Railway path

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/entities/acquire.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Sibling `edogbeatz/robo-skill-acquire` now has the TypeSafe
  sidecar on retrieve (search Choice, palette-covers Noul, near-parent
  after family table). Fail-open to bag-of-words. Push to `main` deploys
  `acquire-api` on Railway; Jev stays off until `ACQUIRE_TYPESAFE=1` +
  `TYPESAFE_API_KEY` are set on that service. OpenRAL reasoner gate is
  unchanged.

## [2026-09-19] work | Apply hop is a scripted jump, not the ONNX crouch

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: rskills/rskill-zero-go2-hop-fp32
- linear: none
- notes: Operator "still not enough power / doesnt untouch the
  floor". mjlab hop ONNX cmd calf only −1.76..−1.29, air_ticks=0.
  Isaac hop kp=20 sags calves (actual −2.04). Dashboard hop is now
  `OpenRAL/rskill-zero-go2-hop-fp32` (zero / gait jump, walk PD).
  Headless: air_ticks≈18, max foot ≈0.17 m. HAL keeps walk PD on
  every stand. Reload Bare/Z1. No E-STOP / no pkill.

## [2026-09-19] work | Bare Go2 top hitch was cricket yaml missing top

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/analyses/mujoco-render-without-lag.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md, python/hal/tests/test_camera_rig.py, robots/go2/robot.yaml
- new: none
- linear: none
- notes: Operator "armed dog moves perfectly, bare has performance
  issues". Same MJPEG path. Cricket `robots/go2/robot.yaml` had only
  `front` so `/simple` CAM_TOP was leftover ~0.9 Hz; Z1 yaml already
  had `top`. Synced this-branch yaml + HAL (`sim_render` filter);
  Load Bare Go2. After reload: `top` 15–32 fps / 640 px, `front` no
  thumb. Hard-refresh `/simple`. No extra EGL camera / no pkill.

## [2026-09-19] work | Acquire presentation catalog: fit / adopt / reject

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/entities/acquire.md, wiki/analyses/go2-hop-candidates.md, wiki/index.md, wiki/log.md
- new: none
- linear: 1-225
- notes: Sibling seed DB now fires the three on-stage paths — walk
  fits bare Go2; walk adopts onto go2_z1 (family + remap); unladen
  hop rejects on go2_z1 (payload 4.69 kg, not remappable). Chat
  tool-calling is a separate wire. OpenRAL hop picker still hold-pads;
  Acquire will not warrant it.

## [2026-09-19] work | Hop shuffle was Hub-z under hop legs

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md, python/hal/src/openral_hal/go2.py, python/hal/src/openral_hal/go2_z1.py
- new: none
- linear: none
- notes: Operator "go2 doesnt jump / doesnt untouch the ground /
  moves weirdly". Headless on go2_walk: hop ResetToPose kept Hub
  z=0.27, feet 5.3 cm in the floor, air_ticks=0. HAL now drops
  every stand to contact and uses hop PD (kp=20 kd=0.5) on a
  hop-stand row. Even then the ONNX only crouches (z_span≈0.11 m,
  air_ticks=0) — not a jump. Reload Bare/Z1 for the HAL. No
  E-STOP / no pkill.

## [2026-09-19] query | Go2+Z1 walk fall is three modes, not one bug

- summary: wiki/entities/go2-z1.md
- touched: wiki/log.md
- new: none
- linear: none
- notes: Operator "when walking go2 +z1 fall". Same settled
  picture: home pose ~0.7 s pitch; 60 s deadline freeze-fall; live
  mid-gait tip ~14 s / 3.5 m (headless 8/8). Recalibrate → Apply →
  Stop before 60 s. Do not change arm_mass_scale / heading lock.

## [2026-09-19] work | /simple canvas MJPEG keep-latest

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/mjpeg.ts, python/observability/simple_ui/components/camera-tile.tsx, python/observability/simple_ui/app/globals.css, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/tests/test_dashboard_app.py, python/observability/README.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, CLAUDE.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/simple_ui/lib/mjpeg.ts
- linear: none
- notes: Tile hitch was `<img src=multipart>` remounting on
  spurious error (3 fps slideshow) plus forever latest.jpg polls
  sharing the HTTP/1.1 pool. /simple now fetch+canvas keep-latest;
  still poll stops after the first frame. Operator / does not remount
  a live stream; still interval 1.5 s; dashboard.js?v=cam8. No extra
  EGL camera. Hard-refresh /simple after export.

## [2026-09-19] work | Started /simple against live cricket

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: none
- linear: none
- notes: Operator start. Cricket already RUNNING / SHELL READY;
  occupant Bare Go2 (`go2mujocohal`); tunnels pid 21349 left alone;
  laptop `:4318` serving write+demo; opened
  `http://127.0.0.1:4318/simple`. No brev start / no pkill. Host
  PIDs stay in the Foxglove skill, not this page.

## [2026-09-19] work | /simple Stop cancel is idempotent

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/demo_controls.py, python/observability/tests/test_dashboard_app.py, python/observability/README.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, CLAUDE.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: OP_FAULT `execute_rskill cancel failed` was Stop treating
  CancelGoal return_code 1 as fatal. rclpy cancel-all with nothing
  cancelable is ERROR_REJECTED, not UNKNOWN_GOAL_ID. Parser now
  accepts 0–3 and ERROR_* names; a broken dump still Hub-stands;
  dead graph is 503 once. Restart laptop dashboard. No safety
  check touched.

## [2026-09-19] query | Jev on Acquire is rank, not gate

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/analyses/typesafe-in-openral.md, wiki/entities/acquire.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Yes apply TypeSafe/Jev to Acquire retrieve (catalog Choice,
  need-a-skill Noul, near-parent pick after family table). No: hard
  gate, DEFAULT_TAG_FAMILIES, adapt.py remap, skill_ran. Copy OpenRAL
  questions+policy+opt-in; fail open to token ranker. Not landed;
  lives in robo-skill-acquire.

## [2026-09-19] work | Laptop UNIT switch actually reloads cricket

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Changing UNIT on laptop `:4318` did not change the dog —
  load spawned a Mac relaunch and `/healthz` never dropped; UNIT
  snapped back to cricket `go2_z1`. Laptop load now SSHes
  `/tmp/openral_demo_relaunch.sh` into the container; `/simple` waits
  for `/api/config` `robot_id`. Restart laptop dashboard. Do not
  pkill / steal tunnels.

## [2026-09-19] query | OpenRAL search/reject is not Acquire

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/entities/acquire.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Asked why Acquire if OpenRAL already has search / near-miss /
  reject. It does not have that loop. OpenRAL Hub search +
  `check_capabilities` run and refuse; reasoner `active_search` finds
  objects; HAL near-miss is collision mm. Acquire ranks, remaps family
  near-misses, verifies, then feeds the closed palette.

## [2026-09-19] query | Walk ONNX already turns; no new weights required

- summary: wiki/analyses/no-uturn-rskill.md
- touched: wiki/analyses/no-uturn-rskill.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Corrected "nothing to adapt." diasAiMaster env has
  heading_command + heading ±π + ang_vel_z ±0.5. TypeSafe already
  maps turn_left/right to [0,0,±0.6]. Demo Apply is [0.35,0,0].

## [2026-09-19] work | /simple compact left Calibrate under full-width OP_CAL

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: GET /simple live chrome is a full-width `justify-between`
  OP_CAL + conn row, then a compact left-aligned Calibrate (size sm).
  No “No skill is applied…” subtitle and no ok status under the
  button. UNIT + SKILL + top sit below that cluster.

## [2026-09-19] work | Stop dogs-skills loop + /simple Load the unit

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, CLAUDE.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator stopped the both-dogs `/loop` (sentinels
  AGENT_LOOP_WAKE/TICK_dogs-skills). Heartbeat 214135 and healthz
  214131 already dead; 214136 aborted; no PIDs re-armed; tunnel 21349
  left up. Last matrix tick 7, occupant Go2+Z1. `/simple` empty state
  is **Load the unit**; UNIT follows cricket `robot_id` so a live
  Go2+Z1 graph cannot keep a stale Bare Go2 session label.

## [2026-09-19] query | Still no public U-turn / turn-around weights

- summary: wiki/analyses/no-uturn-rskill.md
- touched: wiki/analyses/no-uturn-rskill.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Hub API (uturn / turn-around / quadruped) empty. Closest
  public ckpt still `m3/go2z1-walking-rsl-rl-v2` (`walking_v2.pt`, no
  ONNX). Isaac official Go2 flat policies are joystick turns. OpenGo
  Turn Around remains paper-only.

## [2026-09-19] work | Laptop cricket camera pipeline first-frame + robot_id

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Laptop `:4318` still an empty collector. Remaining stuck was
  MJPEG TTFB + cricket `/latest.jpg` 404 + sticky stream `error` +
  empty `/api/config` `robot_id`. Seed stills from tunneled
  `/api/state`, sibling `camera-still` on `/simple`, remount stream on
  error, overlay live `go2`/`go2_z1`. Restart laptop dashboard +
  hard-refresh `/simple`. Do not steal `:14318`/`:8765` or pkill.

## [2026-09-19] work | /simple conn pill beside step title

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: GET /simple header is one row — step mark (`// OP_LOAD`) and
  the ingest conn pill sit side by side (`justify-between`), not stacked
  above the title. Same 4-state host-clock contract as operator `/`.

## [2026-09-19] work | Loop tick 7: Bare walk recovered 2.59 m

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Bare walk 2.59 m upright (4/7). Hop 0.09 m. Z1 walk 1.62 m
  z held; hop/arm pass (arm cancel timeout, stand recovered).
  Occupant Go2+Z1.

## [2026-09-19] work | Loop tick 6: Bare walk started down; Z1 good

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Z1 walk 1.46 m z held; hop/arm pass. Bare Recalibrate 200
  then walk already z=0.059 dxy=0 (3/6). Hop recovered. Occupant
  Bare Go2. Watcher wake was our load.

## [2026-09-19] work | Loop tick 5: Bare walk 3/5; Z1 recovered

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Bare walk 1.73 m upright again (3/5). Bare hop 0.08 m.
  Z1 walk 1.24 m z held 0.355 after tick-4 near-tip; hop 0.09 m;
  arm ready. Occupant left Go2+Z1. No Jev this tick.

## [2026-09-19] work | Loop tick 4: Bare walk upright again; Z1 near-tip

- summary: wiki/entities/go2.md
- touched: wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Bare walk 1.73 m upright (2/4). Z1 walk z 0.35→0.15.
  Hop/arm still pass. Occupant Bare Go2.

## [2026-09-19] work | Loop tick 3: Bare walk tipped again; Z1 still good

- summary: wiki/entities/go2.md
- touched: wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Bare walk 2 consecutive tips (z→0.06). Hop + Z1 matrix
  still pass. Occupant left Go2+Z1. Watcher wake was our reload.

## [2026-09-19] work | Loop retest: Z1 still good; Bare move tipped once

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Same matrix, no Jev rerun. Z1 move 2.13 m / hop 0.09 m /
  arm ready. Bare hop 0.10 m. Bare walk this tick fell
  (z→0.06, dxy 0.43 m); Stop+Recalibrate recovered. Intermittent,
  not a new cause. Occupant left Bare Go2.

## [2026-09-19] work | Live both-dogs move/hop/arm; Jev routed the three prompts

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Cricket :14318, Fast DDS, no laptop collector. Jev
  TypeSafeGate (zappi-cli key): walk/hop/arm skip-LLM on the matching
  palette; arm on bare Go2 correctly fell through to reasoner. Bare
  move Δx≈2.40 m / 8 s; Bare hop z_span≈0.10 m after copying the hop
  package + policy.onnx + this-branch rsl_rl_onnx (old cricket adapter
  rejected gait_phase_2; Hub OpenRAL/hop 401). Go2+Z1 move dxy≈1.21 m
  arm frozen ready; hop z_span≈0.08 m; arm_ready 202 held ready.
  Stop before 60 s. Did not pkill / steal tunnels / E-STOP.

## [2026-09-19] work | Go2 front is sim_render false so top is the only EGL camera

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/core/src/openral_core/schemas.py, python/hal/src/openral_hal/_camera_rig.py, python/hal/src/openral_hal/_mujoco_arm.py, python/hal/src/openral_hal/go2.py, python/hal/src/openral_hal/sim_sensor_bridge.py, robots/go2/robot.yaml, robots/go2_z1/robot.yaml, python/observability/src/openral_observability/dashboard/store.py, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/simple_ui/components/simple-play.tsx, packages/openral_rskill_ros/launch/deploy_e2e.launch.py, docs/architecture/repo-state-map.html, docs/methods/00-core-schemas.md, docs/methods/01-hal.md, docs/methods/06-reasoning-wam-safety-observability.md, CLAUDE.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/analyses/mujoco-render-without-lag.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: SensorSpec.sim_render=false on Go2/Go2+Z1 front. HAL skips
  splice + mjr_readPixels. Dashboard /simple hero is top only. 200 Hz
  proprio unchanged. Reload the cricket graph to pick this up.

## [2026-09-19] work | /simple cricket cameras stuck connecting

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md, python/observability/simple_ui/components/camera-tile.tsx, python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/cricket_session.py, python/observability/src/openral_observability/dashboard/demo_controls.py, python/observability/tests/test_dashboard_app.py, python/observability/tests/test_cricket_session.py, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Cricket graph was live (Bare Go2, MJPEG on :14318) while
  laptop /simple tiles waited on GET /api/demo/cricket SSH occupancy
  and the conn pill read empty collector ingest. Laptop now attaches
  /stream immediately, proxies latest.jpg (state-thumb fallback for
  Sep 17 cricket 404), overlays cricket ingest, prefers tunneled
  occupancy. Attach/relaunch set OPENRAL_CRICKET_ROLE=host. Did not
  pkill the graph or steal tunnels.

## [2026-09-19] work | /simple Go2 chat into sidebar

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/go2-chat-bar.tsx, python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_dashboard_app.py, python/observability/src/openral_observability/dashboard/chat.py, python/observability/src/openral_observability/dashboard/app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, CLAUDE.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked to put `#go2-chat` in a sidebar. Right column
  `aside` `lg:w-80` / `lg:flex-row`; stacks under play on narrow
  viewports. Still POST /api/chat. No safety check touched.

## [2026-09-19] query | Hiding a camera tile does not speed up the other

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/analyses/mujoco-render-without-lag.md, wiki/log.md
- new: none
- linear: none
- notes: Browser MJPEG off ≠ HAL read_images off. Both cameras still
  mjr_readPixels on the walk thread. Real cheapen is stop rendering
  front in the HAL. Foxglove 3D is pose, not a second video.

## [2026-09-19] work | /simple Go2 chat bar not sidebar

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/go2-chat-bar.tsx, python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_dashboard_app.py, python/observability/src/openral_observability/dashboard/chat.py, python/observability/src/openral_observability/dashboard/app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, CLAUDE.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked for a chat bar, not a sidebar. `#go2-chat` is
  sticky bottom full-width (not `aside` / `lg:w-80`). Still POST /api/chat
  with origin-absolute URL, Streamdown + json-render. No safety check
  touched.

## [2026-09-19] work | /simple Go2 chat sidebar

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/go2-chat-bar.tsx, python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, CLAUDE.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: GET /simple `#go2-chat` is a right sidebar (`lg:w-80`) that
  does not overlay cameras or Calibrate/Apply. Still `POST /api/chat`
  (same `openral prompt` publisher as `/api/prompt`); origin-absolute
  URL so `/simple` does not resolve to `/simple/api/chat`. 404 stays
  CHAT_FAULT in the pane — no fake reasoner. Calibrate remains one
  POST. No safety check touched.

## [2026-09-19] query | /simple needs no reconnect button

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: ConnIndicator already retries EventSource every 1.5 s with a
  5 s /api/state poll. A reconnect button would be a placebo for
  dead/stale ingest age and would compete with Start engine / the
  one reserved primary CTA. Operator `/` has none.

## [2026-09-19] work | /simple Calibrate one-shot

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/src/openral_observability/dashboard/demo_controls.py, python/observability/tests/test_dashboard_app.py, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md, CLAUDE.md
- new: none
- linear: none
- notes: Operator `demo.reset_to_pose_failed` ~8× was UI
  `RECAL_WAITS_MS` (6 POSTs) plus stand_response still calling
  ResetToPose on a dead graph (estop + pose). GET /simple Calibrate
  is now one POST /api/demo/recalibrate; loader Calibrating… while
  that call is in flight. Backend `_graph_down_response` 503s once
  (`cricket is disconnected`) and does not retry ResetToPose. No
  safety check touched.

## [2026-09-19] work | /simple Go2 chat bar

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/chat.py, python/observability/src/openral_observability/dashboard/app.py, python/observability/simple_ui/, python/observability/tests/test_dashboard_chat.py, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/methods/14-duplication-watch.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: python/observability/src/openral_observability/dashboard/chat.py, python/observability/simple_ui/components/go2-chat-bar.tsx, python/observability/simple_ui/lib/chat-catalog.ts, python/observability/simple_ui/lib/chat-registry.tsx
- linear: none
- notes: Bottom chat bar on GET /simple (not a sidebar). POST /api/chat
  streams mixed text + JSONL for Vercel json-render useChatUI + Streamdown
  and reuses publish_operator_prompt with POST /api/prompt. No second LLM
  on the dashboard. No safety check touched.

## [2026-09-19] work | /simple Go2 embodiment skill gate

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/src/openral_observability/dashboard/demo_controls.py, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/tests/test_dashboard_app.py, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2-z1.md, wiki/analyses/go2-hop-candidates.md, wiki/analyses/creating-acquire.md, wiki/index.md, wiki/log.md
- new: none
- linear: 1-225
- notes: SO101 is out of the embodiment demo. GET /simple SKILL is
  tag-gated — move+hop on Bare Go2 and Go2+Z1, arm_ready only on the
  armed twin. Recalibrate preferWalk still steals arm_ready, not hop.
  Hop Apply stays POST /api/skill/execute. Browser-checked UNIT lists.
  Hop quality on Go2+Z1 still unclaimed. No safety check touched.

## [2026-09-19] work | /simple top ingest conn pill

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/conn.ts, python/observability/simple_ui/components/conn-indicator.tsx, python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/app/globals.css, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/simple_ui/lib/conn.ts, python/observability/simple_ui/components/conn-indicator.tsx
- linear: none
- notes: GET /simple header now has the operator `/` connection pill —
  color-coded circle, waiting… / live / stale / dead, aged on host
  `now_unix - last_ingest_ts` via EventSource `/api/stream` plus
  `/api/state` poll. Not EventSource-up and not the browser clock.
  Theme `rounded-full` is 0 so the dot uses `border-radius: 50%`.
  Camera LIVE badge is unchanged. No safety check touched.

## [2026-09-19] work | laptop Calibrate never PATH hint

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/cricket_session.py, python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/demo_controls.py, python/observability/simple_ui/lib/play.ts, python/observability/tests/test_dashboard_app.py, python/observability/tests/test_cricket_session.py, docs/methods/06-reasoning-wam-safety-observability.md, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: GET /simple Calibrate OP_FAULT was `ros2` not on PATH on the
  laptop collector. `_estop_reset_response` / `_skill_execute_response`
  used local `shutil.which("ros2")`. Laptop now SSHes `ros2` when the
  cricket graph is up; graph/SSH/credits down is **cricket is
  disconnected** (or start_error). classifyStartError maps a leaked
  PATH string to the same copy. No safety check touched.

## [2026-09-19] work | /simple refresh restores wizard state

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_dashboard_app.py, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: sessionStorage now always writes step+robot+skill. Boot paints
  stored step (including running). bootAsync reconciles graph_running /
  skill_running and does not drop a live graph to idle Start. No
  safety check touched.

## [2026-09-19] work | /simple cameras no signal when graph down

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/camera-tile.tsx, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Live 2026-09-19 laptop :4318 — graph_running=false,
  end_in_progress, latest.jpg 204, MJPEG /stream 200 + 0 bytes,
  :14318/:8765 down, Brev credits exhausted then idle End. Overlay
  was hidden (src set, onError never fires). Tiles now probe cricket
  + latest.jpg and show **no signal**. Did not touch Calibrate/Apply
  one-button. No safety check touched.

## [2026-09-19] work | /simple one primary button changes state

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/lib/play.ts, python/observability/tests/test_dashboard_app.py, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: One #primary slot — Start / Calibrate / Apply / Stop. choose
  maps to Calibrate. No dual Calibrate+Apply row. No safety check
  touched.

## [2026-09-19] work | /simple Calibrate + Apply stay on live

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/lib/play.ts, python/observability/tests/test_dashboard_app.py, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: choose hid the primary because primaryAction was none. Live
  now always mounts Calibrate + Apply (Stop while running). Apply
  disabled until calibrated. No safety check touched.

## [2026-09-19] work | /simple camera HMI marks are white on transparent

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/app/globals.css, python/observability/simple_ui/components/hmi-frame.tsx, python/observability/tests/test_dashboard_app.py, wiki/log.md
- new: none
- linear: none
- notes: `.hmi-mark` is `background: transparent; color: #fff` (CAM_FRONT /
  CAM_TOP / 01 / 02 only). UNIT/SKILL/OP_* chips unchanged. Rebuild
  ships the full-width `#live-band`. No safety check touched.

## [2026-09-19] work | /simple UNIT+skill dropdowns full width

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/ui/select.tsx, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: python/observability/simple_ui/components/ui/select.tsx
- linear: none
- notes: Live band is full-width UNIT + SKILL shadcn Selects above
  side-by-side cameras. move =
  Acquire/rskill-rsl-rl-onnx-go2-velocity-flat via POST /api/demo/walk;
  hop = OpenRAL/rskill-rsl_rl_onnx-go2-hop_flat-fp32 via
  POST /api/skill/execute. Selecting a skill does not start motion.
  Footer is powered by openral; top OPENRAL/SIMPLE header+logo gone.
  No safety check touched.

## [2026-09-19] work | /simple UNIT cards sit above cameras

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/components/camera-tile.tsx, python/observability/simple_ui/app/globals.css, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: python/observability/simple_ui/components/camera-tile.tsx
- linear: none
- notes: Live order is title → UNIT two-card grid → side-by-side
  CAM_FRONT/CAM_TOP → LIVE → primary. Engine idle/connecting has
  neither cameras nor cards. Overlays are connecting / no signal
  (`:has(img[src])` hide; `onerror` not `onload`). Start slots
  unchanged. No dropdown. No safety check touched.

## [2026-09-19] work | /simple Start does not jump the column

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_dashboard_app.py, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Idle→connecting kept the idle heading. Button uses a
  3-column slot (icon / label / reserved arrow). Status/Alert sits
  in a min-height region under the CTA. No safety check touched.

## [2026-09-19] query | Bare Go2 video is not a worse encoder than Go2+Z1

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/log.md
- new: none
- linear: none
- notes: Same 640×480 front+top JPEG path. Bare Go2 was the canary for
  RGB8 republish, LANCZOS hitch, and still-poll MJPEG abort. Remaining
  gap is higher RTF (more gait per wall-clock frame) plus an emptier
  snout view. Not a second image processor.

## [2026-09-19] work | /simple credits fail as OP_FAULT

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/cricket_session.py, python/observability/simple_ui/lib/play.ts, python/observability/tests/test_cricket_session.py, python/observability/tests/test_dashboard_app.py, docs/methods/06-reasoning-wam-safety-observability.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Live POST /api/demo/cricket/start returned 202
  “Start Cricket already in progress” with no start_error (old
  dashboard process). startCricket painted that as kind=ok. 202
  in-flight is now connecting (not green); credits/SSH on the watch
  are 400 + OP_FAULT. Dashboard Python must be restarted. No safety
  check touched.

## [2026-09-19] work | /simple Start recovers after idle End

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/cricket_session.py, python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/tests/test_cricket_session.py, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Start was a silent no-op because GET /api/demo/cricket
  sync-SSHed on the uvicorn loop (POST /start queued behind ~12s) and
  bootAsync painted idle over connecting after idle auto-End left
  end_in_progress stuck. GET cricket now to_thread; operator Start
  resets the end guard; Brev credits/SSH surface as OP_FAULT. Engine
  screen has no cameras; live steps show front + top. No safety check
  touched.

## [2026-09-19] work | /simple camera marks sit off the ticks

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/app/globals.css, wiki/log.md
- new: none
- linear: none
- notes: `// CAM_FRONT` / `// 01` sit 8px past the L-bracket (tick size +
  `--hmi-gap`), not on the tick corner. No safety check touched.

## [2026-09-19] query | Cloud deploy does not help dashboard video

- summary: wiki/analyses/mujoco-render-without-lag.md
- touched: wiki/analyses/mujoco-render-without-lag.md, wiki/analyses/cloud-browser-needs-tunnel.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Cricket already is the cloud GPU. Public HTTPS/wss is auth+TLS
  (ADR), not a smoothness knob. Readback + JPEG stay on the HAL
  thread. qpos + client render is the fps path.

## [2026-09-19] query | Second GPU does not help dashboard video

- summary: wiki/analyses/mujoco-render-without-lag.md
- touched: wiki/analyses/mujoco-render-without-lag.md, wiki/log.md
- new: none
- linear: none
- notes: Dashboard MJPEG is readback + JPEG + SSH on the HAL
  executor, not L40S fill rate. A second cricket GPU or a Mac GPU
  does not fix that. Kinematic qpos already is the split.

## [2026-09-19] work | /simple camera marks sit on tick corners

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/hmi-frame.tsx, python/observability/simple_ui/app/globals.css, wiki/log.md
- new: none
- linear: none
- notes: `// CAM_FRONT` and `// 01` share `--hmi-inset` with the
  L-brackets. Label text starts after the 14px arm so the tick sits on
  the badge corner, not over the glyphs. No safety check touched.

## [2026-09-19] work | /simple drops the page grid

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/app/globals.css, wiki/log.md
- new: none
- linear: none
- notes: Removed the 32px square grid on `body`. Page is a flat
  `--background` fill. No safety check touched.

## [2026-09-19] work | /simple drops the operator-dashboard link

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/lib/play.ts, python/observability/tests/test_dashboard_app.py, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Removed the Operator dashboard button. Start engine shows
  Loader2 + Starting… while cricket comes up. `/` still exists; this
  page no longer points at it. No safety check touched.

## [2026-09-19] work | /simple buttons are square; only the camera has inner ticks

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/components/ui/button.tsx, python/observability/simple_ui/components/ui/card.tsx, python/observability/simple_ui/components/ui/badge.tsx, python/observability/simple_ui/components/ui/alert.tsx, python/observability/simple_ui/components/ui/control.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/app/globals.css, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Removed 45° clip-path chamfers from buttons, cards, badges,
  alerts, logo. Camera keeps L-bracket inner ticks only. No safety check
  touched.

## [2026-09-19] work | /simple industrial HMI chrome

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/, python/observability/src/openral_observability/dashboard/app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: python/observability/simple_ui/components/mark.tsx, python/observability/simple_ui/components/hmi-frame.tsx
- linear: none
- notes: Square controls (radius 0), opposite-corner 45° chamfers, `//`
  labels, L-bracket camera ticks. Playhead and APIs unchanged. No safety
  check touched.

## [2026-09-19] work | /simple fails in place with an Alert

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/lib/play.ts, python/observability/simple_ui/components/simple-play.tsx, python/observability/simple_ui/components/ui/alert.tsx, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/simple_ui/components/ui/alert.tsx
- linear: none
- notes: Engine/load/calibrate/apply/stop errors stay on the current
  step. 403 write-controls and unreachable dashboard are named. Retry is
  the same CTA. No safety check touched.

## [2026-09-19] work | /simple is a simple dashboard, not auto-play

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/, python/observability/src/openral_observability/dashboard/app.py, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/simple_ui/components/ui/card.tsx, python/observability/simple_ui/components/robot-card.tsx, python/observability/simple_ui/public/robots/
- linear: none
- notes: Start engine → Bare Go2 / Go2+Z1 cards → Calibrate (no skill on
  that embodiment yet) → Apply walk. Stop is Hub stand. Never auto-walk.
  No safety check touched.

## [2026-09-19] query | Jev splits hop vs walk; Z1 later is not a 19-D policy

- summary: wiki/analyses/go2-hop-candidates.md
- touched: tests/unit/test_reasoner_typesafe.py, wiki/analyses/go2-hop-candidates.md, wiki/analyses/typesafe-in-openral.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Live TypeSafeGate on go2_z1 palette (walk+hop+arm). "hop" /
  "hop in place" skip LLM onto hop with walk_command=none (YAML zeros).
  "walk forward" still velocity-flat + [0.5,0,0]. "adapt hop for z1
  later" falls through (chosen_skill conf 0.43). Extra Nouls: dispatchable
  0.73, quality proven 0.03, new family 0.17. later_work Choice 19-D at
  conf 0.38 — ignore vs sim-measurement plan. TypeSafe tests now include
  hop. No safety check touched.

## [2026-09-19] query | No better web MuJoCo player than official WASM + qpos

- summary: wiki/analyses/mujoco-render-without-lag.md
- touched: wiki/analyses/mujoco-render-without-lag.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md
- new: none
- linear: 1-269
- notes: Surveyed web MuJoCo players. There is no pixel-stream player to
  point at cricket. Best web engine is @mujoco/mujoco 3.13.0 Apache-2.0
  (MjvScene → Three.js). Closest streaming player is TorchRL's pause +
  setQpos Vite iframe — copy the pattern onto GET /api/qpos, do not
  vendor TorchRL. zalo is a demo; Filament Studio WASM is experimental.
  Native openral viz mujoco stays the reliable first cut.

## [2026-09-18] work | /simple uses Zappi's Next.js + shadcn stack

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/, python/observability/src/openral_observability/dashboard/static/simple-ui/, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Replaced the Vite island with Next.js 16.3.3 + React 19.2.6 +
  Tailwind v4 + Geist + shadcn New York (`rsc: true`), same pin set as
  zappi. `pnpm build` static-exports to static/simple-ui/_next. Auto-play
  sequence unchanged. No safety check touched.

## [2026-09-18] work | Simple auto-play page is shadcn New York

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/simple_ui/, python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/static/simple-ui/, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/simple_ui/
- linear: none
- notes: /simple is a Vite+React shadcn (New York) island with Zappi
  ink/paper tokens (Button, Badge). Auto-play sequence unchanged. Rebuild
  with pnpm --dir python/observability/simple_ui build. No safety check
  touched.

## [2026-09-18] query | Hop on Go2+Z1 later is hold-pad, not a new family

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Hop already tags go2_z1. Same 12-D ONNX, runner 12→19, sticky
  arm freeze, go2_z1_walk. Recalibrate/preferWalk still velocity-only.
  Quality unclaimed (bare-dog hop, different stand, walk already pose-
  sensitive). Later = sim measurement, not a second adapter. No safety
  check touched.

## [2026-09-18] work | Simple auto-play page at GET /simple

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/static/simple.html, python/observability/src/openral_observability/dashboard/static/simple.css, python/observability/src/openral_observability/dashboard/static/simple.js, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/src/openral_observability/dashboard/static/dashboard.css, python/observability/tests/test_dashboard_app.py, docs/quickstart/dashboard.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/architecture/repo-state-map.html, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/observability/src/openral_observability/dashboard/static/simple.html, python/observability/src/openral_observability/dashboard/static/simple.css, python/observability/src/openral_observability/dashboard/static/simple.js
- linear: none
- notes: New Zappi-styled auto-play at GET /simple (operator `/` unchanged).
  Cricket start → live front MJPEG → Bare Go2 walk 8 s → POST /api/demo/stop
  (Hub stand) → Go2+Z1 Recalibrate + walk 8 s → Stop. Never waits the 60 s
  deadline (idle-hold mid-gait falls). Abort is Stop, not End Cricket.
  sessionStorage openral.simple.play resumes cold-reload. No safety check
  touched.

## [2026-09-18] work | Go2 hop is a second rsl_rl_onnx customer

- summary: wiki/analyses/go2-hop-candidates.md
- touched: python/sim/src/openral_sim/policies/rsl_rl_onnx.py, tests/unit/test_rsl_rl_onnx_adapter.py, rskills/rsl-rl-onnx-go2-hop-flat/, docs/methods/07-eval-sim.md, docs/methods/14-duplication-watch.md, docs/reference/rskills.md, docs/reference/vla_compatibility.md, docs/architecture/repo-state-map.html, CLAUDE.md, robots/go2/README.md, wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md
- new: rskills/rsl-rl-onnx-go2-hop-flat/
- linear: none
- notes: Same family, not a new ModelFamily. 470-D term-major history-10
  (gait_phase_2 1.5 s, euler RPY, scale 0.25). ONNX fetched via
  policy_extras.onnx_url into ~/.cache/openral; not vendored (upstream
  has no license). Does not claim hop quality. Walk 45-D path unchanged.
  No safety check touched.

## [2026-09-18] work | Start app: cricket STOPPED, Brev out of credits

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: none
- linear: none
- notes: Operator "can you start the app". abundant-turquoise-cricket
  STOPPED / SHELL NOT READY; no :4318/:8765. brev start failed with
  out-of-credits. Did not start a laptop collector (WAITING, not the
  dog). Filed in the operator skill catalog. No safety check touched.

## [2026-09-18] work | Laptop kinematic MuJoCo viewer from GET /api/qpos

- summary: wiki/analyses/mujoco-render-without-lag.md
- touched: python/hal/src/openral_hal/proprio_snapshot.py, python/hal/src/openral_hal/lifecycle.py, python/observability/src/openral_observability/semconv.py, python/observability/src/openral_observability/producer.py, python/observability/src/openral_observability/dashboard/store.py, python/observability/src/openral_observability/dashboard/app.py, python/cli/src/openral_cli/viz.py, python/cli/src/openral_cli/main.py, python/observability/tests/test_dashboard_app.py, python/observability/tests/test_dashboard_topics.py, python/hal/tests/test_proprio_snapshot.py, tests/unit/test_viz_mujoco.py, docs/methods/01-hal.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/methods/08-cli.md, docs/methods/14-duplication-watch.md, docs/architecture/repo-state-map.html, robots/go2/README.md, robots/go2_z1/README.md, wiki/analyses/mujoco-render-without-lag.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: python/cli/src/openral_cli/viz.py, tests/unit/test_viz_mujoco.py
- linear: 1-266, 1-267, 1-268
- notes: First cut of native-MuJoCo-without-lags. HAL copies MjData.qpos
  onto ProprioFrame on the sim thread; record_qpos on the existing
  hal.read_state span; dashboard GET /api/qpos (204 until first sample);
  openral viz mujoco polls and mj_forward only. Did not add cricket EGL
  cameras, GLFW on the VM, or lower publish_rate_hz: 200. WASM viewer
  remains 1-269. No safety check touched.

## [2026-09-18] work | Foxglove Problems tab: WS localhost vs layout sync 400

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md, .agents/skills/go2-foxglove-view/scripts/open-viewer.sh
- new: none
- linear: none
- notes: Three Studio errors, graph was live. Bridge `foxglove.sdk.v1`
  101 on the tunnel; "not reachable" is localhost/old-protocol 400.
  Layout sync 400 Invalid ID format is cloud layout id, not ROS —
  import `/tmp/openral_layout_go2.json`, no `layoutId` in the open URL.
  Reopened `ws://127.0.0.1:8765`. No graph relaunch.

## [2026-09-18] work | Second Go2 skill stood still (resident reuse + queued Apply)

- summary: wiki/entities/go2.md
- touched: packages/openral_rskill_ros/openral_rskill_ros/rskill_runner_node.py, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/src/openral_observability/dashboard/static/index.html, tests/unit/test_reset_resident_episode.py, tests/unit/test_rsl_rl_onnx_adapter.py, python/observability/tests/test_dashboard_app.py, packages/openral_rskill_ros/test/test_rskill_runner_node.py, docs/methods/11-ros2-nodes.md, wiki/entities/go2.md, wiki/entities/go2-z1.md, wiki/concepts/deploy-sim-visualization.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: packages/openral_rskill_ros/openral_rskill_ros/\_resident_episode.py, tests/unit/test_reset_resident_episode.py
- linear: none
- notes: Operator "the dog doesnt move on second skill". Two stacked
  bugs: (1) `_acquire_skill` reused the GPU-resident walk without
  `activate()`, so `last_action` / hold-pad / `horizon_s` leaked —
  second execute stood still or completed on tick 1. Fix:
  `reset_resident_episode` on reuse + from `apply_goal_params_json`.
  (2) Dashboard Apply while a skill was running queued behind the 60 s
  walk. Fix: Apply POSTs `/api/demo/stop` first. Hard-refresh
  `?v=cam6`. No safety check touched.

## [2026-09-18] work | Bare Go2 camera slideshow was still-poll aborting MJPEG

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/src/openral_observability/dashboard/static/dashboard.css, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/store.py, python/observability/src/openral_observability/producer.py, python/hal/src/openral_hal/sim_sensor_bridge.py, docs/methods/06-reasoning-wam-safety-observability.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: After the HAL JPEG path, Bare Go2 tiles were still ~3 fps
  because `ensureCameraPixels` replaced the MJPEG `<img>` with a blob
  still at 200 ms (stream TTFB ~2.6 s) and `/latest.jpg` cloned
  `snapshot()` each poll. Stills now overlay; stream stays; HAL shrink
  is BILINEAR + Pillow rotate. Hard-refresh `?v=cam5`; reload graph
  for Python. No safety check touched.

## [2026-09-18] query | Native MuJoCo dog without lags is client-side qpos

- summary: wiki/analyses/mujoco-render-without-lag.md
- touched: wiki/analyses/mujoco-render-without-lag.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/mujoco-render-without-lag.md
- linear: none
- notes: Operator asked for a reliable way to render MuJoCo in-system
  to show the dog without lags. Settled: do not send pixels from
  cricket. Stream qpos and render kinematically on the laptop
  (`mujoco.viewer.launch_passive` now; `@mujoco/mujoco` WASM later).
  Extra EGL/`mjr_readPixels` on the HAL executor collides with the 40 ms
  proprio cliff. GLFW on cricket has no DISPLAY and X11-forwarding it
  is the laggiest option. Foxglove 3D is a URDF stand-in (mesh fetch,
  not pixel lag). Dashboard `top` stays a native-MJ proof still. No
  code; no safety check touched.

## [2026-09-18] work | Dashboard camera tiles black while LIVE (MJPEG first-frame)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/observability/src/openral_observability/dashboard/app.py, python/observability/src/openral_observability/dashboard/static/dashboard.js, python/observability/src/openral_observability/dashboard/static/index.html, python/observability/tests/test_dashboard_app.py, docs/methods/06-reasoning-wam-safety-observability.md, wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Tiles showed LIVE / age 0 / fps with an empty wrap. OTLP JPEGs
  were live; MJPEG only emitted when JPEG bytes changed, so a standing
  dog sent one part and browsers never committed it. Heartbeat 0.2 s +
  `/api/camera/{src}/latest.jpg` + JS still fallback (`?v=cam4`).
  Cricket got the static files without a graph restart. No safety
  check touched.

## [2026-09-18] work | Start cricket dashboard (already up, Bare Go2)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator "start the dashboard and cricket". VM RUNNING/SHELL
  READY, container Up, graph already Bare `go2_walk` / `go2mujocohal`,
  Mac tunnels `:4318`+`:8765` already live. Reused; did not relaunch,
  Recalibrate, Apply, or End. Opened `http://127.0.0.1:4318/` and
  Foxglove `ws://127.0.0.1:8765`. Occupant is no longer Go2+Z1 (was
  earlier today). Host PIDs stay in the operator skill.

## [2026-09-18] work | Bare Go2 camera slideshow was raw RGB8 serialize

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: python/hal/src/openral_hal/sim_sensor_bridge.py, python/observability/src/openral_observability/dashboard/store.py, python/observability/src/openral_observability/dashboard/app.py, packages/openral_rskill_ros/launch/deploy_e2e.launch.py, docs/methods/01-hal.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/methods/14-duplication-watch.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Bare Go2 dashboard/Foxglove cameras lagged because
  `SimSensorBridge` copied two 640×480 RGB8 frames through rclpy
  (~900 KiB GIL each) and `image_transport republish` subscribed that
  raw topic to make `/compressed`. Dashboard MJPEG also cloned the
  whole snapshot to read one JPEG. Fix: `_rgb8_payload` (single copy),
  skip raw Image when nothing is subscribed, native `/compressed` from
  the dashboard JPEG (one encode, two consumers), sim `--foxglove` does
  not spawn republishers, `store.camera_thumb`. Reload Bare Go2 after
  the HAL lands on cricket; re-import layout onto `/compressed`. No
  safety check touched. Physics RTF can still cap fps.

## [2026-09-18] work | Go2 proprio freshness cliff measured; staleness and twist-frame excluded from the live tip

- summary: wiki/analyses/go2-proprio-freshness-cliff.md
- touched: tools/go2_z1_mass_balance.py, tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py, docs/reference/go2-z1-mass-balance.md, docs/methods/10-tools.md, scenes/deploy/go2_z1_walk.yaml, scenes/deploy/go2_walk.yaml, wiki/analyses/go2-proprio-freshness-cliff.md, wiki/analyses/go2-z1-arm-pose-decides-the-walk.md, wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: wiki/analyses/go2-proprio-freshness-cliff.md
- linear: none
- notes: Operator asked whether TypeSafe could test the live fall. It cannot —
  layer-4 text judgment, ≤1 Hz, no tensors, and the walk is a direct
  dashboard apply it never sees ([[analyses/typesafe-in-openral]]). Static
  typing was the productive reading: `WorldState.base_twist` is an untagged
  6-tuple with no frame, so a world-vs-body mix-up passes `mypy --strict`.
  Chasing it closed BOTH remaining hypotheses. (1) No frame mismatch — the
  twist passes verbatim through every hop and the HAL's `qvel[3:6]` is
  already body-frame `base_ang_vel`; also established that the runner reads
  the aggregator **in-process**, so `publish_rate_hz_fast` (30 Hz) is not in
  the policy path. (2) Staleness — new `stale` mode found a sharp cliff
  (8/8 at 20 ms, **1/8 at 40 ms**, 0/8 at 60 ms), which retro-justifies the
  200 Hz publishers the scenes already carried on an unquantified comment;
  then measured the live age at median 5.1 ms / p90 10.2 ms (n=469, matched
  externally against the 200 Hz `/joint_states` history), inside the safe
  band. Excluded. Live tip is also **intermittent** (~3 in 5; two clean
  34 s / 5.5 m walks this session), so the earlier "3/3 reproducible" is
  downgraded. Landed: `stale` CLI mode, `PROPRIO_AGE_CLIFF_TICKS`,
  `lateral_drift_m` / `tip_times_s` on the rollout records, and a sim test
  bracketing the cliff at 1 and 3 ticks so a rate change cannot cross it
  silently. Open: the tip itself (11 hypotheses eliminated); frame-tagged
  twist types want an ADR; `/openral/world_state_fast` publishes 11.2 Hz
  against its 30 Hz timer (real, not the policy path). No safety check
  touched; twin left upright.

## [2026-09-18] work | Start cricket dashboard (VM up, container down)

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator "start the dashboard". Cricket RUNNING/SHELL READY but
  docker exited and graph empty. docker start + relaunch Go2+Z1 + tunnel
  `:4318`/`:8765` (`ControlMaster=no`). Live `go2_z1` / ingest ~0 s /
  MJPEG. No local collector — use `:4318` not `:14318`. Catalog:
  brev RUNNING ≠ graph. Did not Recalibrate or Apply.

## [2026-09-18] work | TypeSafe S2 gate (opt-in, Go2/Go2+Z1 questions)

- summary: wiki/analyses/typesafe-in-openral.md
- touched: python/reasoner/src/openral_reasoner/typesafe_questions.py, python/reasoner/src/openral_reasoner/typesafe_policy.py, python/reasoner/src/openral_reasoner/typesafe_gate.py, packages/openral_reasoner_ros/openral_reasoner_ros/reasoner_node.py, tests/unit/test_reasoner_typesafe.py, wiki/analyses/typesafe-in-openral.md, wiki/sources/typesafe-system-one.md, wiki/entities/openral.md, wiki/index.md, docs/methods/06-reasoning-wam-safety-observability.md, docs/methods/14-duplication-watch.md, docs/architecture/repo-state-map.html, mypy.ini, pyproject.toml, wiki/log.md
- new: python/reasoner/src/openral_reasoner/typesafe_questions.py, python/reasoner/src/openral_reasoner/typesafe_policy.py, python/reasoner/src/openral_reasoner/typesafe_gate.py, tests/unit/test_reasoner_typesafe.py
- linear: none
- notes: OPENRAL_TYPESAFE=1 + TYPESAFE_API_KEY; just sync --group typesafe.
  Skip-LLM walk/arm via goal_params_schema; safety Noul → WaitTool.
  Missing SDK / API fail open to the LLM. Not S1, not the C++ kernel.
  Unreachable TypeSafe does not invent a safety refuse.

## [2026-09-18] query | TypeSafe as S2 judgment sidecar, not S1

- summary: wiki/analyses/typesafe-in-openral.md
- touched: wiki/analyses/typesafe-in-openral.md, wiki/sources/typesafe-system-one.md, wiki/entities/openral.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/typesafe-in-openral.md, wiki/sources/typesafe-system-one.md
- linear: none
- notes: TypeSafe Jev is already in zappi-cli (`@typesafe-ai/sdk@0.6.0`).
  OpenRAL wiring stays in `python/reasoner/` behind TYPESAFE_API_KEY +
  OPENRAL_TYPESAFE=1. Highest leverage is palette shortlist + skip-LLM
  routing + finishing the partial substitute-skill rung. Must not publish
  ActionChunk or enter the C++ kernel. Name collision: TypeSafe "System
  One" ≠ OpenRAL S1.

## [2026-09-18] work | Helix 2.5 arXiv-style review

- summary: wiki/analyses/helix-25-zero-shot-home-generalization.md
- touched: wiki/analyses/helix-25-zero-shot-home-generalization.md, wiki/sources/figure-helix-lineage.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/helix-25-zero-shot-home-generalization.md, wiki/sources/figure-helix-lineage.md
- linear: none
- notes: Narrative review of public Figure posts (Helix → 02 → Index → 2.5). Not original experiments. 56% vs 9% and S2/S1/S0 reconstructed from company blogs; 2.5 backbone unpublished.

## [2026-09-18] work | Hackathon demo scoped to Go2 only

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/log.md
- new: none
- linear: 1-225
- notes: Operator call — drop the so101 arm from the stage demo.
  Embodiment story is now bare Go2 vs Go2+Z1 under one 12-D walk
  skill (hold-pad 12→19). Linear 1-225 still says dual-body; it is
  backlog and now out of date. Side benefit: the demo is entirely
  fork-owned code, no upstream SmolVLA package on stage.

## [2026-09-18] query | Go2 is fork-only; SO-101 wrap is upstream's

- summary: wiki/entities/go2.md
- touched: wiki/entities/go2.md, wiki/log.md
- new: none
- linear: 1-225
- notes: Corrects this morning's earlier note ("distinctive upstream
  offer is Go2+Z1, Go2 HAL already in-tree") — wrong. `git cat-file`
  vs `upstream/master` (61fb003, 2026-09-17): robots/go2, go2.py,
  rsl_rl_onnx.py, rskills/rsl-rl-onnx-go2-velocity-flat and
  rskill-zero-go2_z1-arm_ready-fp32 are all FORK-ONLY; go2_z1 is
  branch-only. The Adrian PR offer is the whole Go2 stack, not just
  the composite. Inverse for SO-101:
  rskill-smolvla-so101-eraser_place-bf16 IS upstream (we changed one
  README line) and its weights already sit on the OpenRAL HF org — do
  not offer to host it. Neither of our two rSkills ships our weights
  (one wraps diasAiMaster BSD-3, one is `local://` weightless), so
  there is nothing for Adrian to host at all.

## [2026-09-18] query | Later train farm: Lab or mjlab for loco, not Gym

- summary: wiki/analyses/isaac-lab-with-openral.md
- touched: wiki/analyses/isaac-lab-with-openral.md, wiki/log.md
- new: none
- linear: none
- notes: When Acquire trains: Go2-class rsl-rl needs Isaac Lab or
  mjlab. Gym is legacy. SO-101 stays LeRobot. OpenRAL sidecar is run
  not PPO.

## [2026-09-18] query | Future train is Lab or mjlab, not Gym+Lab

- summary: wiki/analyses/isaac-lab-with-openral.md
- touched: wiki/analyses/isaac-lab-with-openral.md, wiki/log.md
- new: none
- linear: none
- notes: Do not tell Adrian we need Isaac Gym and Lab. Gym is
  deprecated. Current walk ONNX is unitree_rl_mjlab. Future: one
  recipe. Acquire still does not train.

## [2026-09-18] query | OpenRAL quantize is manifest-driven, not automatic

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/log.md
- new: none
- linear: none
- notes: Tell Adrian sorry, we did not quantize. OpenRAL can pack
  VLAs on load when dtype says nf4/int8 (GR00T-class defaults NF4);
  ONNX and our fp32/bf16 cards do not. Never silent (WARNING on
  override).

## [2026-09-18] query | No quantization on the Acquire beachhead

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/log.md
- new: none
- linear: none
- notes: Confirmed. Go2 walk fp32 ONNX, Z1 fp32 zero hold, SO-101
  SmolVLA bf16 wrap. Do not tell Adrian "we quantized skills." OpenRAL
  still ships unrelated NF4 rSkills.

## [2026-09-18] query | Go2+Z1 arm is scripted hold, not quantized

- summary: wiki/entities/go2-z1.md
- touched: wiki/entities/go2-z1.md, wiki/analyses/creating-acquire.md, wiki/log.md
- new: none
- linear: none
- notes: Corrected the Adrian story. Z1 is not a quantized manipulator
  skill. It is `rskill-zero-go2_z1-arm_ready-fp32` (named poses) plus
  12→19 hold-pad of the same rsl-rl walk and a sticky HAL arm freeze.
  SO-101 eraser_place is a bf16 wrap of an existing SmolVLA, also not
  a quantize-to-adapt.

## [2026-09-18] query | What to answer Adrian on Isaac Lab + hackathon

- summary: wiki/analyses/isaac-lab-with-openral.md
- touched: wiki/analyses/isaac-lab-with-openral.md, wiki/analyses/creating-acquire.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/isaac-lab-with-openral.md
- linear: 1-225
- notes: Slack reply to Adrian. Hackathon date not in Linear (Acquire
  project has no targetDate). MVP = Lab-trained ONNX + MuJoCo verify;
  do not wait on a Go2 Lab env. Distinctive upstream offer is Go2+Z1
  and fork deltas, not a from-scratch Go2 HAL. Embodiment adapt is
  contract remap, not a private quantized weight dump unless we
  actually have one.

## [2026-09-17] work | Operator stopped cricket

- summary: .agents/skills/go2-foxglove-view/SKILL.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: none
- linear: none
- notes: `brev stop abundant-turquoise-cricket` → STOPPED (L40S
  d4dyyrsd1). Last occupant Go2+Z1. Host-only; no code. Start Cricket
  to resume.

## [2026-09-17] work | Go2+Z1 mass balance: CoM centring rejected, `ready` spawn fixes the walk

- summary: wiki/analyses/go2-z1-arm-pose-decides-the-walk.md
- touched: wiki/entities/go2-z1.md, wiki/index.md, wiki/log.md, robots/go2_z1/robot.yaml, robots/go2_z1/README.md, python/hal/src/openral_hal/go2_z1.py, docs/methods/01-hal.md, docs/methods/10-tools.md, tests/sim/test_go2_z1_hal_mujoco.py
- new: wiki/analyses/go2-z1-arm-pose-decides-the-walk.md, tools/go2_z1_mass_balance.py, docs/reference/go2-z1-mass-balance.md, tests/sim/test_go2_z1_rsl_rl_onnx_mujoco.py
- linear: none
- notes: >-
  Asked to park the arm at the composite's centre of mass to help the shared
  rsl-rl walk skill. Built the measurement tool, found the centred pose
  (0.60 mm vs 54.8 mm for `ready`), and the rollout batteries **rejected the
  premise**: survival is uncorrelated with CoM offset (0.45 mm pose 0/6,
  54.7 mm pose 6/6) and the centred pose tracks 27 % slower, so it was not
  shipped. Pitch inertia fails as a second explanation (1.335 vs
  1.337 kg m² gave 6/6 vs 0/6). Arm pose is still decisive — mechanism
  unexplained, failures pitch over inside the first second with zero arm
  contacts. En route this exposed a real defect: the menagerie `home` spawn
  pose falls 0/8 at honest mass, and since a 12-D locomotion row leaves the
  sticky arm hold alone, a walk before any Recalibrate rode it. Fixed by
  spawning at `ready` (`GO2_Z1_SPAWN_JOINT_TARGETS`), verified 5/5 vs 0/5 on
  the production path, guarded in both directions.
  Still open: `arm_mass_scale: 0.01` may be over-correcting — honest mass did
  not tip headless, but the original tip was seen on the live `deploy sim`
  graph (ROS jitter + wall-clock idle stepping this loop lacks), so re-measure
  there before touching the manifest. `fold` ships with 5 arm self-contacts.
  Method lesson: the first pass concluded the opposite from single
  deterministic rollouts; randomise initial conditions.

## [2026-09-17] query | How we create Acquire on this harness

- summary: wiki/analyses/creating-acquire.md
- touched: wiki/analyses/creating-acquire.md, wiki/entities/acquire.md, wiki/entities/openral.md, wiki/index.md, wiki/log.md
- new: wiki/entities/acquire.md, wiki/analyses/creating-acquire.md
- linear: 1-189, 1-225
- notes: Read sibling edogbeatz/robo-skill-acquire (wiki + acquire-api
  v0.1.2) and Linear project Acquire. OpenRAL = runtime substrate;
  Acquire = retrieve/reject/adapt/verify on top. Not a better harness,
  not a training farm. Warranty still blocked on cricket skill_ran for
  rsl_rl_onnx velocity-flat. No code change.

## [2026-09-17] query | Closest Go2 hop is a 470-D mjlab ONNX

- summary: wiki/analyses/go2-hop-candidates.md
- touched: wiki/analyses/go2-hop-candidates.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/go2-hop-candidates.md
- linear: none
- notes: Best public hop: Renkunzhao/legged_rl_deploy
  policies/go2/mjlab/hop (Mjlab-Hopping-Flat-Unitree-Go2, 12-D
  JOINT_POSITION, 50 Hz, gait_phase 1.5 s, 47×10 obs, scale 0.25).
  Current rsl_rl_onnx walk adapter is 45-D history-1 scale 0.5 and
  cannot load it. SportClient FrontJump/FreeBound/FreeJump is real
  firmware only. Hub has no go2 hop/jump models. No license on that
  deploy repo. No code change.

## [2026-09-17] query | No public U-turn skill outside the repo either

- summary: wiki/analyses/no-uturn-rskill.md
- touched: wiki/analyses/no-uturn-rskill.md, wiki/index.md, wiki/log.md
- new: none
- linear: none
- notes: Hub search (uturn / go2 turn / rskill), Unitree SportClient
  header, GitHub OpenClaw skills, OpenGo arXiv:2604.01708. No named
  UTurn API. OpenGo Fig. 1 "Turn Around" is paper-only (no code).
  Compose from Looper `turn left 180` or dongsheng duration yaw.
  Closest policy: m3/go2z1-walking-rsl-rl-v2 (ωz ±2 rad/s).

## [2026-09-17] query | Video stutter was raw RGB8 + 1 Hz thumbs, not Go2+Z1

- summary: wiki/concepts/deploy-sim-visualization.md
- touched: wiki/concepts/deploy-sim-visualization.md, wiki/log.md, .agents/skills/go2-foxglove-view/SKILL.md
- new: none
- linear: none
- notes: Operator asked why video was very slow, then said it is
  fixed on the second robot. Live cricket dashboard is Go2+Z1;
  `front`/`top` 640×480 age ~0 with thumbs flowing. Cause already
  filed (1 Hz still-card thumbs, SSE re-shipping JPEGs, Foxglove raw
  640×480 RGB8 ~18 MB/s saturating the laptop tunnel / 10 MB send
  buffer). Go2+Z1 reload spawned `/compressed` republishers + 25 Hz
  cap. Bare Go2 can still stutter until that graph restarts and its
  layout is re-imported onto `/compressed`. No code change.

## [2026-09-17] query | No dedicated U-turn rSkill

- summary: wiki/analyses/no-uturn-rskill.md
- touched: wiki/analyses/no-uturn-rskill.md, wiki/entities/go2.md, wiki/index.md, wiki/log.md
- new: wiki/analyses/no-uturn-rskill.md
- linear: none
- notes: Repo + Linear search found no u-turn / uturn / turn-around
  skill. Closest: rsl-rl Go2 joystick `[vx, vy, yaw_rate]` (demo is
  forward `[0.35, 0, 0]`; yaw-only is an override, not a 180° skill);
  Nav2 navigate-to-pose documents 180° as `base_link` z=1,w=0 but needs
  mobile_base + body_twist (Go2 undeclared); InternVLA-N1 can emit
  yaw BODY_TWIST from an instruction, same actuator gap. turning-on-radio
  is a radio task. No code change, no commit.

## [2026-09-17] query | Cloud + browser is cricket tunnels, not a public URL

- summary: wiki/analyses/cloud-browser-needs-tunnel.md
- touched: wiki/analyses/cloud-browser-needs-tunnel.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/openral-foxglove-bringup.md, wiki/index.md, .agents/skills/go2-foxglove-view/SKILL.md, wiki/log.md
- new: wiki/analyses/cloud-browser-needs-tunnel.md
- linear: none
- notes: Operator asked if the twin can run in the cloud and show in a
  browser. Yes: cricket already is that (Start Cricket → SSH
  `:4318`/`:8765` → dashboard + app.foxglove.dev on localhost). A
  shareable https link is not shipped — dashboard has no auth
  (`_exposure_warning` / issue #44; non-loopback + write-controls is
  CRITICAL, warns don't refuse) and Foxglove web blocks remote `ws://`
  mixed content. Public view would be TLS + auth in front of both ports;
  ADR in private management log first. No code change, no commit.

## [2026-09-17] work | Condense Go2 cricket demo lessons into skills

- summary: .agents/skills/go2-foxglove-view/SKILL.md
- touched: .agents/skills/go2-foxglove-view/SKILL.md, wiki/concepts/deploy-sim-visualization.md, wiki/entities/go2-z1.md, wiki/log.md
- new: none
- linear: none
- notes: Condensed Troubleshooting Catalog to eight durable operator
  bullets (WAITING/tunnel+127.0.0.1, cameras onload/:14318, Recalibrate
  demo, Apply≠arm_ready, 502 runner latch+estop_reset, load/idle/
  deadline, occupancy/hostname lie, arm soft-physics OK / no heading
  lock). Tightened Operator start + Current beliefs. Promoted :14318
  bounce, 127.0.0.1 preference, hostname lie, reasoner-not-required,
  and arm-mass expectation to wiki. openral-wiki / robot-bring-up
  unchanged (process already correct). No commit / no graph restart.

## [2026-09-17] work | Walk dispatch failed: runner estop latch

- summary: .agents/skills/go2-foxglove-view/SKILL.md + Recalibrate EstopPublisher
- touched: .agents/skills/go2-foxglove-view/SKILL.md, python/observability/.../demo_controls.py, app.py, tests, wiki/concepts/deploy-sim-visualization.md, wiki/log.md
- new: none
- linear: none
- notes: Exact error 502 `walk dispatch failed` /
  `action server rejected the goal`. End Cricket latched skill_runner;
  Recalibrate cleared kernel only. Live: `POST /api/estop_reset` then
  walk 202 `Acquire/rskill-rsl-rl-onnx-go2-velocity-flat`. Reasoner not
  required. Code: Stand/Recalibrate pass EstopPublisher. No commit /
  no E-STOP. User: hard-refresh `:4318`, picker walk, Apply, Stop before 60s.

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
    - Recalibrate left upright. One `go2_z1_walk` graph. No E-STOP, no
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
    > from this page — that was the on-cricket-only implementation.

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
  panels need the paired CameraInfo on the _manifest_ `frame_id`; the
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
