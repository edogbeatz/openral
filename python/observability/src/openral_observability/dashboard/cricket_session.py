"""Cricket GPU session — Start / End / idle auto-stop for the demo bar.

Two places the demo bar can run:

* **On cricket** (Brev ``abundant-turquoise-cricket``, docker
  ``openral-jazzy-go2``): Start brings the ``openral deploy sim`` graph up
  if it is down. Occupancy is local character-class ``pgrep``.
* **On a laptop**: Start is the operator path that used to be a no-op.
  It ``brev start``s a stopped box, ``docker start``s the container, opens
  SSH tunnels (Foxglove ``8765`` and cricket's dashboard on a documented
  local port so this process can keep ``4318``), and attaches the graph if
  it is not already running. If the graph is up, Start only ensures
  tunnels and reports already-running — it does not tear down.

End / idle-stop cancel ``ExecuteRskill`` (no e-stop latch), kill the graph
with the same character-class ``pgrep`` as demo reload (never a self-matching
``pkill -f``), then ``brev stop`` (laptop) or host halt (cricket) so GPU
billing stops. **Stop** on the wizard is the other button: freeze the robot,
keep the sim.

Idle default is 15 minutes (``OPENRAL_CRICKET_IDLE_S``). A running
``ExecuteRskill`` is not idle. Operator POSTs and ``POST /api/demo/cricket/touch``
reset the timer. Polling ``GET /api/demo/cricket`` does not.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from fastapi.responses import JSONResponse

from openral_observability.dashboard._fall import fallen_from_snapshot

_logger = logging.getLogger("openral.dashboard")

DEFAULT_CRICKET_IDLE_S: Final[float] = 900.0
DEFAULT_CRICKET_INSTANCE: Final[str] = "abundant-turquoise-cricket"
DEFAULT_CRICKET_CONTAINER: Final[str] = "openral-jazzy-go2"
DEFAULT_FOXGLOVE_PORT: Final[int] = 8765
DEFAULT_DASHBOARD_PORT: Final[int] = 4318
#: Local port for cricket's own dashboard when this process already owns 4318.
DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT: Final[int] = 14318
_MAX_TCP_PORT: Final[int] = 65535
#: Character-class pattern so the wrapper argv cannot match itself.
DEPLOY_SIM_PGREP: Final[str] = "[o]penral deploy sim"
_END_SCRIPT_PATH: Path = Path("/tmp/openral_cricket_end.sh")
_ATTACH_SCRIPT_REMOTE: Final[str] = "/tmp/openral_cricket_attach.sh"
_RELOAD_SCRIPT_REMOTE: Final[str] = "/tmp/openral_demo_relaunch.sh"
_SKILL_LIVE_AGE_S: Final[float] = 4.0
_SSH_STATUS_TIMEOUT_S: Final[float] = 12.0
_CONTAINER_REPO: Final[str] = "/openral"
#: Laptop → cricket copies so Apply hop is gym spring_jump, not a
#: Hub 401 / mjlab crouch / old adapter. Reload still required
#: (rsl_rl_onnx is already imported).
CRICKET_HOP_SYNC_RELPATHS: Final[tuple[str, ...]] = (
    "rskills/rsl-rl-onnx-go2-spring-jump",
    "python/sim/src/openral_sim/policies/rsl_rl_onnx.py",
)
#: Laptop Calibrate/Apply when SSH/graph/credits are down. Never a PATH hint.
CRICKET_DISCONNECTED_MSG: Final[str] = "cricket is disconnected"
_ROS2_PATH_HINT: Final[str] = "`ros2` not on PATH; source the workspace install first"

_WATCH: CricketIdleWatch | None = None
_WATCH_LOCK = threading.Lock()
#: Same age as the dashboard conn pill's dead threshold.
_TUNNELED_INGEST_LIVE_S: Final[float] = 60.0
_TUNNELED_STATE_TTL_S: Final[float] = 1.0
_LIVE_ROBOT_IDS: Final[frozenset[str]] = frozenset({"go2", "go2_z1"})
_tunneled_lock = threading.Lock()
_tunneled_cache_mono: float = 0.0
_tunneled_cache_payload: dict[str, Any] | None = None


def cricket_instance_name() -> str:
    """Brev workspace name, overridable with ``OPENRAL_CRICKET_INSTANCE``."""
    raw = os.environ.get("OPENRAL_CRICKET_INSTANCE", "").strip()
    return raw or DEFAULT_CRICKET_INSTANCE


def cricket_container_name() -> str:
    """Docker name on cricket, overridable with ``OPENRAL_CRICKET_CONTAINER``."""
    raw = os.environ.get("OPENRAL_CRICKET_CONTAINER", "").strip()
    return raw or DEFAULT_CRICKET_CONTAINER


def _openral_container_markers() -> bool:
    """True inside the graph container.

    Brev's hostname is ``brev-<id>`` (e.g. ``brev-d4dyyrsd1``), not
    ``*cricket*``. The attach/relaunch scripts set
    ``OPENRAL_CRICKET_ROLE=host``; this marker is the fallback when that
    env is missing on an already-running graph.
    """
    return Path("/.dockerenv").is_file() and Path("/openral").is_dir()


def on_cricket_host() -> bool:
    """True when this process is the cricket VM, not a laptop dashboard.

    ``OPENRAL_CRICKET_ROLE=host|laptop`` wins. Otherwise the hostname must
    contain ``cricket``, or we are inside the ``/openral`` graph container
    (Brev hostnames are ``brev-<id>``). A Mac local dashboard is laptop.
    """
    raw = os.environ.get("OPENRAL_CRICKET_ROLE", "").strip().lower()
    if raw in {"host", "cricket"}:
        return True
    if raw in {"laptop", "local", "client"}:
        return False
    if "cricket" in socket.gethostname().lower():
        return True
    return _openral_container_markers()


def can_start_from_cold() -> bool:
    """True when Start may ``brev start`` a stopped instance (laptop path)."""
    return not on_cricket_host()


def cricket_operator_role() -> str:
    """``host`` on cricket, ``laptop`` on a local dashboard."""
    return "host" if on_cricket_host() else "laptop"


def brev_ssh_config() -> Path:
    """Brev SSH config path (``BREV_SSH_CONFIG``, else ``~/.brev/ssh_config``)."""
    raw = os.environ.get("BREV_SSH_CONFIG", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".brev" / "ssh_config"


def foxglove_local_port() -> int:
    """Local Foxglove websocket port (tunnel target on a laptop)."""
    return _env_port("OPENRAL_CRICKET_FOXGLOVE_LOCAL_PORT", DEFAULT_FOXGLOVE_PORT)


def cricket_dashboard_local_port() -> int:
    """Local port tunneled to cricket's ``:4318`` when this process owns 4318."""
    return _env_port(
        "OPENRAL_CRICKET_DASHBOARD_LOCAL_PORT",
        DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT,
    )


def idle_timeout_s() -> float:
    """Idle auto-stop timeout. ``0`` disables. Default 900 s."""
    raw = os.environ.get("OPENRAL_CRICKET_IDLE_S", "").strip()
    if not raw:
        return DEFAULT_CRICKET_IDLE_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_CRICKET_IDLE_S
    if value < 0.0:
        return DEFAULT_CRICKET_IDLE_S
    return value


