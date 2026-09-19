---
type: index
tags: [openral, index]
updated: 2026-09-19
---

# OpenRAL Second Brain — Index

A maintained knowledge base for **OpenRAL**, the open Robot Agentic Layer.
Pages are cross-linked with `[[wikilinks]]`. Normative engineering stays in
`docs/`, `docs/METHODS.md`, Pydantic schemas, and IDL. This wiki is
compounding agent memory for tasks, synthesis, and contradictions.

Start here: [[entities/openral]].

**Tasks must cite this wiki.** See [[concepts/task-wiki-contract]].
**Finished work is filed here** — update pages, append `wiki/log.md`.
See [[concepts/wiki-maintenance-workflow]].

> The four pages lost in the 2026-09-16 partial restore were rebuilt the
> same day from their in-repo sources (`CLAUDE.md`,
> `docs/architecture/repo-map.md`, `README.md`, the wiki skill). They are
> re-derivations, not the original text. See `wiki/log.md`.

## Entities

- [[entities/openral]] — the project overall (harness, eight layers, where truth lives). Opt-in TypeSafe S2 gate: [[analyses/typesafe-in-openral]].
- [[entities/acquire]] — install-on-the-fly rSkill product on top of this harness (`edogbeatz/robo-skill-acquire`). `/simple` chat is the landed probe/ask wire (laptop `:4318` loads `~/.openral/dashboard.env` via `just dashboard-acquire-env`). Not Hub search, not `check_capabilities`, not collision near-miss.
- [[entities/go2]] — Unitree Go2 sim-only quadruped: 12-DoF, torque-motor PD hold, `go2_bench` vs `go2_walk`, `front` declared (`sim_render: false`) + viz-only `top`. Walk coasts to stand in the last 3 s. Cricket checkout without `top` makes `/simple` CAM_TOP leftover ~1 Hz while [[entities/go2-z1]] looks live.
- [[entities/go2-z1]] — Go2 + Z1 19-DoF composite; Recalibrate parks Z1 at arm-ready; rsl-rl walk hold-pads 12→19 and qpos-snaps **arm only**; `/simple` Adapt is tag-fork not a payload gait ([[analyses/go2-z1-payload-walk-finetune]]).
- [[entities/openral-foxglove-bringup]] — read-only Foxglove live-scene package; `package://` meshes via ament overlay; layout generator.

## Concepts

