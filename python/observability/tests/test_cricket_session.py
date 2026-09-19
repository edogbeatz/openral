"""Cricket idle clock, occupancy pattern, and End script (process-boundary fakes)."""

from __future__ import annotations

import asyncio
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
from openral_observability.dashboard import cricket_session as cs
from openral_observability.dashboard.app import create_app
from openral_observability.dashboard.cricket_session import (
    DEFAULT_CRICKET_IDLE_S,
    CricketIdleWatch,
    _build_cricket_end_script,
    bind_watch,
    cricket_idle_loop,
    halt_host_enabled,
    idle_timeout_s,
    telemetry_skill_live,
)
from openral_observability.dashboard.demo_controls import _DEMO_RELOAD_KILL_RES
from openral_observability.dashboard.store import TelemetryStore


def test_idle_timeout_default_is_15_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_CRICKET_IDLE_S", raising=False)
    assert idle_timeout_s() == DEFAULT_CRICKET_IDLE_S
    assert DEFAULT_CRICKET_IDLE_S == 900.0


def test_idle_timeout_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_IDLE_S", "0")
    assert idle_timeout_s() == 0.0


def test_idle_watch_skill_pauses_countdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_IDLE_S", "30")
    clock = {"t": 0.0}
    watch = CricketIdleWatch(monotonic=lambda: clock["t"])
    assert watch.remaining_s() == 30.0
    clock["t"] = 10.0
    assert watch.remaining_s() == 20.0
    watch.mark_skill_started()
    clock["t"] = 100.0
    assert watch.should_stop() is False
    assert watch.remaining_s(skill_live=False) == 30.0
    watch.mark_skill_ended()
    assert watch.remaining_s() == 30.0
    clock["t"] = 130.0
    assert watch.should_stop() is True


def test_idle_watch_operator_touch_resets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_IDLE_S", "15")
    clock = {"t": 0.0}
    watch = CricketIdleWatch(monotonic=lambda: clock["t"])
    clock["t"] = 10.0
    watch.touch()
    clock["t"] = 20.0
    assert watch.remaining_s() == 5.0
    assert watch.should_stop() is False


def test_end_script_does_not_pkill_self() -> None:
    script = _build_cricket_end_script(
        instance="abundant-turquoise-cricket",
        stop_cmd="",
        halt_host=True,
        kill_res=_DEMO_RELOAD_KILL_RES,
    )
    assert "pkill" not in script
    assert "[o]penral deploy sim" in script
    assert "bash -c" not in script
    assert "brev stop" in script
    assert "shutdown -h now" in script
    assert "ulimit -c 0" in script


def test_end_script_custom_stop_cmd_skips_brev() -> None:
    script = _build_cricket_end_script(
        instance="abundant-turquoise-cricket",
        stop_cmd="echo stopped-by-test",
        halt_host=True,
        kill_res=_DEMO_RELOAD_KILL_RES,
    )
    assert "echo stopped-by-test" in script
    assert "brev stop" not in script
    assert "shutdown -h now" not in script


def test_halt_host_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_HALT_HOST", "0")
    assert halt_host_enabled() is False
    monkeypatch.setenv("OPENRAL_CRICKET_HALT_HOST", "1")
    assert halt_host_enabled() is True


def test_telemetry_skill_live_uses_recent_rskill_card() -> None:
    class _Live:
        def snapshot(self, include_camera_thumbs: bool = True) -> dict[str, object]:
            del include_camera_thumbs
            return {"cards": {"rskill_execute": {"ts_unix": time.time()}}}

    class _Stale:
        def snapshot(self, include_camera_thumbs: bool = True) -> dict[str, object]:
            del include_camera_thumbs
            return {"cards": {"rskill_execute": {"ts_unix": 1.0}}}

    assert telemetry_skill_live(_Live()) is True
    assert telemetry_skill_live(_Stale(), max_age_s=4.0) is False
    assert telemetry_skill_live(None) is False


def test_parse_brev_ls_reads_workspaces_status() -> None:
    from openral_observability.dashboard.cricket_session import parse_brev_ls

    payload = {
        "workspaces": [
            {"name": "abundant-turquoise-cricket", "status": "RUNNING"},
            {"name": "other", "status": "STOPPED"},
        ]
    }
    assert parse_brev_ls(payload, instance="abundant-turquoise-cricket") == "RUNNING"
    assert parse_brev_ls(payload, instance="missing") is None