def halt_host_enabled() -> bool:
    """Whether End Cricket may halt the VM after the graph is down.

    Explicit ``OPENRAL_CRICKET_HALT_HOST=0/1`` wins. Default on only when the
    hostname looks like cricket, so a laptop dashboard never ``shutdown -h``.
    """
    raw = os.environ.get("OPENRAL_CRICKET_HALT_HOST", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return "cricket" in socket.gethostname().lower()


def start_from_cold_hint() -> str:
    """How Start behaves on this process (laptop cold-start vs on-host)."""
    instance = cricket_instance_name()
    container = cricket_container_name()
    if can_start_from_cold():
        fox = foxglove_local_port()
        dash = cricket_dashboard_local_port()
        return (
            f"Start Cricket from this laptop: `brev start {instance}` if stopped, "
            f"`docker start {container}`, SSH tunnels "
            f"(Foxglove ws://127.0.0.1:{fox}, cricket dashboard "
            f"http://127.0.0.1:{dash}/). Local :{DEFAULT_DASHBOARD_PORT} stays "
            "this page. If the graph is already up, Start only attaches."
        )
    return (
        "This dashboard is served from cricket. Start brings the deploy-sim "
        "graph up if it is down. A fully stopped box is started from a laptop "
        f"dashboard (Start Cricket) or `brev start {instance}`."
    )


def _env_port(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0 or value > _MAX_TCP_PORT:
        return default
    return value


class CricketIdleWatch:
    """Idle clock for auto-End. Skill-in-flight pauses the countdown."""

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] | None = None,
        poll_s: float = 1.0,
    ) -> None:
        """``monotonic`` is injectable so tests can drive the clock."""
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self.poll_s = poll_s
        self._lock = threading.Lock()
        self._last_touch = self._monotonic()
        self._in_flight = 0
        self._end_started = False
        self._start_started = False
        self._start_error: str | None = None

    def touch(self) -> None:
        """Record operator activity; restarts the idle countdown."""
        with self._lock:
            self._last_touch = self._monotonic()

    def mark_skill_started(self) -> None:
        """Pause idle: a dashboard-dispatched ExecuteRskill is in flight."""
        with self._lock:
            self._in_flight += 1
            self._last_touch = self._monotonic()

    def mark_skill_ended(self) -> None:
        """One dashboard-dispatched goal finished. Idle clock starts now."""
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._last_touch = self._monotonic()

    def mark_skills_idle(self) -> None:
        """Cancel-all / session teardown: nothing in flight."""
        with self._lock:
            self._in_flight = 0
            self._last_touch = self._monotonic()

    def skill_in_flight(self) -> bool:
        """True while at least one dashboard-dispatched goal is open."""
        with self._lock:
            return self._in_flight > 0

    def remaining_s(self, *, skill_live: bool = False) -> float | None:
        """Seconds until auto-End, ``timeout`` while paused, or ``None`` if off."""
        timeout = idle_timeout_s()
        if timeout <= 0.0:
            return None
        with self._lock:
            if skill_live or self._in_flight > 0:
                return timeout
            elapsed = self._monotonic() - self._last_touch
            return max(0.0, timeout - elapsed)

    def should_stop(self, *, skill_live: bool = False) -> bool:
        """True when idle has elapsed and no skill is running."""
        remaining = self.remaining_s(skill_live=skill_live)
        if remaining is None:
            return False
        if skill_live or self.skill_in_flight():
            return False
        return remaining <= 0.0

    def begin_end(self) -> bool:
        """One-shot guard so idle and the button cannot double-spawn End."""
        with self._lock:
            if self._end_started:
                return False
            self._end_started = True
            return True

    def reset_end_guard(self) -> None:
        """Allow another End after a failed spawn."""
        with self._lock:
            self._end_started = False

    def end_in_progress(self) -> bool:
        """True after End has been scheduled for this watch."""
        with self._lock:
            return self._end_started

    def begin_start(self) -> bool:
        """One-shot guard so a laptop cold-start is not double-spawned."""
        with self._lock:
            if self._start_started:
                return False
            self._start_started = True
            self._start_error = None
            return True

    def reset_start_guard(self) -> None:
        """Allow another Start after attach, failure, or graph-up."""
        with self._lock:
            self._start_started = False

    def start_in_progress(self) -> bool:
        """True after a background laptop Start has been scheduled."""
        with self._lock:
            return self._start_started

    def set_start_error(self, message: str | None) -> None:
        """Record a Brev/SSH/attach failure for ``GET /api/demo/cricket``."""
        with self._lock:
            self._start_error = message

    def start_error(self) -> str | None:
        """Last laptop-start failure, or ``None`` if the job has not failed."""
        with self._lock:
            return self._start_error


def bind_watch(watch: CricketIdleWatch | None) -> None:
    """Point the process-wide watch at ``watch`` (``create_app`` / tests)."""
    global _WATCH
    with _WATCH_LOCK:
        _WATCH = watch


def get_watch() -> CricketIdleWatch | None:
    """Process-wide watch bound by ``create_app``, or ``None`` in isolation."""
    with _WATCH_LOCK:
        return _WATCH


def touch_idle() -> None:
    """Reset the bound idle clock if one exists."""
    watch = get_watch()
    if watch is not None:
        watch.touch()


def mark_skill_started() -> None:
    """Pause idle on the bound watch for a newly accepted ExecuteRskill."""
    watch = get_watch()
    if watch is not None:
        watch.mark_skill_started()


def mark_skill_ended() -> None:
    """Resume idle on the bound watch when a dispatched goal finishes."""
    watch = get_watch()
    if watch is not None:
        watch.mark_skill_ended()


def mark_skills_idle() -> None:
    """Clear in-flight count on Stop / End Cricket."""
    watch = get_watch()
    if watch is not None:
        watch.mark_skills_idle()


