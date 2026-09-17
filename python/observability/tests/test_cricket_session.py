"""Cricket idle clock, occupancy pattern, and End script (process-boundary fakes)."""

from __future__ import annotations

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