def test_attach_script_never_kills_and_sets_write_controls() -> None:
    from openral_observability.dashboard.cricket_session import (
        DEPLOY_SIM_PGREP,
        _build_cricket_attach_script,
    )

    script = _build_cricket_attach_script(
        scene="/openral/scenes/deploy/go2_z1_walk.yaml",
        robot_id="go2_z1",
        domain="77",
        openral_bin="/openral/.venv/bin/openral",
    )
    assert "pkill" not in script
    assert "_kill_re" not in script
    assert DEPLOY_SIM_PGREP in script
    assert "OPENRAL_DASHBOARD_WRITE_CONTROLS=1" in script
    assert "OPENRAL_CRICKET_ROLE=host" in script
    assert "OPENRAL_CRICKET_IDLE_S" in script
    assert "deploy sim --config" in script
    assert "--dashboard --foxglove" in script
    assert "ROS_DOMAIN_ID=77" in script


def test_tunnel_argv_control_master_no_and_both_ports() -> None:
    from openral_observability.dashboard.cricket_session import cricket_tunnel_argv

    argv = cricket_tunnel_argv(local_forwards=[(8765, 8765), (14318, 4318)])
    assert argv[0] == "ssh"
    assert "-N" in argv
    joined = " ".join(argv)
    assert "ControlMaster=no" in joined
    assert "8765:127.0.0.1:8765" in joined
    assert "14318:127.0.0.1:4318" in joined
    assert "abundant-turquoise-cricket" in argv


def test_laptop_end_script_sshes_then_brev_stop() -> None:
    from openral_observability.dashboard.cricket_session import (
        _build_cricket_laptop_end_script,
    )
    from openral_observability.dashboard.demo_controls import _DEMO_RELOAD_KILL_RES

    script = _build_cricket_laptop_end_script(
        instance="abundant-turquoise-cricket",
        container="openral-jazzy-go2",
        ssh_config=Path("/tmp/fake_brev_ssh_config"),
        stop_cmd="",
        kill_res=_DEMO_RELOAD_KILL_RES,
    )
    assert "pkill" not in script
    assert "[o]penral deploy sim" in script
    assert "docker exec -i" in script
    assert "ControlMaster=no" in script
    assert "brev stop abundant-turquoise-cricket" in script
    assert "shutdown -h now" not in script


def test_on_cricket_host_brev_hostname_uses_container_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENRAL_CRICKET_ROLE", raising=False)
    monkeypatch.setattr(cs.socket, "gethostname", lambda: "brev-d4dyyrsd1")
    monkeypatch.setattr(cs, "_openral_container_markers", lambda: True)
    assert cs.on_cricket_host() is True
    monkeypatch.setattr(cs, "_openral_container_markers", lambda: False)
    assert cs.on_cricket_host() is False


def test_remote_graph_running_prefers_tunneled_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_tunneled_ingest_live", lambda: True)

    def _no_ssh(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ssh occupancy should not run")

    monkeypatch.setattr(cs, "_ssh_run", _no_ssh)
    assert cs.remote_graph_running() is True


def test_overlay_cricket_ingest_copies_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        cs,
        "cricket_tunneled_state",
        lambda: {
            "last_ingest_ts": 10.0,
            "now_unix": 11.0,
            "identity": {"openral.hal.adapter": "go2mujocohal"},
            "topics": {
                "perception": {"cameras": {"top": {"thumbnail_jpeg_b64": "abc", "role": "side"}}}
            },
        },
    )
    out = cs.overlay_cricket_ingest({"last_ingest_ts": 0.0, "now_unix": 1.0, "identity": {}})
    assert out["last_ingest_ts"] == 10.0
    assert out["now_unix"] == 11.0
    ident = out["identity"]
    assert isinstance(ident, dict)
    assert ident["openral.hal.adapter"] == "go2mujocohal"
    topics = out.get("topics")
    assert topics is None or "perception" not in topics
    with_thumbs = cs.overlay_cricket_ingest(
        {"last_ingest_ts": 0.0, "now_unix": 1.0, "identity": {}, "topics": {}},
        include_camera_thumbs=True,
    )
    cams = with_thumbs["topics"]["perception"]["cameras"]
    assert cams["top"]["thumbnail_jpeg_b64"] == "abc"
    assert cams["top"]["role"] == "side"


def test_cricket_live_robot_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        cs,
        "cricket_tunneled_state",
        lambda: {"identity": {"openral.hal.robot.model": "go2_z1"}},
    )
    assert cs.cricket_live_robot_id() == "go2_z1"
    monkeypatch.setattr(cs, "cricket_tunneled_state", lambda: {"identity": {}})
    assert cs.cricket_live_robot_id() == ""