def deploy_sim_pids() -> list[int]:
    """Pids whose argv match the deploy-sim occupancy pattern (not this wrapper)."""
    try:
        proc = subprocess.run(
            ["pgrep", "-f", DEPLOY_SIM_PGREP],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    pids: list[int] = []
    for line in proc.stdout.splitlines():
        token = line.strip()
        if not token.isdigit():
            continue
        pid = int(token)
        if pid == os.getpid():
            continue
        pids.append(pid)
    return pids


def graph_running() -> bool:
    """True when an ``openral deploy sim`` graph occupies this host."""
    return bool(deploy_sim_pids())


def cricket_graph_running() -> bool:
    """True when cricket's deploy-sim graph occupies ROS_DOMAIN_ID.

    On cricket this is local ``pgrep``. On a laptop it is ``docker exec``
    ``pgrep`` over SSH — never a local laptop process.
    """
    if on_cricket_host():
        return graph_running()
    return remote_graph_running()


def telemetry_skill_live(store: object | None, *, max_age_s: float = _SKILL_LIVE_AGE_S) -> bool:
    """True when the store's rSkill cards ticked within ``max_age_s``."""
    if store is None:
        return False
    snapshot_fn = getattr(store, "snapshot", None)
    if not callable(snapshot_fn):
        return False
    snapshot = snapshot_fn(include_camera_thumbs=False)
    cards = snapshot.get("cards") if isinstance(snapshot, dict) else None
    if not isinstance(cards, dict):
        return False
    now = time.time()
    for key in ("rskill_execute", "rskill_tick"):
        card = cards.get(key)
        if not isinstance(card, dict):
            continue
        ts = card.get("ts_unix")
        if isinstance(ts, (int, float)) and (now - float(ts)) <= max_age_s:
            return True
    return False


def cricket_viewer_payload() -> dict[str, Any]:
    """Foxglove + dashboard URLs the operator should open after Start."""
    fox_port = foxglove_local_port() if not on_cricket_host() else DEFAULT_FOXGLOVE_PORT
    if on_cricket_host():
        dash_url = f"http://127.0.0.1:{DEFAULT_DASHBOARD_PORT}/"
    else:
        dash_url = f"http://127.0.0.1:{cricket_dashboard_local_port()}/"
    fox = f"ws://127.0.0.1:{fox_port}"
    return {
        "foxglove_url": fox,
        "foxglove_open_url": (f"foxglove://open?ds=foxglove-websocket&ds.url={fox}"),
        "foxglove_web_url": (f"https://app.foxglove.dev/?ds=foxglove-websocket&ds.url={fox}"),
        "cricket_dashboard_url": dash_url,
        "control_dashboard_url": f"http://127.0.0.1:{DEFAULT_DASHBOARD_PORT}/",
    }


def cricket_status_payload(store: object | None = None) -> dict[str, Any]:
    """Wire shape for ``GET /api/demo/cricket``.

    A live graph clears a stale laptop ``start_error`` (``brev start``
    can print ready before sshd accepts).
    """
    watch = get_watch()
    timeout = idle_timeout_s()
    skill_live = False
    if watch is not None:
        skill_live = watch.skill_in_flight() or telemetry_skill_live(store)
    remaining: float | None
    if watch is None:
        remaining = timeout if timeout > 0.0 else None
    else:
        remaining = watch.remaining_s(skill_live=skill_live)
    running = cricket_graph_running()
    if watch is not None and running:
        watch.reset_start_guard()
        watch.set_start_error(None)
    payload: dict[str, Any] = {
        "instance": cricket_instance_name(),
        "container": cricket_container_name(),
        "role": cricket_operator_role(),
        "graph_running": running,
        "skill_running": skill_live,
        "idle_timeout_s": timeout,
        "idle_remaining_s": remaining,
        "idle_paused": bool(skill_live and timeout > 0.0),
        "idle_enabled": timeout > 0.0,
        "can_start_from_cold": can_start_from_cold(),
        "start_from_cold_hint": start_from_cold_hint(),
        "halt_host": halt_host_enabled(),
        "end_in_progress": bool(watch is not None and watch.end_in_progress()),
        "start_in_progress": bool(watch is not None and watch.start_in_progress()),
        "start_error": watch.start_error() if watch is not None else None,
    }
    payload.update(cricket_viewer_payload())
    return payload


def cricket_config_payload() -> dict[str, Any]:
    """Subset of :func:`cricket_status_payload` for the one-shot config fetch.

    Does not SSH for occupancy — that is ``GET /api/demo/cricket``.
    """
    timeout = idle_timeout_s()
    payload: dict[str, Any] = {
        "instance": cricket_instance_name(),
        "container": cricket_container_name(),
        "role": cricket_operator_role(),
        "idle_timeout_s": timeout,
        "idle_enabled": timeout > 0.0,
        "can_start_from_cold": can_start_from_cold(),
        "start_from_cold_hint": start_from_cold_hint(),
    }
    payload.update(cricket_viewer_payload())
    return payload


def _write_controls_or_403() -> JSONResponse | None:
    from openral_observability.dashboard.app import _write_controls_enabled

    if _write_controls_enabled():
        return None
    return JSONResponse(
        {"error": "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1"},
        status_code=403,
    )


async def cricket_status_response(store: object | None = None) -> JSONResponse:
    """``GET /api/demo/cricket`` — idle remaining, occupancy, cold-start hint.

    Occupancy SSH runs in a worker thread so this does not block the
    uvicorn event loop (a blocked loop makes ``POST /start`` a silent wait).
    """
    denied = _write_controls_or_403()
    if denied is not None:
        return denied
    payload = await asyncio.to_thread(cricket_status_payload, store)
    return JSONResponse(payload, status_code=200)


async def touch_cricket_response() -> JSONResponse:
    """``POST /api/demo/cricket/touch`` — dashboard interaction resets idle."""
    denied = _write_controls_or_403()
    if denied is not None:
        return denied
    touch_idle()
    return JSONResponse({"status": "ok", "touched": True}, status_code=200)


def _preset_for_running_robot() -> str:
    from openral_observability.dashboard.demo_controls import DEMO_PRESETS

    robot = os.environ.get("OPENRAL_ROBOT_ID", "").strip() or "go2"
    if robot in DEMO_PRESETS:
        return robot
    for key, meta in DEMO_PRESETS.items():
        if meta.get("robot_id") == robot:
            return key
    return "go2"


def parse_brev_ls(payload: object, *, instance: str) -> str | None:
    """Return the UPPER status for ``instance`` from ``brev ls --json``."""
    rows: object
    if isinstance(payload, Mapping):
        rows = payload.get("workspaces", payload.get("instances", []))
    else:
        rows = payload
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None
    needle = instance.lower()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or row.get("Name") or "")
        if name.lower() != needle:
            continue
        status = row.get("status") or row.get("Status") or row.get("state") or ""
        return str(status).upper()
    return None


def cricket_ssh_argv(*, extra: Sequence[str] = ()) -> list[str]:
    """Base ``ssh`` argv for cricket: Brev config, ``ControlMaster=no``."""
    argv: list[str] = [
        "ssh",
        "-T",
        "-F",
        str(brev_ssh_config()),
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "ServerAliveInterval=30",
    ]
    argv.extend(extra)
    argv.append(cricket_instance_name())
    return argv


def cricket_tunnel_argv(*, local_forwards: Sequence[tuple[int, int]]) -> list[str]:
    """``ssh -N -L`` argv for Foxglove / cricket dashboard tunnels."""
    extra: list[str] = [
        "-N",
        "-o",
        "ExitOnForwardFailure=yes",
    ]
    for local, remote in local_forwards:
        extra.extend(["-L", f"{local}:127.0.0.1:{remote}"])
    # ``-N`` is an ssh mode flag; put it after ``-T`` by rebuilding.
    argv = cricket_ssh_argv(extra=extra)
    # cricket_ssh_argv starts with ``ssh -T``; keep -T and insert nothing else.
    return argv


def _run(
    argv: Sequence[str],
    *,
    timeout_s: float,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
            input=input_text,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "timeout"
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=124,
            stdout=stdout or "",
            stderr=stderr or "timeout",
        )


