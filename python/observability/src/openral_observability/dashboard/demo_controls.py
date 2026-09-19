"""Dashboard demo controls — stand / walk / stop / reload Go2 benches.

Operator write endpoints behind ``OPENRAL_DASHBOARD_WRITE_CONTROLS=1``. The
UI wizard is story-split: Bare Go2 (``story=bare``, ``resume=stand``)
auto-calibrates after reload and lands on **select skill + Apply**;
Go2+Z1 (``story=armed``, empty resume) **asks** for Recalibrate first.
Neither story auto-walks. Apply dispatches the selected skill through
``POST /api/skill/execute``; the rsl-rl walk skill still uses
:func:`walk_response` so the gentle forward jog stays the default.
**Stop** cancels the in-flight ``ExecuteRskill`` goal (no e-stop latch)
then snaps Hub stand so Apply can run again. Cancel-all is idempotent:
nothing in flight (rclpy ``ERROR_REJECTED``) still stands — it must not
paint OP_FAULT ``execute_rskill cancel failed``. **End Cricket** (see
``cricket_session``) tears the GPU session down; that is not Stop.
"""

from __future__ import annotations

import asyncio
import http
import json
import logging
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from fastapi.responses import JSONResponse

_logger = logging.getLogger("openral.dashboard")

#: Preset scene reloads. Paths are repo-relative; the restart script resolves
#: them against ``OPENRAL_REPO_ROOT`` (default ``/openral`` in the container).
#: ``resume=stand`` → the page auto-calls Recalibrate once ``/healthz`` is
#: back (no auto-walk). Empty resume → operator must Recalibrate.
DEMO_PRESETS: Final[dict[str, dict[str, str]]] = {
    "go2": {
        "scene": "scenes/deploy/go2_walk.yaml",
        "label": "Bare Go2",
        "robot_id": "go2",
        "resume": "stand",
        "story": "bare",
    },
    "go2_z1": {
        "scene": "scenes/deploy/go2_z1_walk.yaml",
        "label": "Go2 + Z1",
        "robot_id": "go2_z1",
        "resume": "",
        "story": "armed",
    },
}

#: Default locomotion skill for Apply when the walk skill is selected
#: (Acquire Hub id preferred on cricket; in-tree manifest name works when
#: the runner indexes it).
_WALK_SKILL_CANDIDATES: Final[tuple[str, ...]] = (
    "Acquire/rskill-rsl-rl-onnx-go2-velocity-flat",
    "OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32",
)

#: Recalibrate / Stand / Stop `ResetToPose`. Go2+Z1 parks the Z1 at
#: `GO2_Z1_ARM_READY` (0, 1.2, -1, -0.4, …) so Walk hold-snaps that pose.
_HOME_POSE_BY_ROBOT: Final[dict[str, tuple[float, ...]]] = {
    "go2": (
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
    ),
    "go2_z1": (
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
        0.0,
        1.2,
        -1.0,
        -0.4,
        0.0,
        0.0,
        0.0,
    ),
}


def walk_skill_ids() -> list[str]:
    """Ids the demo picker treats as the rsl-rl velocity walk skill."""
    return list(_WALK_SKILL_CANDIDATES)


def is_walk_skill_id(skill_id: str) -> bool:
    """True when ``skill_id`` is the Go2 rsl-rl velocity-flat walk skill.

    Hop and arm_ready share the Go2 family token in the id; they are never
    walk. Recalibrate ``preferWalk`` must not rewrite a hop pick.
    """
    sid = skill_id.strip()
    if not sid:
        return False
    compact = sid.lower().replace("-", "_")
    if "hop" in compact or "jump" in compact or "arm_ready" in compact:
        return False
    if sid in _WALK_SKILL_CANDIDATES:
        return True
    return "rsl_rl" in compact and "go2" in compact and "velocity" in compact