def test_laptop_spawn_scene_reload_sshes_cricket(monkeypatch: pytest.MonkeyPatch) -> None:
    from openral_observability.dashboard import demo_controls

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    called: list[str] = []
    monkeypatch.setattr(
        cs,
        "spawn_remote_scene_reload",
        lambda preset: called.append(preset) or (True, "Bare Go2"),
    )
    ok, label = demo_controls._spawn_scene_reload("go2")
    assert ok is True
    assert label == "Bare Go2"
    assert called == ["go2"]


def test_spawn_remote_scene_reload_tees_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_demo_block_reason", lambda: None)
    runs: list[tuple[str, str | None]] = []

    def _ssh(
        cmd: str, timeout_s: float = 0.0, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        del timeout_s
        runs.append((cmd, input_text))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cs, "_ssh_run", _ssh)
    ok, label = cs.spawn_remote_scene_reload("go2")
    assert ok is True
    assert label == "Bare Go2"
    joined = " ".join(cmd for cmd, _ in runs)
    assert "base64 -d" in joined
    assert "rskill-zero-go2-hop-fp32" not in joined  # tar payload, not argv
    assert "tee" in joined
    assert "openral_demo_relaunch.sh" in joined
    assert "chmod 700" in joined
    assert "bash" in joined
    body = next(text for _, text in runs if text and "relaunching" in text)
    assert "pkill" not in body
    assert "go2_walk.yaml" in body
    assert "OPENRAL_CRICKET_ROLE=host" in body
    assert "[o]penral deploy sim" in body


def test_sync_cricket_scripted_hop_reports_missing(tmp_path: Path) -> None:
    ok, detail = cs.sync_cricket_scripted_hop(repo=tmp_path)
    assert ok is False
    assert "missing locally" in detail


def test_cricket_tunneled_camera_thumb_b64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        cs,
        "cricket_tunneled_state",
        lambda: {
            "topics": {"perception": {"cameras": {"front": {"thumbnail_jpeg_b64": "abc123"}}}}
        },
    )
    assert cs.cricket_tunneled_camera_thumb_b64("front") == "abc123"
    assert cs.cricket_tunneled_camera_thumb_b64("top") is None


def test_can_start_from_cold_on_laptop(monkeypatch: pytest.MonkeyPatch) -> None:
    from openral_observability.dashboard import cricket_session as cs

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    assert cs.on_cricket_host() is False
    assert cs.can_start_from_cold() is True
    hint = cs.start_from_cold_hint()
    assert "brev start" in hint
    assert "14318" in hint
    assert "8765" in hint


def test_spawn_end_execs_script_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openral_observability.dashboard import cricket_session

    script_path = tmp_path / "openral_cricket_end.sh"
    popped: list[list[str]] = []
    monkeypatch.setattr(cricket_session, "_END_SCRIPT_PATH", script_path)
    monkeypatch.setenv("OPENRAL_CRICKET_HALT_HOST", "0")
    monkeypatch.setenv("OPENRAL_CRICKET_STOP_CMD", "echo halt-test")

    def _fake_popen(argv: list[str], **kwargs: object) -> object:
        del kwargs
        popped.append(list(argv))

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(cricket_session.subprocess, "Popen", _fake_popen)
    assert cricket_session._spawn_cricket_end() is True
    assert popped == [["bash", str(script_path)]]
    body = script_path.read_text(encoding="utf-8")
    assert "pkill" not in body
    assert "[o]penral deploy sim" in body
    assert "echo halt-test" in body


@pytest.mark.asyncio
async def test_idle_loop_ends_cricket_when_clock_elapses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_IDLE_S", "10")
    monkeypatch.setenv("OPENRAL_CRICKET_HALT_HOST", "0")
    clock = {"t": 0.0}
    watch = CricketIdleWatch(monotonic=lambda: clock["t"], poll_s=1.0)
    bind_watch(watch)
    spawned: list[str] = []

    async def _fake_cancel() -> tuple[bool, str]:
        return True, "return_code: 0"

    def _fake_spawn() -> bool:
        spawned.append("end")
        return True

    async def _fake_wait(dt: float) -> None:
        clock["t"] += max(dt, 10.0)

    monkeypatch.setattr(
        "openral_observability.dashboard.cricket_session._cancel_skill_quiet",
        _fake_cancel,
    )
    monkeypatch.setattr(
        "openral_observability.dashboard.cricket_session._spawn_cricket_end",
        _fake_spawn,
    )
    await cricket_idle_loop(None, wait=_fake_wait)
    assert spawned == ["end"]
    bind_watch(None)