def _ssh_run(
    remote_cmd: str,
    *,
    timeout_s: float = _SSH_STATUS_TIMEOUT_S,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [*cricket_ssh_argv(), "--", remote_cmd]
    return _run(argv, timeout_s=timeout_s, input_text=input_text)


def _ssh_ok() -> bool:
    """True when BatchMode SSH to cricket succeeds."""
    if not brev_ssh_config().is_file():
        return False
    proc = _ssh_run("true", timeout_s=8.0)
    return proc.returncode == 0


def _tcp_open(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket()
    sock.settimeout(0.3)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def cricket_tunneled_state() -> dict[str, Any] | None:
    """GET the tunneled cricket dashboard ``/api/state``, or ``None``.

    Laptop-only. Cached ``1`` s so occupancy, the conn pill, and camera
    stills do not stampede ``:14318``. Never fetched when this process
    *is* cricket (that would loop).
    """
    global _tunneled_cache_mono, _tunneled_cache_payload
    if on_cricket_host():
        return None
    now = time.monotonic()
    with _tunneled_lock:
        age = now - _tunneled_cache_mono
        if _tunneled_cache_mono > 0.0 and age < _TUNNELED_STATE_TTL_S:
            return _tunneled_cache_payload
    port = cricket_dashboard_local_port()
    payload: dict[str, Any] | None
    if not _tcp_open(port):
        payload = None
    else:
        url = f"http://127.0.0.1:{port}/api/state"
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                raw = resp.read()
            parsed: object = json.loads(raw)
            payload = parsed if isinstance(parsed, dict) else None
        except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError):
            payload = None
    with _tunneled_lock:
        _tunneled_cache_mono = time.monotonic()
        _tunneled_cache_payload = payload
    return payload


def cricket_tunneled_ingest_live(*, max_age_s: float = _TUNNELED_INGEST_LIVE_S) -> bool | None:
    """True/False from tunneled ``/api/state``, or ``None`` if the tunnel is dark."""
    state = cricket_tunneled_state()
    if state is None:
        return None
    last = state.get("last_ingest_ts")
    if not isinstance(last, (int, float)) or float(last) <= 0.0:
        return False
    now = state.get("now_unix")
    now_f = float(now) if isinstance(now, (int, float)) and float(now) > 0.0 else time.time()
    return (now_f - float(last)) < max_age_s


def cricket_live_robot_id() -> str:
    """``go2`` / ``go2_z1`` from tunneled cricket identity, else ``""``.

    Laptop ``GET /api/config`` has no ``OPENRAL_ROBOT_ID`` — the graph
    env lives on cricket. Without this, ``/simple`` boots with an empty
    UNIT while the twin is already loaded.
    """
    state = cricket_tunneled_state()
    ident = state.get("identity") if isinstance(state, dict) else None
    model = ident.get("openral.hal.robot.model") if isinstance(ident, dict) else None
    if isinstance(model, str) and model in _LIVE_ROBOT_IDS:
        return model
    return ""


def overlay_cricket_ingest(
    snap: dict[str, Any], *, include_camera_thumbs: bool = False
) -> dict[str, Any]:
    """Copy cricket ingest onto an empty laptop collector snapshot.

    The laptop ``:4318`` store never receives OTLP. Without this overlay the
    ``/simple`` conn pill stays ``waiting…`` while cricket cameras are live.
    ``include_camera_thumbs`` copies JPEG stills onto ``GET /api/state``
    only — SSE stays thumb-free. ``fallen`` copies cricket's bool, or
    computes it from cricket ``topics.robot_state.qpos``.
    """
    if snap.get("last_ingest_ts"):
        return snap
    state = cricket_tunneled_state()
    if state is None:
        return snap
    last = state.get("last_ingest_ts")
    if not isinstance(last, (int, float)) or float(last) <= 0.0:
        return snap
    out = dict(snap)
    out["last_ingest_ts"] = float(last)
    now = state.get("now_unix")
    if isinstance(now, (int, float)) and float(now) > 0.0:
        out["now_unix"] = float(now)
    ident = state.get("identity")
    if isinstance(ident, dict) and ident:
        out["identity"] = ident
    out["fallen"] = fallen_from_snapshot(state)
    if include_camera_thumbs:
        _merge_cricket_camera_thumbs(out, state)
    return out


def _merge_cricket_camera_thumbs(snap: dict[str, Any], state: dict[str, Any]) -> None:
    src_topics = state.get("topics")
    src_perc = src_topics.get("perception") if isinstance(src_topics, dict) else None
    src_cams = src_perc.get("cameras") if isinstance(src_perc, dict) else None
    if not isinstance(src_cams, dict):
        return
    dst_topics = snap.get("topics")
    if not isinstance(dst_topics, dict):
        dst_topics = {}
        snap["topics"] = dst_topics
    dst_perc = dst_topics.get("perception")
    if not isinstance(dst_perc, dict):
        dst_perc = {}
        dst_topics["perception"] = dst_perc
    dst_cams = dst_perc.get("cameras")
    if not isinstance(dst_cams, dict):
        dst_cams = {}
        dst_perc["cameras"] = dst_cams
    for name, entry in src_cams.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        thumb = entry.get("thumbnail_jpeg_b64")
        if not isinstance(thumb, str) or not thumb:
            continue
        dest = dst_cams.get(name)
        if not isinstance(dest, dict):
            dest = {}
            dst_cams[name] = dest
        if dest.get("thumbnail_jpeg_b64"):
            continue
        dest["thumbnail_jpeg_b64"] = thumb
        for key in ("role", "width", "height"):
            if key in entry and key not in dest:
                dest[key] = entry[key]


def cricket_tunneled_camera_thumb_b64(source: str) -> str | None:
    """Base64 JPEG for ``source`` from tunneled cricket ``/api/state``, or ``None``."""
    state = cricket_tunneled_state()
    topics = state.get("topics") if isinstance(state, dict) else None
    perc = topics.get("perception") if isinstance(topics, dict) else None
    cams = perc.get("cameras") if isinstance(perc, dict) else None
    entry = cams.get(source) if isinstance(cams, dict) else None
    b64 = entry.get("thumbnail_jpeg_b64") if isinstance(entry, dict) else None
    if not isinstance(b64, str) or not b64:
        return None
    return b64


def remote_graph_running() -> bool:
    """True when cricket's container has a live deploy-sim occupant.

    Prefer the tunneled cricket dashboard ingest (``:14318/api/state``)
    when that tunnel is up — it is the same proof the cameras use, and
    avoids a 12 s SSH pile-up. Fall back to ``docker exec pgrep`` over SSH.
    """
    ingest = cricket_tunneled_ingest_live()
    if ingest is not None:
        return ingest
    container = shlex.quote(cricket_container_name())
    remote = f"docker exec {container} pgrep -f {shlex.quote(DEPLOY_SIM_PGREP)}"
    proc = _ssh_run(remote, timeout_s=_SSH_STATUS_TIMEOUT_S)
    if proc.returncode not in {0, 1}:
        return False
    return any(line.strip().isdigit() for line in proc.stdout.splitlines())


def cricket_demo_block_reason() -> str | None:
    """Laptop-only reason a demo ``ros2`` call must not run locally.

    ``None`` on cricket (local ``ros2``) or on a laptop when the remote graph
    is up (a stale SSH-race ``start_error`` is cleared). Otherwise
    ``start_error`` (credits / SSH) or :data:`CRICKET_DISCONNECTED_MSG`.
    Never a PATH hint.
    """
    if on_cricket_host():
        return None
    if cricket_graph_running():
        watch = get_watch()
        if watch is not None:
            watch.set_start_error(None)
        return None
    watch = get_watch()
    start_err = watch.start_error() if watch is not None else None
    if start_err:
        return start_err
    return CRICKET_DISCONNECTED_MSG


def is_cricket_unavailable_message(text: str) -> bool:
    """True when ``text`` is a cricket-down operator reason (not a PATH hint)."""
    if text == CRICKET_DISCONNECTED_MSG:
        return True
    lower = text.lower()
    if "not on path" in lower or "source the workspace" in lower:
        return False
    return any(
        token in lower
        for token in (
            "credit",
            "insufficient",
            "quota",
            "billing",
            "can't reach cricket",
            "cricket is disconnected",
        )
    )


def remote_ros2_argv(args: Sequence[str]) -> list[str]:
    """``ssh`` + ``docker exec`` argv that runs ``ros2`` inside cricket."""
    domain = os.environ.get("ROS_DOMAIN_ID", "77").strip() or "77"
    ros2_cmd = " ".join(shlex.quote(part) for part in ("ros2", *args))
    inner = (
        "set +e; "
        "[ -f /opt/ros/jazzy/setup.bash ] && . /opt/ros/jazzy/setup.bash; "
        f"[ -f {_CONTAINER_REPO}/install/setup.bash ] && "
        f". {_CONTAINER_REPO}/install/setup.bash; "
        f"export ROS_DOMAIN_ID={shlex.quote(domain)}; "
        f"exec {ros2_cmd}"
    )
    remote = f"docker exec {shlex.quote(cricket_container_name())} bash -lc {shlex.quote(inner)}"
    return [*cricket_ssh_argv(), "--", remote]


def ros2_command_argv(args: Sequence[str]) -> tuple[list[str], str | None]:
    """Build ``ros2`` argv for this dashboard role.

    On cricket the binary is local. On a laptop the call is SSH +
    ``docker exec`` when the remote graph is up; otherwise the error is
    a disconnected / ``start_error`` string — never a local PATH hint.
    """
    if not on_cricket_host():
        blocked = cricket_demo_block_reason()
        if blocked is not None:
            return [], blocked
        return remote_ros2_argv(args), None
    ros2 = shutil.which("ros2")
    if ros2 is None:
        return [], _ROS2_PATH_HINT
    return [ros2, *args], None


async def spawn_ros2(
    args: Sequence[str],
    *,
    stdout: int | None = asyncio.subprocess.PIPE,
    stderr: int | None = asyncio.subprocess.PIPE,
) -> tuple[asyncio.subprocess.Process | None, str | None]:
    """Spawn ``ros2`` locally on cricket or remotely from a laptop."""
    argv, err = await asyncio.to_thread(ros2_command_argv, args)
    if err is not None:
        return None, err
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=stdout,
            stderr=stderr,
            env=os.environ.copy(),
        )
    except FileNotFoundError:
        if on_cricket_host():
            return None, _ROS2_PATH_HINT
        return None, CRICKET_DISCONNECTED_MSG
    return proc, None