def walk_skill_dispatch_ids(skill_id: str = "") -> list[str]:
    """Ordered ExecuteRskill ids for a demo Walk Apply.

    The picker's selected id goes first when it is a walk skill so cricket's
    Hub name (``Acquire/…``) is not skipped in favour of a missing in-tree
    alias. Remaining :data:`_WALK_SKILL_CANDIDATES` follow as fallbacks.
    """
    out: list[str] = []
    selected = skill_id.strip()
    if selected and is_walk_skill_id(selected):
        out.append(selected)
    for candidate in _WALK_SKILL_CANDIDATES:
        if candidate not in out:
            out.append(candidate)
    return out


def demo_presets_payload() -> list[dict[str, str]]:
    """Wire shape for ``GET /api/config`` → demo button labels and resume policy."""
    return [
        {
            "id": key,
            "label": meta["label"],
            "robot_id": meta["robot_id"],
            "resume": meta.get("resume", ""),
            "story": meta.get("story", ""),
        }
        for key, meta in DEMO_PRESETS.items()
    ]


def robot_embodiment_tags(robot_id: str | None = None) -> list[str]:
    """Capability tags for the running twin — picker intersection, not name-equality.

    The Run-skill strip used to filter ``skill.embodiment_tags === robot.model``,
    which hid the 12-DoF Go2 walk skill on ``go2_z1`` even though that robot
    declares ``go2`` in ``capabilities.embodiment_tags`` (the loader's real gate).
    """
    rid = (robot_id if robot_id is not None else _robot_id_from_env()).strip()
    if not rid:
        return []
    path = _repo_root() / "robots" / rid / "robot.yaml"
    if not path.is_file():
        return [rid]
    try:
        from openral_core.exceptions import ROSConfigError
        from openral_core.schemas import RobotDescription
        from pydantic import ValidationError
    except ImportError:
        return [rid]
    try:
        desc = RobotDescription.from_yaml(str(path))
    except (OSError, ValidationError, ROSConfigError, TypeError) as exc:
        _logger.warning("demo.robot_tags_failed robot=%s err=%s", rid, exc)
        return [rid]
    return [str(t) for t in desc.capabilities.embodiment_tags]