- [[concepts/second-brain]] — what the wiki is and is not.
- [[concepts/task-wiki-contract]] — Linear / PR / agent tasks cite wiki pages; how the wiki references Linear back.
- [[concepts/wiki-maintenance-workflow]] — ingest, query, lint, **Done / finish** close-out, log format; cricket/dashboard/Foxglove start failures also append `.agents/skills/go2-foxglove-view/SKILL.md` the same turn.
- [[concepts/deploy-sim-visualization]] — hybrid `--dashboard` + `--foxglove`; **agents start the app when asked** (`just dashboard` / `scripts/start-app.sh` this turn, do not print and wait); laptop viewer vs remote graph (cloud+browser **is** cricket + SSH tunnels; no public URL — dashboard has no auth, Foxglove web needs `ws://localhost` / mixed-content); display frame, floor, up-axis; host-clock freshness; Event log collapsed live-debug; command-band counters are session totals (Recalibrate does not zero them); write-controls **demo** bar (Bare Go2 auto-calibrates then Apply; Go2+Z1 asks Recalibrate first then defaults Apply to walk, not saved arm_ready; a **second Apply** stops the running skill first so the dog actually moves; **Stop** cancels the skill without e-stop; laptop **Start Cricket** `brev start`s + tunnels Foxglove `:8765` and cricket `:4318`, or `:14318` only when a local collector already owns `:4318`; **End Cricket** + 15 min idle auto-stop still `brev stop`); `GET /simple` is the only operator dashboard (`GET /` 307s; classic HTML is not started); ingest conn pill on the same full-width row as the step mark (`justify-between`; waiting… / live / stale / dead, host clock, same as `/`; no reconnect button — EventSource retries, dead/stale is ingest age, Start engine is recovery); compact left-aligned Calibrate under that row (no skill-applied subtitle); Start engine → Load the unit (empty UNIT; live occupant wins over session Bare Go2) + empty SKILL until chat Acquire propose (walk fit / adapt-ask / hop reject) above full-width top → header primary is Start / Load the unit / Stop only; footer RESET is POST /api/demo/recalibrate (503 once if cricket is disconnected — no ResetToPose retry); Load auto-stands so Apply is ready; chat `#chat-apply` APPLYING… when stood (STANDING… only if not; same button is STOP / STOPPING… while running); never auto-walk; Next.js 16 + shadcn New York; industrial HMI chrome: square chamfers, `//` labels); footer powered by openral; right Go2 chat sidebar via POST /api/chat (json-render useChatUI + Streamdown `isAnimating` / `// pulling` shimmer while waiting; Apply/Adapt Buttons; sibling Acquire probe/ask, no reasoner prompt publish; UNIT switch chats `unit changed.` only when the occupant actually changes; a base tip past 1.0 rad chats `the unit fell. this skill needs retraining or finetuning.` once until RESET); engine screen has no pickers; CAM_TOP fills leftover viewport; live tiles fetch `/stream` into a canvas (keep-latest JPEG, no `<img src=multipart>` remount) plus a sibling `latest.jpg` still until the first frame (no `GET /api/demo/cricket` occupancy SSH); **no signal** on `latest.jpg` 204 only when the stream has never painted (404 keeps the stream; laptop seeds MJPEG from cricket `/api/state` thumbs); laptop conn pill overlays cricket ingest so it is not stuck `waiting…`; laptop `/api/config` `robot_id` is the tunneled cricket identity; Start paints Starting… before any await and recovers after idle auto-End; Brev credits/SSH/403 fail in place; a live graph clears a stale 56280 `start_error`; laptop Calibrate/Apply/Stop SSH `ros2` into cricket — graph down is **cricket is disconnected**, never a PATH hint; Stop cancel-all is idempotent (`ERROR_REJECTED` still Hub-stands); `GET /api/demo/cricket` occupancy SSH is `asyncio.to_thread`; `brev ls` RUNNING is not occupancy (container can be exited); laptop `openral dashboard` is an empty collector (WAITING) — live twin is cricket `deploy sim`; Bare Go2 / Go2+Z1 cold-reload must not `pkill -f` its own argv; operator `/` always mounts Go2 `top` even while WAITING; opaque `waiting for camera` placeholder must not cover live MJPEG (tiles start `is-streaming`); operator `/` does not remount a live `<img>` stream on spurious `error` (still poll 1.5 s, `?v=cam8`); Foxglove Image panels on `/compressed`; start failures catalog in `.agents/skills/go2-foxglove-view/SKILL.md`. Native-MuJoCo dog without lags is **not** another cricket EGL camera — stream `qpos`, render on the laptop with `openral viz mujoco` ([[analyses/mujoco-render-without-lag]]).

## Sources

- [[sources/engineering-playbook]] — `CLAUDE.md` (agent + contributor contract); what it governs and where it points.
- [[sources/repo-map]] — `python/*` vs `packages/*` vs `cpp/`, the state-map PR gate, out-of-tree repos.
- [[sources/figure-helix-lineage]] — Figure Helix → Helix 02 → Index → Helix 2.5 public posts (Sep 2026 30-home eval).
- [[sources/typesafe-system-one]] — TypeSafe Jev / System One docs (typed parallel questions; not OpenRAL S1).

## Analyses