@pytest.mark.asyncio
async def test_laptop_start_attaches_when_remote_graph_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local Start must tunnel + report running — never respawn a live graph."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: True)
    monkeypatch.setattr(cs, "_docker_start", lambda: (True, "openral-jazzy-go2"))
    monkeypatch.setattr(cs, "remote_graph_running", lambda: True)
    monkeypatch.setattr(
        cs,
        "_ensure_tunnels",
        lambda: {
            "foxglove": 8765,
            "dashboard": 14318,
            "reused": True,
            "pid": None,
            "foxglove_open": True,
            "dashboard_open": True,
        },
    )
    spawned: list[str] = []
    monkeypatch.setattr(cs, "_spawn_remote_graph", lambda: spawned.append("graph") or (True, "x"))
    monkeypatch.setattr(cs, "_spawn_laptop_start", lambda: spawned.append("bg") or True)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_running"] is True
    assert body["role"] == "laptop"
    assert body["foxglove_url"] == "ws://127.0.0.1:8765"
    assert body["cricket_dashboard_url"] == "http://127.0.0.1:14318/"
    assert "foxglove://" in body["foxglove_open_url"]
    assert spawned == []


@pytest.mark.asyncio
async def test_laptop_start_spawns_remote_graph_when_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2_z1")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: True)
    monkeypatch.setattr(cs, "_docker_start", lambda: (True, "openral-jazzy-go2"))
    monkeypatch.setattr(cs, "remote_graph_running", lambda: False)
    monkeypatch.setattr(
        cs,
        "_ensure_tunnels",
        lambda: {
            "foxglove": 8765,
            "dashboard": 14318,
            "reused": False,
            "pid": 99,
            "foxglove_open": True,
            "dashboard_open": True,
        },
    )
    spawned: list[str] = []
    monkeypatch.setattr(
        cs, "_spawn_remote_graph", lambda: spawned.append("graph") or (True, "Go2 + Z1")
    )
    monkeypatch.setattr(cs, "_spawn_laptop_start", lambda: spawned.append("bg") or True)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["already_running"] is False
    assert body["role"] == "laptop"
    assert body["preset"] == "go2_z1"
    assert spawned == ["graph"]
    assert "14318" in body["cricket_dashboard_url"]


@pytest.mark.asyncio
async def test_laptop_start_backgrounds_brev_when_ssh_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: False)
    monkeypatch.setattr(cs, "remote_graph_running", lambda: False)
    spawned: list[str] = []
    monkeypatch.setattr(cs, "_spawn_laptop_start", lambda: spawned.append("bg") or True)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["role"] == "laptop"
    assert body["can_start_from_cold"] is True
    assert spawned == ["bg"]
    assert "brev start" in body["detail"]
    assert body.get("start_error") is None


@pytest.mark.asyncio
async def test_start_already_in_progress_returns_400_when_credits_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stuck begin_start after a credits fail must not look like success."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: False)
    spawned: list[str] = []
    monkeypatch.setattr(cs, "_spawn_laptop_start", lambda: spawned.append("bg") or True)
    app = create_app(TelemetryStore())
    watch = app.state.cricket
    assert isinstance(watch, CricketIdleWatch)
    assert watch.begin_start() is True
    watch.set_start_error("there was issues with your credits You have run out of credits")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "credit" in str(body.get("error") or "").lower()
    assert body["start_error"] == body["error"]
    assert spawned == []


@pytest.mark.asyncio
async def test_start_already_in_progress_without_error_is_202(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: False)
    spawned: list[str] = []
    monkeypatch.setattr(cs, "_spawn_laptop_start", lambda: spawned.append("bg") or True)
    app = create_app(TelemetryStore())
    watch = app.state.cricket
    assert isinstance(watch, CricketIdleWatch)
    assert watch.begin_start() is True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["detail"] == "Start Cricket already in progress"
    assert body["start_error"] is None
    assert spawned == []


def test_brev_operator_error_detects_credits() -> None:
    from openral_observability.dashboard.cricket_session import _brev_operator_error

    msg = _brev_operator_error(
        "",
        "there was issues with your credits You have run out of credits",
    )
    assert msg is not None
    assert "credit" in msg.lower()
    assert _brev_operator_error("instance starting", "") is None


def test_brev_start_surfaces_credits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cs, "_brev_instance_status", lambda: None)

    def _fake_run(
        argv: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=1,
            stdout="",
            stderr="Error: insufficient credits — visit billing",
        )

    monkeypatch.setattr(cs, "_run", _fake_run)
    ok, detail = cs._brev_start_if_needed()
    assert ok is False
    assert "credit" in detail.lower()