def _brev_instance_status() -> str | None:
    proc = _run(["brev", "ls", "--json"], timeout_s=30.0)
    if proc.returncode != 0:
        return None
    try:
        payload: object = json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        return None
    return parse_brev_ls(payload, instance=cricket_instance_name())


def _brev_operator_error(stdout: str, stderr: str) -> str | None:
    """Return a credits/quota/billing snippet when Brev refused start."""
    blob = f"{stdout}\n{stderr}".strip()
    if not blob:
        return None
    lowered = blob.lower()
    if not any(token in lowered for token in ("credit", "insufficient", "quota", "billing")):
        return None
    return blob[-800:]


def _brev_start_if_needed() -> tuple[bool, str]:
    status = _brev_instance_status()
    if status is not None and "RUN" in status:
        return True, "already running"
    proc = _run(["brev", "start", cricket_instance_name()], timeout_s=300.0)
    credit_err = _brev_operator_error(proc.stdout, proc.stderr)
    if credit_err is not None:
        _logger.warning("cricket.brev_start credits err=%s", credit_err[-400:])
        return False, credit_err
    if proc.returncode != 0:
        # Already-running instances may error; SSH is the real gate.
        _logger.warning("cricket.brev_start out=%s err=%s", proc.stdout[-400:], proc.stderr[-400:])
    return True, proc.stdout.strip() or proc.stderr.strip() or "brev start"


def _wait_for_ssh(*, timeout_s: float = 300.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _ssh_ok():
            return True
        time.sleep(5.0)
    return False


def _docker_start() -> tuple[bool, str]:
    container = shlex.quote(cricket_container_name())
    proc = _ssh_run(f"docker start {container}", timeout_s=60.0)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "docker start failed").strip()
        return False, detail
    return True, (proc.stdout or cricket_container_name()).strip()


def _ensure_tunnels() -> dict[str, Any]:
    """Open Foxglove 8765 and cricket dashboard (documented local port)."""
    fox = foxglove_local_port()
    dash = cricket_dashboard_local_port()
    need_fox = not _tcp_open(fox)
    need_dash = not _tcp_open(dash)
    if not need_fox and not need_dash:
        return {
            "foxglove": fox,
            "dashboard": dash,
            "reused": True,
            "pid": None,
            "foxglove_open": True,
            "dashboard_open": True,
        }
    forwards: list[tuple[int, int]] = []
    if need_fox:
        forwards.append((fox, DEFAULT_FOXGLOVE_PORT))
    if need_dash:
        forwards.append((dash, DEFAULT_DASHBOARD_PORT))
    argv = cricket_tunnel_argv(local_forwards=forwards)
    proc = subprocess.Popen(  # reason: long-lived ssh -N tunnels; no user argv
        argv,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        fox_ok = (not need_fox) or _tcp_open(fox)
        dash_ok = (not need_dash) or _tcp_open(dash)
        if fox_ok and dash_ok:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    return {
        "foxglove": fox,
        "dashboard": dash,
        "reused": False,
        "pid": proc.pid,
        "foxglove_open": _tcp_open(fox),
        "dashboard_open": _tcp_open(dash),
    }


def _build_cricket_attach_script(
    *,
    scene: str,
    robot_id: str,
    domain: str,
    openral_bin: str,
) -> str:
    """Container script: start deploy-sim if occupancy is empty. Never kills."""
    scene_q = shlex.quote(scene)
    robot_q = shlex.quote(robot_id)
    domain_q = shlex.quote(domain)
    bin_q = shlex.quote(openral_bin)
    repo_q = shlex.quote(_CONTAINER_REPO)
    pgrep_q = shlex.quote(DEPLOY_SIM_PGREP)
    return f"""#!/usr/bin/env bash
# Written by openral_observability.dashboard.cricket_session._spawn_remote_graph.
# Argv is bash $path — occupancy pgrep cannot match this wrapper.
set +e
ulimit -c 0
if pgrep -f {pgrep_q} >/dev/null; then
  echo already_running >> /tmp/openral_demo_deploy.log
  exit 0
fi
if [ -f /opt/ros/jazzy/setup.bash ]; then
  . /opt/ros/jazzy/setup.bash
fi
if [ -f {repo_q}/install/setup.bash ]; then
  . {repo_q}/install/setup.bash
fi
cd {repo_q}
export OPENRAL_DASHBOARD_WRITE_CONTROLS=1
export OPENRAL_ROBOT_ID={robot_q}
export ROS_DOMAIN_ID={domain_q}
export OPENRAL_REPO_ROOT={repo_q}
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export OPENRAL_CRICKET_INSTANCE="${{OPENRAL_CRICKET_INSTANCE:-abundant-turquoise-cricket}}"
export OPENRAL_CRICKET_CONTAINER="${{OPENRAL_CRICKET_CONTAINER:-openral-jazzy-go2}}"
export OPENRAL_CRICKET_HALT_HOST="${{OPENRAL_CRICKET_HALT_HOST:-1}}"
export OPENRAL_CRICKET_ROLE=host
export OPENRAL_CRICKET_IDLE_S="${{OPENRAL_CRICKET_IDLE_S:-0}}"
: >> /tmp/openral_demo_deploy.log
echo "attach scene={scene_q} robot={robot_q}" >> /tmp/openral_demo_deploy.log
nohup setsid xvfb-run -a env MUJOCO_GL=egl PYOPENGL_PLATFORM=egl \\
  OPENRAL_DASHBOARD_WRITE_CONTROLS=1 OPENRAL_ROBOT_ID={robot_q} \\
  ROS_DOMAIN_ID={domain_q} OPENRAL_REPO_ROOT={repo_q} \\
  OPENRAL_CRICKET_INSTANCE="$OPENRAL_CRICKET_INSTANCE" \\
  OPENRAL_CRICKET_CONTAINER="$OPENRAL_CRICKET_CONTAINER" \\
  OPENRAL_CRICKET_HALT_HOST="$OPENRAL_CRICKET_HALT_HOST" \\
  OPENRAL_CRICKET_ROLE=host \\
  OPENRAL_CRICKET_IDLE_S="$OPENRAL_CRICKET_IDLE_S" \\
  {bin_q} deploy sim --config {scene_q} --dashboard --foxglove \\
  >> /tmp/openral_demo_deploy.log 2>&1 &
echo attach_pid=$! >> /tmp/openral_demo_deploy.log
"""


def _spawn_remote_graph() -> tuple[bool, str]:
    """Write the attach script inside the container and exec it. No kill."""
    from openral_observability.dashboard.demo_controls import DEMO_PRESETS

    preset = _preset_for_running_robot()
    meta = DEMO_PRESETS[preset]
    scene = f"{_CONTAINER_REPO}/{meta['scene']}"
    domain = os.environ.get("ROS_DOMAIN_ID", "77")
    openral_bin = f"{_CONTAINER_REPO}/.venv/bin/openral"
    script = _build_cricket_attach_script(
        scene=scene,
        robot_id=meta["robot_id"],
        domain=domain,
        openral_bin=openral_bin,
    )
    container = shlex.quote(cricket_container_name())
    path = _ATTACH_SCRIPT_REMOTE
    tee = _ssh_run(
        f"docker exec -i {container} tee {shlex.quote(path)}",
        timeout_s=20.0,
        input_text=script,
    )
    if tee.returncode != 0:
        detail = (tee.stderr or tee.stdout or "failed to write attach script").strip()
        return False, detail
    chmod = _ssh_run(
        f"docker exec {container} chmod 700 {shlex.quote(path)}",
        timeout_s=10.0,
    )
    if chmod.returncode != 0:
        detail = (chmod.stderr or chmod.stdout or "chmod attach script failed").strip()
        return False, detail
    run = _ssh_run(
        f"docker exec -d {container} bash {shlex.quote(path)}",
        timeout_s=20.0,
    )
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "attach exec failed").strip()
        return False, detail
    return True, meta["label"]