- [[analyses/helix-25-zero-shot-home-generalization]] — arXiv-style review of Helix 2.5: Index pretraining, S2/S1/S0, 56% vs 9% in 30 unseen homes; company eval, not independent.
- [[analyses/typesafe-in-openral]] — TypeSafe as S2 judgment sidecar (skill shortlist, skip-LLM routing, hop vs walk vs arm; colloquial **go left** is `turn_left` yaw); never S1 / never safety kernel / never gait physics. Second legal surface: Acquire catalog rank ([[analyses/creating-acquire]]).
- [[analyses/foxglove-web-meshes-need-package-uri]] — Studio (web and desktop) only requests `package://` from the bridge; the overlay works, and Studio still caches the earlier failure.
- [[analyses/proving-sim-motion-not-a-frozen-stand]] — `/joint_states` span is ground truth; `action_applied`, `ros2 node list`, and a silent `docker exec` all lie.
- [[analyses/cloud-browser-needs-tunnel]] — cricket + SSH is cloud+browser; a public URL is blocked by unauthenticated dashboard (issue #44) and mixed-content `ws://` (needs `wss://` + auth, ADR first). HTTPS vs SSH is not a dashboard-video fix ([[analyses/mujoco-render-without-lag]]).
- [[analyses/no-uturn-rskill]] — no *named* U-turn weights; the in-tree walk ONNX already turns (`[0,0,ω]`, TypeSafe `turn_left`/`turn_right`). Demo Apply is forward-only. Closed-loop 180° is a heading loop, not a new Hub ckpt. `m3` v2 is the wider-yaw fallback (no ONNX).
- [[analyses/go2-hop-candidates]] — dashboard hop is gym spring_jump `rsl-rl-onnx-go2-spring-jump` (frame-major 470-D, joystick A; `air_ticks≈15`, max foot ≈0.34 m, `z_max≈0.53 m` on walk PD); cricket Load syncs that package + this-branch `rsl_rl_onnx.py`; mjlab ONNX and gym hop only crouch (`air_ticks=0`); scripted zero hop is fallback; Isaac `kp=20` sags calves.
- [[analyses/creating-acquire]] — how Acquire is created on this harness: OpenRAL runs skills; Acquire finds, fits, and proves them. On-stage trio: walk fit on bare Go2, walk adopt on Go2+Z1, hop reject on payload. `/simple` chat probes with `skill_id` and asks before remap. Jev retrieve ranker landed in the sibling (opt-in); not gate/remap/verify. Isaac Lab trains `rsl_rl_onnx`; hackathon verify stays MuJoCo.
- [[analyses/wrapping-third-party-weights]] — rSkill is an envelope around someone else's Hub ckpt (`weights_uri` may be `lerobot/`, `diasAiMaster/`, Xiaomi, NVIDIA); `model_family` picks the adapter; camera aliases / state layouts / 12→19 hold-pad remap IO without retraining; Acquire `adapt=remap` is tag retarget + verify, not a new policy. Payload Go2+Z1 walk is mjlab resume ([[analyses/go2-z1-payload-walk-finetune]]). Quantization is a separate packing step (NF4/int8 for 8 GB); Acquire beachhead stayed fp32/bf16.
- [[analyses/isaac-lab-with-openral]] — three Isaac paths: Lab-shaped rsl-rl ONNX on MuJoCo HAL (MVP; Hub walk is mjlab not Gym), existing Isaac Sim core sidecar, full Lab manager env as a follow-up. Gym and Lab are not both required.
- [[analyses/go2-proprio-freshness-cliff]] — Go2 locomotion has a **sharp** observation-age cliff (8/8 at 20 ms, 1/8 at 40 ms, 0/8 at 60 ms) — the measured reason the deploy scenes publish proprio at 200 Hz; and the live graph at median 5.1 ms age, which **excludes** staleness as the mid-gait tip. Also closes the twist-frame suspicion, and records that `publish_rate_hz_fast` is not in the policy path (the runner reads the aggregator in-process).
- [[analyses/mujoco-render-without-lag]] — show the dog as native MuJoCo without lags: stream `qpos` to a laptop kinematic viewer (`openral viz mujoco` + `GET /api/qpos` shipped); web tab is official `@mujoco/mujoco` WASM + Three.js on that same pose stream (no better pixel-stream player). Do not add EGL cameras or GLFW on cricket (40 ms proprio cliff). Foxglove 3D stays a URDF stand-in; dashboard `top` stays a proof still.
- [[analyses/go2-z1-arm-pose-decides-the-walk]] — arm **pose** decides the Go2+Z1 walk (ready 8/8, menagerie home 0/8 at honest mass), and **neither** CoM offset nor pitch inertia predicts which poses fall — mechanism open; drove the `ready` spawn (`GO2_Z1_SPAWN_JOINT_TARGETS`); centred pose not shipped (27 % slower tracking); one deterministic rollout per pose is an anecdote.
- [[analyses/go2-z1-payload-walk-finetune]] — `/simple` move Adapt is tag-fork + hold-pad, not variable retune. A live fall chats needs retraining. Payload-aware walk is mjlab resume of `model_500.pt` (not ONNX) with Z1 mass in the train env, then a new card; still 12-D legs. Do not drop `m3` Go2+Z1 walk into `rsl_rl_onnx`.
