---
type: analysis
tags: [openral, dashboard, foxglove, cricket, security]
updated: 2026-09-19
---

# Cloud + browser needs a tunnel, not a public URL

Settled 2026-09-17 from the operator question "can we run this in the
cloud and show it in a browser?" Home:
[[concepts/deploy-sim-visualization]] ("Viewer on a laptop, graph on a
host"). Code: `openral_observability.dashboard.server._exposure_warning`.

## What already works

The graph is already in the cloud. Cricket (`abundant-turquoise-cricket`,
container `openral-jazzy-go2`) runs `openral deploy sim --dashboard
--foxglove`. Laptop **Start Cricket** does `brev start`, `docker start`,
and SSH forwards so a browser on the operator machine sees:

- dashboard `http://127.0.0.1:4318/` (or cricket's own UI at
  `http://127.0.0.1:14318/` when the laptop collector already owns `:4318`)
- Foxglove `ws://127.0.0.1:8765`, opened as
  `https://app.foxglove.dev/?ds=foxglove-websocket&ds.url=ws://localhost:8765`

No local GPU is required. The laptop is a viewer + tunnel, not the twin.

## What is not supported

A shareable `https://…` link. Two independent blockers, both deliberate:

1. **The dashboard has no authentication.** Binding anything other than
   loopback (`127.0.0.1` / `localhost` / `::1`) prints a warning: any host
   that can reach the port can `POST /api/prompt` and spoof OTLP.
   Combining a non-loopback bind with `OPENRAL_DASHBOARD_WRITE_CONTROLS=1`
   prints `CRITICAL` — unauthenticated skill-switch and param-tune reach
   actuation config. The code warns; it does not refuse. On a routable
   Brev address that is an unauthenticated stranger driving the robot.
2. **The Foxglove web client cannot speak remote `ws://`.**
   `app.foxglove.dev` is HTTPS. Browsers treat mixed-content websockets as
   blocked except `ws://localhost` (trustworthy origin — why the tunnel
   works). A genuinely remote bridge needs `wss://`, i.e. TLS in front of
   `foxglove_bridge`. The bridge itself binds `127.0.0.1:8765`
   ([[entities/openral-foxglove-bringup]]).

A public read-only view would be a TLS reverse proxy (Caddy /
Cloudflare / Tailscale) in front of `:4318` and `:8765` with real auth,
write-controls off for anyone but the operator. That is a new attack
surface on a robot control plane — record a decision in the private
management ADR log before implementing. Do not bind `0.0.0.0` as a
shortcut.

A public URL is **not** a video fix. Dashboard MJPEG still pays
`mjr_readPixels` + JPEG on cricket's HAL thread; HTTPS vs SSH only
changes the last hop
([[analyses/mujoco-render-without-lag]]). Stream `qpos`, render on the
client.

Related: [[entities/openral-foxglove-bringup]], [[entities/go2]].