def laptop_repo_root() -> Path:
    """Checkout that holds the spring-jump rSkill (``OPENRAL_REPO_ROOT`` or walk)."""
    override = os.environ.get("OPENRAL_REPO_ROOT", "").strip()
    if override:
        return Path(override)
    marker = Path("rskills") / "rsl-rl-onnx-go2-spring-jump" / "rskill.yaml"
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    return Path.cwd()


def sync_cricket_scripted_hop(*, repo: Path | None = None) -> tuple[bool, str]:
    """Copy spring-jump rSkill + this-branch rsl_rl_onnx into cricket.

    Apply hop uses ``OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32``.
    Cricket's checkout often has only mjlab hop / an old adapter that
    cannot load ``constants`` / ``joystick_buttons`` / frame-major
    history. Existing dest values on disk are overwritten. Reload still
    required so the runner re-imports the adapter.
    """
    root = repo if repo is not None else laptop_repo_root()
    missing = [rel for rel in CRICKET_HOP_SYNC_RELPATHS if not (root / rel).exists()]
    if missing:
        return False, f"hop files missing locally: {missing}"
    packed = subprocess.run(
        ["tar", "czf", "-", *CRICKET_HOP_SYNC_RELPATHS],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if packed.returncode != 0:
        err = packed.stderr.decode(errors="replace").strip() or "tar failed"
        return False, err
    decode = "base64 -d | tar xzf - -C " + _CONTAINER_REPO
    container = shlex.quote(cricket_container_name())
    proc = _ssh_run(
        f"docker exec -i {container} bash -lc {shlex.quote(decode)}",
        timeout_s=60.0,
        input_text=base64.b64encode(packed.stdout).decode("ascii"),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "cricket hop sync failed").strip()
        return False, detail
    return True, "hop synced"


def spawn_remote_scene_reload(preset_id: str) -> tuple[bool, str]:
    """SSH cricket's demo reload script. Never runs ``deploy sim`` on the laptop.

    Same file + character-class ``pgrep`` as on-host load. Attach never
    kills; this path must, or UNIT cannot switch twins.
    """
    blocked = cricket_demo_block_reason()
    if blocked is None:
        synced, sync_detail = sync_cricket_scripted_hop()
        if not synced:
            blocked = sync_detail
    if blocked is not None:
        return False, blocked
    from openral_observability.dashboard.demo_controls import (
        DEMO_PRESETS,
        _build_demo_reload_script,
    )

    meta = DEMO_PRESETS.get(preset_id)
    if meta is None:
        return False, f"unknown preset {preset_id!r}"
    repo = Path(_CONTAINER_REPO)
    script = _build_demo_reload_script(
        preset_id=preset_id,
        repo=repo,
        scene=repo / meta["scene"],
        robot_id=meta["robot_id"],
        domain=os.environ.get("ROS_DOMAIN_ID", "77").strip() or "77",
        openral_bin=f"{_CONTAINER_REPO}/.venv/bin/openral",
    )
    container = shlex.quote(cricket_container_name())
    path = _RELOAD_SCRIPT_REMOTE
    tee = _ssh_run(
        f"docker exec -i {container} tee {shlex.quote(path)}",
        timeout_s=20.0,
        input_text=script,
    )
    if tee.returncode != 0:
        detail = (tee.stderr or tee.stdout or "failed to write reload script").strip()
        return False, detail
    chmod = _ssh_run(
        f"docker exec {container} chmod 700 {shlex.quote(path)}",
        timeout_s=10.0,
    )
    if chmod.returncode != 0:
        detail = (chmod.stderr or chmod.stdout or "chmod reload script failed").strip()
        return False, detail
    run = _ssh_run(
        f"docker exec -d {container} bash {shlex.quote(path)}",
        timeout_s=20.0,
    )
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "reload exec failed").strip()
        return False, detail
    return True, meta["label"]


def _laptop_attach_running_instance() -> dict[str, Any]:
    """Docker start + tunnels + attach-if-down. Does not ``brev start``."""
    docker_ok, docker_detail = _docker_start()
    if not docker_ok:
        return {"ok": False, "error": docker_detail, "already_running": False}
    tunnels = _ensure_tunnels()
    if remote_graph_running():
        return {
            "ok": True,
            "already_running": True,
            "spawned_graph": False,
            "tunnels": tunnels,
            "detail": (
                "cricket graph already up — Foxglove "
                f"{cricket_viewer_payload()['foxglove_url']}; cricket dashboard "
                f"{cricket_viewer_payload()['cricket_dashboard_url']}"
            ),
        }
    spawned, label = _spawn_remote_graph()
    if not spawned:
        return {"ok": False, "error": label, "already_running": False, "tunnels": tunnels}
    return {
        "ok": True,
        "already_running": False,
        "spawned_graph": True,
        "tunnels": tunnels,
        "preset": _preset_for_running_robot(),
        "detail": (
            f"Starting {label} on cricket (~30-90s). Foxglove "
            f"{cricket_viewer_payload()['foxglove_url']}; cricket dashboard "
            f"{cricket_viewer_payload()['cricket_dashboard_url']}"
        ),
    }