def _repo_root() -> Path:
    env = os.environ.get("OPENRAL_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    # Dashboard imported from the editable workspace, or the cricket image.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "scenes" / "deploy" / "go2_walk.yaml").is_file():
            return parent
    return Path("/openral")


def _robot_id_from_env() -> str:
    raw = os.environ.get("OPENRAL_ROBOT_ID", "").strip()
    if raw:
        return raw
    from openral_observability.dashboard.cricket_session import cricket_live_robot_id

    return cricket_live_robot_id() or "go2_z1"


def _reset_service_for(robot_id: str) -> str:
    return f"/openral/{robot_id}/reset_to_pose"


#: Drain window after CancelGoal before Hub stand. The runner's cancel_cb
#: sleeps ≤100 ms without republishing; snapping too early can be overwritten
#: by idle-hold of the last walk chunk. Tests set this to ``0``.
_CANCEL_THEN_STAND_S: float = 0.35

#: Zero UUID + zero stamp on ``goal_info`` → cancel ALL goals (Jazzy
#: ``action_msgs/srv/CancelGoal``; older ROS 2 used a ``goals[]`` array).
_EXECUTE_RSKILL_CANCEL_SERVICE: Final[str] = "/openral/execute_rskill/_action/cancel_goal"
_EXECUTE_RSKILL_CANCEL_TYPE: Final[str] = "action_msgs/srv/CancelGoal"
_CANCEL_ALL_GOALS_YAML: Final[str] = (
    "{goal_info: {stamp: {sec: 0, nanosec: 0}, "
    "goal_id: {uuid: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}}}"
)

# action_msgs CancelGoal. Demo Stop is cancel-all (zero UUID). Idempotent:
# 0 ERROR_NONE — one or more goals entered CANCELING
# 1 ERROR_REJECTED — no goal entered CANCELING (cancel-all with nothing
#   cancelable, or cancel_cb REJECT / failed CANCELING transition)
# 2 ERROR_UNKNOWN_GOAL_ID — specific id missing
# 3 ERROR_GOAL_TERMINATED — already done
# Treating 1 as OK is load-bearing: rclpy cancel-all with no cancelable
# goal is REJECTED, not UNKNOWN_GOAL_ID. A strict {0,2,3} made Stop /
# Apply-while-running paint OP_FAULT ``execute_rskill cancel failed``.
_CANCEL_OK_CODES: Final[frozenset[int]] = frozenset({0, 1, 2, 3})
_CANCEL_OK_NAMES: Final[frozenset[str]] = frozenset(
    {
        "ERROR_NONE",
        "ERROR_REJECTED",
        "ERROR_UNKNOWN_GOAL_ID",
        "ERROR_GOAL_TERMINATED",
    }
)


def _trigger_success(text: str) -> bool:
    """True when a Trigger / ResetToPose response reports success."""
    compact = text.replace(" ", "")
    if "success=True" in compact:
        return True
    return "success=True" in text or "success: true" in text.lower()


def _cancel_goal_succeeded(text: str) -> bool:
    """True when CancelGoal returned a defined code (including idle REJECTED)."""
    match = re.search(r"return_code\s*[:=]\s*(-?\d+)", text)
    if match is not None:
        return int(match.group(1)) in _CANCEL_OK_CODES
    named = re.search(r"return_code\s*[:=]\s*(ERROR_[A-Z_]+)", text)
    if named is not None:
        return named.group(1) in _CANCEL_OK_NAMES
    compact = text.replace(" ", "")
    return "goals_canceling" in compact


async def _ros2_service_call(
    service: str,
    srv_type: str,
    args: str,
    *,
    succeeded: Callable[[str], bool] | None = None,
) -> tuple[bool, str]:
    """Shell ``ros2 service call``; return ``(ok, stdout_or_err)``.

    Laptop dashboards SSH the call into cricket. A down graph / SSH /
    credits failure is :data:`CRICKET_DISCONNECTED_MSG` (or
    ``start_error``), never a local PATH hint.
    """
    from openral_observability.dashboard.cricket_session import spawn_ros2

    proc, err = await spawn_ros2(
        ["service", "call", service, srv_type, args],
        stderr=asyncio.subprocess.STDOUT,
    )
    if err is not None or proc is None:
        from openral_observability.dashboard.cricket_session import (
            CRICKET_DISCONNECTED_MSG,
        )

        return False, err or CRICKET_DISCONNECTED_MSG
    try:
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        from openral_observability.dashboard.cricket_session import (
            CRICKET_DISCONNECTED_MSG,
            on_cricket_host,
        )

        if not on_cricket_host():
            return False, CRICKET_DISCONNECTED_MSG
        return False, f"timed out calling {service}"
    text = raw.decode(errors="replace")
    checker = succeeded if succeeded is not None else _trigger_success
    checked = checker(text)
    # Custom checkers (CancelGoal return_code) are authoritative — Jazzy
    # ``ros2 service call`` may exit 1 on ERROR_REJECTED even though the
    # action server answered.
    if succeeded is not None:
        return checked, text
    return proc.returncode == 0 and checked, text


async def _graph_down_response() -> JSONResponse | None:
    """503 once when cricket's graph is down — do not SSH ResetToPose."""
    from openral_observability.dashboard.cricket_session import (
        CRICKET_DISCONNECTED_MSG,
        cricket_graph_running,
    )

    running = await asyncio.to_thread(cricket_graph_running)
    if running:
        return None
    return JSONResponse(
        {"error": CRICKET_DISCONNECTED_MSG, "robot_id": _robot_id_from_env()},
        status_code=503,
    )


async def _reset_to_home_pose() -> tuple[str, JSONResponse | None]:
    """Snap Hub home. Returns ``(robot_id, error_or_None)``."""
    robot_id = _robot_id_from_env()
    down = await _graph_down_response()
    if down is not None:
        return robot_id, down
    pose = _HOME_POSE_BY_ROBOT.get(robot_id)
    if pose is None:
        return robot_id, JSONResponse(
            {"error": f"no Hub home pose for robot_id={robot_id!r}"},
            status_code=400,
        )
    pose_yaml = "[" + ", ".join(f"{v:.6g}" for v in pose) + "]"
    ok, out = await _ros2_service_call(
        _reset_service_for(robot_id),
        "openral_msgs/srv/ResetToPose",
        f"{{pose: {pose_yaml}}}",
    )
    if not ok:
        from openral_observability.dashboard.cricket_session import (
            is_cricket_unavailable_message,
        )

        _logger.warning("demo.reset_to_pose_failed robot=%s out=%s", robot_id, out[-500:])
        if is_cricket_unavailable_message(out):
            return robot_id, JSONResponse({"error": out, "robot_id": robot_id}, status_code=503)
        return robot_id, JSONResponse(
            {"error": "reset_to_pose failed", "detail": out[-800:], "robot_id": robot_id},
            status_code=502,
        )
    return robot_id, None


async def stand_response(*, origin: bool = True, estop: Any = None) -> JSONResponse:
    """Clear e-stop and snap the twin upright at Hub home (joints + free base).

    ``estop`` is the dashboard's persistent ``EstopPublisher``. Recalibrate /
    Stand must pass it so ``/openral/estop_cleared`` reaches the skill
    runner — a shell-out ``ros2 topic pub`` can clear the HAL while the
    runner stays latched and every Apply returns
    ``action server rejected the goal``.
    """
    del origin  # HAL always recentres today; kept for call-site clarity
    from openral_observability.dashboard.app import (
        _estop_reset_response,
        _write_controls_enabled,
    )

    if not _write_controls_enabled():
        return JSONResponse(
            {"error": "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1"},
            status_code=403,
        )

    down = await _graph_down_response()
    if down is not None:
        return down

    estop_resp = await _estop_reset_response(estop)
    # 200 or "no estop" still OK to proceed; only hard failures block.
    if estop_resp.status_code not in {200, 409}:
        body = json.loads(estop_resp.body.decode())
        if estop_resp.status_code >= int(http.HTTPStatus.INTERNAL_SERVER_ERROR):
            return estop_resp
        _logger.info("demo.stand_estop_nonfatal status=%s body=%s", estop_resp.status_code, body)

    robot_id, err = await _reset_to_home_pose()
    if err is not None:
        return err
    return JSONResponse(
        {"status": "ok", "accepted": True, "robot_id": robot_id, "action": "stand"},
        status_code=200,
    )


async def stop_response() -> JSONResponse:
    """Cancel the in-flight ExecuteRskill goal, then hold Hub stand.

    Does **not** latch or clear e-stop — that stays the E-STOP / Recalibrate
    pair. The rSkill runner's ``cancel_cb`` drains (≤100 ms) and idle-holds;
    we then snap Hub home so a walk does not freeze mid-gait. The runner
    stays ``active``, so Apply can dispatch the next goal immediately.
    Cancel-all with nothing cancelable is success (rclpy returns
    ``ERROR_REJECTED``). A malformed cancel reply is non-fatal: Hub stand
    still runs. Cricket-down is 503 before ResetToPose.
    """
    from openral_observability.dashboard.app import _write_controls_enabled

    if not _write_controls_enabled():
        return JSONResponse(
            {"error": "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1"},
            status_code=403,
        )

    down = await _graph_down_response()
    if down is not None:
        return down

    from openral_observability.dashboard.cricket_session import mark_skills_idle

    mark_skills_idle()
    cancel_ok, cancel_out = await _ros2_service_call(
        _EXECUTE_RSKILL_CANCEL_SERVICE,
        _EXECUTE_RSKILL_CANCEL_TYPE,
        _CANCEL_ALL_GOALS_YAML,
        succeeded=_cancel_goal_succeeded,
    )
    if not cancel_ok:
        from openral_observability.dashboard.cricket_session import (
            is_cricket_unavailable_message,
        )

        _logger.warning("demo.stop_cancel_nonfatal out=%s", cancel_out[-500:])
        if is_cricket_unavailable_message(cancel_out):
            return JSONResponse({"error": cancel_out}, status_code=503)

    if _CANCEL_THEN_STAND_S > 0.0:
        await asyncio.sleep(_CANCEL_THEN_STAND_S)

    robot_id, err = await _reset_to_home_pose()
    if err is not None:
        return err
    detail = (
        "skill canceled; holding Hub stand — Apply to run again"
        if cancel_ok
        else "cancel did not confirm; holding Hub stand — Apply to run again"
    )
    return JSONResponse(
        {
            "status": "ok",
            "accepted": True,
            "robot_id": robot_id,
            "action": "stop",
            "canceled": cancel_ok,
            "detail": detail,
        },
        status_code=200,
    )


async def walk_response(
    skill_id: str = "",
    velocity_commands: list[float] | None = None,
) -> JSONResponse:
    """Dispatch the Go2 velocity walk skill with a joystick command.

    Demo Apply without a chat propose uses ``[0.35, 0, 0]``. Chat can pass
    TypeSafe-shaped ``velocity_commands`` (forward / turn left / …).
    ``skill_id`` is the picker value when it is a walk skill; candidates
    are fallbacks.
    """
    from openral_observability.dashboard.app import (
        _skill_execute_response,
        _write_controls_enabled,
    )

    if not _write_controls_enabled():
        return JSONResponse(
            {"error": "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1"},
            status_code=403,
        )

    joystick = velocity_commands if velocity_commands is not None else [0.35, 0.0, 0.0]
    goal = json.dumps({"velocity_commands": joystick})
    last_err = "no skill id tried"
    for candidate in walk_skill_dispatch_ids(skill_id):
        result = await _skill_execute_response(
            candidate,
            "",
            "",
            goal,
            "demo",
        )
        if result.status_code < int(http.HTTPStatus.BAD_REQUEST):
            return result
        last_err = result.body.decode(errors="replace")
    hint = ""
    if "action server rejected the goal" in last_err:
        hint = (
            " — skill runner often still latched after End Cricket / e-stop; "
            "POST /api/estop_reset (or Recalibrate with EstopPublisher) so "
            "/openral/estop_cleared reaches the runner, then Apply again"
        )
    return JSONResponse(
        {"error": "walk dispatch failed", "detail": (last_err + hint)[-700:]},
        status_code=502,
    )


#: Character-class pgrep patterns. ``pkill -f 'openral deploy sim'`` matches
#: the killer's own argv (the pkill process *and* a ``bash -c`` body that
#: contains the same string), so the relaunch never starts.
_DEMO_RELOAD_KILL_RES: Final[tuple[str, ...]] = (
    "[o]penral deploy sim",
    "[r]os2 launch openral_rskill_ros",
    "[f]oxglove_bridge",
    "[o]penral dashboard",
    "[u]vicorn .*openral_observability",
)

#: On-disk launcher so process argv is ``bash /tmp/openral_demo_relaunch.sh``,
#: which does not match the kill patterns. The file *contents* may mention
#: ``deploy sim``; pgrep reads argv, not the script body.
_RELOAD_SCRIPT_PATH: Path = Path("/tmp/openral_demo_relaunch.sh")


def _build_demo_reload_script(
    *,
    preset_id: str,
    repo: Path,
    scene: Path,
    robot_id: str,
    domain: str,
    openral_bin: str,
) -> str:
    """Bash body for a detached Bare Go2 / Go2+Z1 cold reload."""
    repo_q = shlex.quote(str(repo))
    scene_q = shlex.quote(str(scene))
    robot_q = shlex.quote(robot_id)
    domain_q = shlex.quote(domain)
    bin_q = shlex.quote(openral_bin)
    preset_q = shlex.quote(preset_id)
    kill_res = " ".join(shlex.quote(p) for p in _DEMO_RELOAD_KILL_RES)
    return f"""#!/usr/bin/env bash
# Written by openral_observability.dashboard.demo_controls._spawn_scene_reload.
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
for re in {kill_res}; do
  _kill_re "$re" TERM
done
sleep 3
for re in {kill_res}; do
  _kill_re "$re" KILL
done
_port_busy() {{
  python3 -c 'import socket,sys
s=socket.socket(); s.settimeout(0.3)
r=s.connect_ex(("127.0.0.1", int(sys.argv[1]))); s.close()
raise SystemExit(0 if r==0 else 1)' "$1"
}}
for _ in $(seq 1 30); do
  _port_busy 4318 || break
  sleep 1
done
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
: > /tmp/openral_demo_deploy.log
echo "relaunching preset={preset_q} scene={scene_q} robot={robot_q}" >> /tmp/openral_demo_deploy.log
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
echo relaunched_pid=$! preset={preset_q} >> /tmp/openral_demo_deploy.log
"""


def _spawn_scene_reload(preset_id: str) -> tuple[bool, str]:
    """Detach a bash job that kills deploy sim and relaunches ``preset_id``.

    On a laptop this SSHes the same script into the cricket container —
    local ``Popen`` would start a Mac graph and leave the live twin unchanged.
    """
    from openral_observability.dashboard.cricket_session import on_cricket_host

    if not on_cricket_host():
        from openral_observability.dashboard.cricket_session import (
            spawn_remote_scene_reload,
        )

        return spawn_remote_scene_reload(preset_id)
    meta = DEMO_PRESETS.get(preset_id)
    if meta is None:
        return False, f"unknown preset {preset_id!r}"
    repo = _repo_root()
    scene = repo / meta["scene"]
    if not scene.is_file():
        return False, f"scene missing: {scene}"
    domain = os.environ.get("ROS_DOMAIN_ID", "77")
    venv_openral = repo / ".venv" / "bin" / "openral"
    openral_bin = str(venv_openral) if venv_openral.is_file() else "openral"
    # Detached: sleep so the HTTP response returns before we kill the parent
    # deploy (and this dashboard child). New deploy respawns the dashboard.
    # Kill dashboard/uvicorn too — otherwise a half-dead graph can leave the
    # previous twin (arm still visible) while healthz comes back.
    # Write a file and exec `bash $path` so argv cannot match the kill regexes.
    script = _build_demo_reload_script(
        preset_id=preset_id,
        repo=repo,
        scene=scene,
        robot_id=meta["robot_id"],
        domain=domain,
        openral_bin=openral_bin,
    )
    _RELOAD_SCRIPT_PATH.write_text(script, encoding="utf-8")
    _RELOAD_SCRIPT_PATH.chmod(0o700)
    subprocess.Popen(  # reason: file-backed demo reload; args are preset-validated paths
        ["bash", str(_RELOAD_SCRIPT_PATH)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    return True, meta["label"]


async def load_preset_response(body: dict[str, Any]) -> JSONResponse:
    """Schedule a cold reload of ``go2_walk`` or ``go2_z1_walk``."""
    from openral_observability.dashboard.app import _write_controls_enabled

    if not _write_controls_enabled():
        return JSONResponse(
            {"error": "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1"},
            status_code=403,
        )
    preset = str(body.get("preset", "")).strip()
    if preset not in DEMO_PRESETS:
        return JSONResponse(
            {"error": f"preset must be one of {sorted(DEMO_PRESETS)}"},
            status_code=400,
        )
    ok, detail = await asyncio.to_thread(_spawn_scene_reload, preset)
    if not ok:
        return JSONResponse({"error": detail}, status_code=400)
    _logger.warning("demo.load_preset scheduled preset=%s", preset)
    meta = DEMO_PRESETS[preset]
    label = meta["label"]
    auto_stand = meta.get("resume", "") == "stand"
    if auto_stand:
        next_beat = "auto_stand"
        hint = (
            f"{label} restarting (~30-90s). When the page returns it "
            "auto-calibrates — then select a skill and Apply."
        )
    else:
        next_beat = "recalibrate"
        hint = (
            f"{label} restarting (~30-90s). When the page returns: "
            "Recalibrate, then select a skill and Apply."
        )
    return JSONResponse(
        {
            "status": "accepted",
            "preset": preset,
            "label": detail,
            "robot_id": meta["robot_id"],
            "story": meta.get("story", ""),
            "resume": meta.get("resume", ""),
            "next": next_beat,
            "detail": hint,
        },
        status_code=202,
    )