def test_laptop_start_job_records_error_and_resets_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watch = CricketIdleWatch()
    bind_watch(watch)
    assert watch.begin_start() is True
    monkeypatch.setattr(cs, "_brev_start_if_needed", lambda: (False, "insufficient credits"))
    cs._laptop_start_job()
    assert watch.start_error() == "insufficient credits"
    assert watch.start_in_progress() is False
    bind_watch(None)


@pytest.mark.asyncio
async def test_get_cricket_offloads_graph_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/demo/cricket must not SSH on the uvicorn event loop."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    seen: list[int] = []

    def _record() -> bool:
        seen.append(threading.get_ident())
        time.sleep(0.05)
        return False

    monkeypatch.setattr(cs, "cricket_graph_running", _record)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    loop_id = threading.get_ident()
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        get_task = asyncio.create_task(client.get("/api/demo/cricket"))
        touch = await asyncio.wait_for(
            client.post("/api/demo/cricket/touch"),
            timeout=1.0,
        )
        get_resp = await get_task
    assert touch.status_code == 200
    assert get_resp.status_code == 200
    assert get_resp.json()["start_error"] is None
    assert seen
    assert seen[0] != loop_id


@pytest.mark.asyncio
async def test_start_after_end_in_progress_resets_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "_ssh_ok", lambda: True)
    monkeypatch.setattr(cs, "_docker_start", lambda: (True, "openral-jazzy-go2"))
    monkeypatch.setattr(cs, "remote_graph_running", lambda: True)
    monkeypatch.setattr(
        cs,
        "_ensure_tunnels",
        lambda: {
            "foxglove": 8765,
            "dashboard": 14318,
            "reused": True,
            "pid": None,
            "foxglove_open": True,
            "dashboard_open": True,
        },
    )
    app = create_app(TelemetryStore())
    watch = app.state.cricket
    assert isinstance(watch, CricketIdleWatch)
    assert watch.begin_end() is True
    assert watch.end_in_progress() is True
    watch.set_start_error("Connection closed by 75.2.122.140 port 56280")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 200, resp.text
    assert watch.end_in_progress() is False
    assert resp.json()["already_running"] is True
    assert resp.json()["start_error"] is None
    assert watch.start_error() is None


def test_laptop_ros2_argv_is_ssh_when_graph_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    argv, err = cs.ros2_command_argv(["service", "list"])
    assert err is None
    assert argv[0] == "ssh"
    assert "--" in argv
    remote = argv[argv.index("--") + 1]
    assert "docker exec" in remote
    assert "ros2" in remote
    assert "service" in remote


def test_laptop_ros2_argv_graph_down_is_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    argv, err = cs.ros2_command_argv(["service", "list"])
    assert argv == []
    assert err == cs.CRICKET_DISCONNECTED_MSG
    assert "PATH" not in (err or "")


def test_laptop_ros2_argv_prefers_start_error(monkeypatch: pytest.MonkeyPatch) -> None:
    watch = CricketIdleWatch()
    watch.set_start_error("there was issues with your credits You have run out of credits")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: watch)
    argv, err = cs.ros2_command_argv(["service", "list"])
    assert argv == []
    assert err is not None
    assert "credits" in err
    assert "PATH" not in err


def test_status_clears_stale_start_error_when_graph_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watch = CricketIdleWatch()
    watch.set_start_error("Connection closed by 75.2.122.140 port 56280")
    bind_watch(watch)
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
    payload = cs.cricket_status_payload()
    assert payload["graph_running"] is True
    assert payload["start_error"] is None
    assert watch.start_error() is None
    bind_watch(None)


def test_status_keeps_start_error_when_graph_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watch = CricketIdleWatch()
    watch.set_start_error("Connection closed by 75.2.122.140 port 56280")
    bind_watch(watch)
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    payload = cs.cricket_status_payload()
    assert payload["graph_running"] is False
    assert payload["start_error"] == "Connection closed by 75.2.122.140 port 56280"
    bind_watch(None)


def test_demo_block_clears_stale_start_error_when_graph_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watch = CricketIdleWatch()
    watch.set_start_error("Connection closed by 75.2.122.140 port 56280")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
    monkeypatch.setattr(cs, "get_watch", lambda: watch)
    assert cs.cricket_demo_block_reason() is None
    assert watch.start_error() is None
    argv, err = cs.ros2_command_argv(["service", "list"])
    assert err is None
    assert argv[0] == "ssh"


def test_host_ros2_argv_without_binary_is_path_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
    monkeypatch.setenv("PATH", str(tmp_path))
    argv, err = cs.ros2_command_argv(["service", "list"])
    assert argv == []
    assert err is not None
    assert "not on PATH" in err