def _laptop_start_job() -> None:
    """Background: brev start a stopped box, then attach."""
    watch = get_watch()
    try:
        ok, detail = _brev_start_if_needed()
        if not ok:
            _logger.warning("cricket.laptop_start brev failed err=%s", detail)
            if watch is not None:
                watch.set_start_error(detail)
            return
        if not _wait_for_ssh():
            msg = "can't reach cricket — SSH never came up"
            _logger.warning("cricket.laptop_start ssh never came up")
            if watch is not None:
                watch.set_start_error(msg)
            return
        result = _laptop_attach_running_instance()
        if not result.get("ok"):
            err = str(result.get("error") or "laptop attach failed")
            _logger.warning("cricket.laptop_start attach failed err=%s", err)
            if watch is not None:
                watch.set_start_error(err)
            return
        if watch is not None:
            watch.set_start_error(None)
        _logger.warning(
            "cricket.laptop_start done already_running=%s spawned=%s",
            result.get("already_running"),
            result.get("spawned_graph"),
        )
    except (OSError, subprocess.SubprocessError, RuntimeError, json.JSONDecodeError):
        _logger.exception("cricket.laptop_start failed")
        if watch is not None:
            watch.set_start_error("laptop start failed")
    finally:
        if watch is not None:
            watch.reset_start_guard()


def _spawn_laptop_start() -> bool:
    """Detach the laptop cold-start job (brev start can take minutes)."""
    thread = threading.Thread(
        target=_laptop_start_job,
        name="openral-cricket-start",
        daemon=True,
    )
    thread.start()
    return True


def _build_cricket_end_script(
    *,
    instance: str,
    stop_cmd: str,
    halt_host: bool,
    kill_res: tuple[str, ...],
) -> str:
    """Bash body for detached session teardown. Argv must not match pgrep."""
    instance_q = shlex.quote(instance)
    kill_joined = " ".join(shlex.quote(p) for p in kill_res)
    halt_flag = "1" if halt_host else "0"
    stop_block = ""
    if stop_cmd.strip():
        stop_block = f"bash -lc {shlex.quote(stop_cmd.strip())}\n"
    else:
        stop_block = f"""if command -v brev >/dev/null 2>&1; then
  brev stop {instance_q} >> /tmp/openral_cricket_end.log 2>&1
elif [ "{halt_flag}" = "1" ]; then
  nsenter -t 1 -m -u -i -n shutdown -h now >> /tmp/openral_cricket_end.log 2>&1 \\
    || shutdown -h now >> /tmp/openral_cricket_end.log 2>&1 \\
    || true
fi
"""
    return f"""#!/usr/bin/env bash
# Written by openral_observability.dashboard.cricket_session._spawn_cricket_end.
set +e
ulimit -c 0
sleep 1
_kill_re() {{
  local re="$1"
  local sig="$2"
  local pid
  for pid in $(pgrep -f "$re" || true); do
    [ "$pid" -eq "$$" ] && continue
    kill -s "$sig" "$pid" 2>/dev/null || true
  done
}}
for re in {kill_joined}; do
  _kill_re "$re" TERM
done
sleep 3
for re in {kill_joined}; do
  _kill_re "$re" KILL
done
echo "graph_stopped instance={instance_q}" >> /tmp/openral_cricket_end.log
{stop_block}echo ended >> /tmp/openral_cricket_end.log
"""


def _build_cricket_laptop_end_script(
    *,
    instance: str,
    container: str,
    ssh_config: Path,
    stop_cmd: str,
    kill_res: tuple[str, ...],
) -> str:
    """Laptop End: SSH into cricket, character-class kill, then ``brev stop``."""
    instance_q = shlex.quote(instance)
    container_q = shlex.quote(container)
    ssh_cfg_q = shlex.quote(str(ssh_config))
    kill_joined = " ".join(shlex.quote(p) for p in kill_res)
    if stop_cmd.strip():
        stop_block = f"bash -lc {shlex.quote(stop_cmd.strip())}\n"
    else:
        stop_block = (
            f"if command -v brev >/dev/null 2>&1; then\n"
            f"  brev stop {instance_q} >> /tmp/openral_cricket_end.log 2>&1\n"
            f"fi\n"
        )
    return f"""#!/usr/bin/env bash
# Written by openral_observability.dashboard.cricket_session._spawn_cricket_end.
# Runs on the laptop. Remote kill is docker exec; argv is bash $path.
set +e
ulimit -c 0
sleep 1
ssh -T -F {ssh_cfg_q} -o ControlMaster=no -o ControlPath=none \\
  -o BatchMode=yes -o ConnectTimeout=20 {instance_q} -- \\
  docker exec -i {container_q} bash -s <<'REMOTE'
set +e
ulimit -c 0
_kill_re() {{
  local re="$1"
  local sig="$2"
  local pid
  for pid in $(pgrep -f "$re" || true); do
    [ "$pid" -eq "$$" ] && continue
    kill -s "$sig" "$pid" 2>/dev/null || true
  done
}}
for re in {kill_joined}; do
  _kill_re "$re" TERM
done
sleep 3
for re in {kill_joined}; do
  _kill_re "$re" KILL
done
echo graph_stopped >> /tmp/openral_cricket_end.log
REMOTE
echo "graph_stopped instance={instance_q}" >> /tmp/openral_cricket_end.log
{stop_block}for pid in $(pgrep -f "[s]sh -N .* {instance}" || true); do
  [ "$pid" -eq "$$" ] && continue
  kill "$pid" 2>/dev/null || true
done
echo ended >> /tmp/openral_cricket_end.log
"""


def _spawn_cricket_end() -> bool:
    """Detach the End Cricket killer. File-backed so argv cannot self-match."""
    from openral_observability.dashboard.demo_controls import _DEMO_RELOAD_KILL_RES

    if on_cricket_host():
        script = _build_cricket_end_script(
            instance=cricket_instance_name(),
            stop_cmd=os.environ.get("OPENRAL_CRICKET_STOP_CMD", ""),
            halt_host=halt_host_enabled(),
            kill_res=_DEMO_RELOAD_KILL_RES,
        )
    else:
        script = _build_cricket_laptop_end_script(
            instance=cricket_instance_name(),
            container=cricket_container_name(),
            ssh_config=brev_ssh_config(),
            stop_cmd=os.environ.get("OPENRAL_CRICKET_STOP_CMD", ""),
            kill_res=_DEMO_RELOAD_KILL_RES,
        )
    _END_SCRIPT_PATH.write_text(script, encoding="utf-8")
    _END_SCRIPT_PATH.chmod(0o700)
    subprocess.Popen(  # reason: file-backed cricket end; no user argv
        ["bash", str(_END_SCRIPT_PATH)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    return True


async def _cancel_skill_quiet() -> tuple[bool, str]:
    """Cancel ExecuteRskill without Hub-stand (the graph is going away)."""
    from openral_observability.dashboard.demo_controls import (
        _CANCEL_ALL_GOALS_YAML,
        _EXECUTE_RSKILL_CANCEL_SERVICE,
        _EXECUTE_RSKILL_CANCEL_TYPE,
        _cancel_goal_succeeded,
        _ros2_service_call,
    )

    return await _ros2_service_call(
        _EXECUTE_RSKILL_CANCEL_SERVICE,
        _EXECUTE_RSKILL_CANCEL_TYPE,
        _CANCEL_ALL_GOALS_YAML,
        succeeded=_cancel_goal_succeeded,
    )


def _start_already_running_body(*, detail: str) -> dict[str, Any]:
    body = {
        "status": "ok",
        "accepted": True,
        "action": "start",
        "already_running": True,
        "detail": detail,
        **cricket_status_payload(),
    }
    return body


async def start_cricket_response() -> JSONResponse:
    """Start or attach cricket. Laptop path may ``brev start``; never a no-op.

    Operator Start is recovery: it re-arms idle and clears an idle-End
    guard so a later click is not swallowed after auto-End.
    """
    denied = _write_controls_or_403()
    if denied is not None:
        return denied
    touch_idle()
    watch = get_watch()
    if watch is not None:
        watch.reset_end_guard()
    if on_cricket_host():
        return await _start_cricket_on_host()
    return await _start_cricket_from_laptop()


async def _start_cricket_on_host() -> JSONResponse:
    """Bring the deploy-sim graph up if this instance is already reachable."""
    running = await asyncio.to_thread(cricket_graph_running)
    if running:
        body = await asyncio.to_thread(
            _start_already_running_body,
            detail=(
                "cricket graph already up — Apply a skill, or End Cricket "
                "to shut the GPU session. Foxglove "
                f"{cricket_viewer_payload()['foxglove_url']}"
            ),
        )
        return JSONResponse(body, status_code=200)
    from openral_observability.dashboard.demo_controls import (
        DEMO_PRESETS,
        _spawn_scene_reload,
    )

    preset = _preset_for_running_robot()
    ok, detail = await asyncio.to_thread(_spawn_scene_reload, preset)
    if not ok:
        return JSONResponse({"error": detail, "action": "start"}, status_code=400)
    meta = DEMO_PRESETS[preset]
    _logger.warning("cricket.start scheduled preset=%s", preset)
    body: dict[str, Any] = {
        "status": "accepted",
        "accepted": True,
        "action": "start",
        "already_running": False,
        "role": "host",
        "preset": preset,
        "robot_id": meta["robot_id"],
        "can_start_from_cold": False,
        "detail": (
            f"Starting {meta['label']} on cricket (~30-90s). "
            "A fully stopped Brev box is started from a laptop Start Cricket."
        ),
        "start_from_cold_hint": start_from_cold_hint(),
    }
    body.update(cricket_viewer_payload())
    return JSONResponse(body, status_code=202)


async def _start_cricket_from_laptop() -> JSONResponse:
    """``brev start`` + docker + tunnels + attach. No-op success if graph up."""
    watch = get_watch()
    ssh_ok = await asyncio.to_thread(_ssh_ok)
    if not ssh_ok:
        if watch is not None and not watch.begin_start():
            prior = watch.start_error()
            viewers = cricket_viewer_payload()
            if prior:
                body = {
                    "error": prior,
                    "start_error": prior,
                    "action": "start",
                    "role": "laptop",
                    **viewers,
                }
                status = 400
            else:
                body = {
                    "status": "accepted",
                    "accepted": True,
                    "action": "start",
                    "already_running": False,
                    "role": "laptop",
                    "start_in_progress": True,
                    "start_error": None,
                    "detail": "Start Cricket already in progress",
                    **viewers,
                }
                status = 202
            return JSONResponse(body, status_code=status)
        ok = await asyncio.to_thread(_spawn_laptop_start)
        if not ok:
            if watch is not None:
                watch.reset_start_guard()
            return JSONResponse(
                {"error": "failed to schedule cricket start", "action": "start"},
                status_code=500,
            )
        instance = cricket_instance_name()
        _logger.warning("cricket.laptop_start scheduled instance=%s", instance)
        fox = cricket_viewer_payload()
        return JSONResponse(
            {
                "status": "accepted",
                "accepted": True,
                "action": "start",
                "already_running": False,
                "role": "laptop",
                "can_start_from_cold": True,
                "start_in_progress": True,
                "start_error": None,
                "detail": (
                    f"Starting `{instance}` (`brev start`, docker, tunnels). "
                    f"Foxglove {fox['foxglove_url']}; cricket dashboard "
                    f"{fox['cricket_dashboard_url']} (this page keeps "
                    f"{fox['control_dashboard_url']})."
                ),
                "start_from_cold_hint": start_from_cold_hint(),
                **fox,
            },
            status_code=202,
        )
    result = await asyncio.to_thread(_laptop_attach_running_instance)
    if not result.get("ok"):
        return JSONResponse(
            {
                "error": str(result.get("error") or "laptop start failed"),
                "action": "start",
                "role": "laptop",
                **cricket_viewer_payload(),
            },
            status_code=400,
        )
    viewers = cricket_viewer_payload()
    if result.get("already_running"):
        if watch is not None:
            watch.reset_start_guard()
        body = await asyncio.to_thread(
            _start_already_running_body,
            detail=str(result.get("detail") or "cricket graph already up"),
        )
        return JSONResponse(body, status_code=200)
    preset = str(result.get("preset") or _preset_for_running_robot())
    _logger.warning("cricket.laptop_attach scheduled preset=%s", preset)
    return JSONResponse(
        {
            "status": "accepted",
            "accepted": True,
            "action": "start",
            "already_running": False,
            "role": "laptop",
            "preset": preset,
            "can_start_from_cold": True,
            "detail": str(result.get("detail") or "starting cricket graph"),
            "tunnels": result.get("tunnels"),
            **viewers,
        },
        status_code=202,
    )


async def end_cricket_response(*, origin: str = "operator") -> JSONResponse:
    """Cancel the skill, stop the graph, then stop the Brev instance."""
    denied = _write_controls_or_403()
    if denied is not None:
        return denied
    watch = get_watch()
    if watch is not None and not watch.begin_end():
        return JSONResponse(
            {
                "status": "accepted",
                "accepted": True,
                "action": "end",
                "detail": "End Cricket already in progress",
            },
            status_code=202,
        )
    touch_idle()
    mark_skills_idle()
    cancel_ok = True
    if on_cricket_host():
        cancel_ok, cancel_out = await _cancel_skill_quiet()
        if not cancel_ok:
            _logger.warning("cricket.end_cancel_nonfatal out=%s", cancel_out[-500:])
    ok = await asyncio.to_thread(_spawn_cricket_end)
    if not ok:
        if watch is not None:
            watch.reset_end_guard()
        return JSONResponse({"error": "failed to schedule cricket end"}, status_code=500)
    _logger.warning(
        "cricket.end scheduled origin=%s role=%s halt_host=%s",
        origin,
        cricket_operator_role(),
        halt_host_enabled(),
    )
    halt = halt_host_enabled()
    if on_cricket_host():
        if halt:
            host_detail = (
                f"then `brev stop {cricket_instance_name()}` or host halt so GPU spend stops"
            )
        else:
            host_detail = (
                f"graph stopping; host halt is off — run `brev stop {cricket_instance_name()}` "
                "from a laptop so billing stops"
            )
    else:
        host_detail = (
            f"graph stopping on cricket, then `brev stop {cricket_instance_name()}` "
            "from this laptop so billing stops"
        )
    return JSONResponse(
        {
            "status": "accepted",
            "accepted": True,
            "action": "end",
            "canceled": cancel_ok,
            "origin": origin,
            "halt_host": halt,
            "role": cricket_operator_role(),
            "detail": (
                "Ending cricket — skill canceled (no E-STOP latch), graph stopping, " + host_detail
            ),
        },
        status_code=202,
    )


async def cricket_idle_loop(
    store: object | None,
    *,
    wait: Callable[[float], Awaitable[None]] | None = None,
) -> None:
    """Background loop: End Cricket when the idle clock hits zero."""
    sleeper = wait if wait is not None else asyncio.sleep
    while True:
        timeout = idle_timeout_s()
        if timeout <= 0.0:
            await sleeper(1.0)
            continue
        watch = get_watch()
        if watch is None:
            await sleeper(1.0)
            continue
        await sleeper(watch.poll_s)
        skill_live = watch.skill_in_flight() or telemetry_skill_live(store)
        if watch.should_stop(skill_live=skill_live):
            _logger.warning("cricket.idle_stop timeout_s=%s", timeout)
            await end_cricket_response(origin="idle")
            return
