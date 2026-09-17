"""HTTP-level tests for the dashboard ASGI app.

Uses ``httpx.AsyncClient`` against an ``httpx.ASGITransport`` so the
tests exercise the full FastAPI request lifecycle — protobuf decode
on the OTLP/HTTP receiver routes, JSON serialization on /api/state,
SSE framing on /api/stream — without binding a real socket.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import stat
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from openral_observability.dashboard import TelemetryStore, create_app
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, InstrumentationScope, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import (
    LogRecord,
    ResourceLogs,
    ScopeLogs,
    SeverityNumber,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)


@pytest.fixture
def _otlp_traces_payload(av: Callable[[object], AnyValue]) -> Callable[[], bytes]:
    def _otlp_traces_payload() -> bytes:
        req = ExportTraceServiceRequest(
            resource_spans=[
                ResourceSpans(
                    resource=Resource(attributes=[KeyValue(key="service.name", value=av("ral"))]),
                    scope_spans=[
                        ScopeSpans(
                            spans=[
                                Span(
                                    trace_id=b"\x02" * 16,
                                    span_id=b"\x02" * 8,
                                    name="rskill.execute",
                                    start_time_unix_nano=1_000_000_000_000_000_000,
                                    end_time_unix_nano=1_000_000_000_023_000_000,
                                    attributes=[
                                        KeyValue(key="rskill.id", value=av("smolvla-libero")),
                                    ],
                                )
                            ]
                        )
                    ],
                )
            ]
        )
        return req.SerializeToString()

    return _otlp_traces_payload


@pytest.mark.asyncio
async def test_post_traces_decodes_and_updates_state(
    _otlp_traces_payload: Callable[[], bytes],
) -> None:
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/traces",
            content=_otlp_traces_payload(),
            headers={"Content-Type": "application/x-protobuf"},
        )
        assert resp.status_code == 200
        # Body must be a valid ExportTraceServiceResponse protobuf.
        ExportTraceServiceResponse.FromString(resp.content)

        state = (await client.get("/api/state")).json()
        assert state["service_name"] == "ral"
        card = state["cards"]["rskill_execute"]
        assert card["attrs"]["rskill.id"] == "smolvla-libero"
        assert card["duration_ms"] == 23.0


@pytest.fixture
def _otlp_logs_payload(av: Callable[[object], AnyValue]) -> Callable[[], bytes]:
    def _otlp_logs_payload() -> bytes:
        req = ExportLogsServiceRequest(
            resource_logs=[
                ResourceLogs(
                    resource=Resource(attributes=[KeyValue(key="service.name", value=av("ral"))]),
                    scope_logs=[
                        ScopeLogs(
                            scope=InstrumentationScope(name="openral.world_state"),
                            log_records=[
                                LogRecord(
                                    time_unix_nano=1_000_000_000_000_000_000,
                                    severity_number=SeverityNumber.SEVERITY_NUMBER_DEBUG,
                                    body=av("world_state.detected_objects count=0"),
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        return req.SerializeToString()

    return _otlp_logs_payload


@pytest.mark.asyncio
async def test_post_logs_ingests_debug_line_into_event_log(
    _otlp_logs_payload: Callable[[], bytes],
) -> None:
    """issue #318 — /v1/logs now surfaces real log lines (incl. DEBUG)."""
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/logs",
            content=_otlp_logs_payload(),
            headers={"Content-Type": "application/x-protobuf"},
        )
        assert resp.status_code == 200
        # Body must be a valid ExportLogsServiceResponse protobuf.
        ExportLogsServiceResponse.FromString(resp.content)

        state = (await client.get("/api/state")).json()
        debug = [ev for ev in state["events"] if ev["severity"] == "debug"]
        assert len(debug) == 1
        assert debug[0]["kind"] == "openral.world_state"
        assert debug[0]["title"] == "world_state.detected_objects count=0"


@pytest.mark.asyncio
async def test_post_logs_malformed_returns_400() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/logs",
            content=b"not-a-protobuf-at-all-\xff\xfe",
            headers={"Content-Type": "application/x-protobuf"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_traces_accepts_gzip_encoding(
    _otlp_traces_payload: Callable[[], bytes],
) -> None:
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = gzip.compress(_otlp_traces_payload())
        resp = await client.post(
            "/v1/traces",
            content=body,
            headers={"Content-Type": "application/x-protobuf", "Content-Encoding": "gzip"},
        )
        assert resp.status_code == 200
        state = (await client.get("/api/state")).json()
        assert "rskill_execute" in state["cards"]


@pytest.mark.asyncio
async def test_post_traces_malformed_returns_400() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/traces",
            content=b"not-a-protobuf",
            headers={"Content-Type": "application/x-protobuf"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_index_serves_html() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "OpenRAL · Live Dashboard".encode() in resp.content
        assert "<title>OpenRAL · Live Dashboard</title>".encode() in resp.content
        assert b'id="cell-cameras" hidden' not in resp.content
        assert b'data-camera="front"' in resp.content
        assert b'data-camera="top"' in resp.content
        assert b"waiting for camera" in resp.content
        # Stream URL is set in HTML; is-streaming drops the opaque placeholder
        # even when multipart MJPEG never fires img.onload.
        assert b'class="camera is-streaming"' in resp.content
        assert b'src="/api/camera/front/stream"' in resp.content
        assert b'src="/api/camera/top/stream"' in resp.content
        assert b"dashboard.js?v=walk1" in resp.content
        assert "Main · front".encode() in resp.content
        assert "Side · top".encode() in resp.content
        assert b"Add Robot" not in resp.content
        assert b"Write-controls enabled" not in resp.content


@pytest.mark.asyncio
async def test_healthz() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_config_defaults_to_empty_jaeger_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """/api/config returns an empty Jaeger URL when OPENRAL_JAEGER_UI_URL is unset.

    The UI uses this to decide whether to enable the "open in jaeger"
    footer link — an empty string keeps the link disabled with a
    tooltip rather than producing a broken-link click against a
    guessed ``localhost:16686``.
    """
    monkeypatch.delenv("OPENRAL_JAEGER_UI_URL", raising=False)
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jaeger_ui_url"] == ""
        assert body["write_controls_enabled"] is False
        assert body["demo_controls_enabled"] is False
        assert body["demo_presets"] == []
        assert body["robot_embodiment_tags"] == []
        assert body["walk_skill_ids"] == []
        assert body["cricket"] is None
        # voice_prompt_enabled (vad_assets.py) reflects whether the offline
        # VAD binary assets are present on disk — not asserted True/False
        # here since that depends on whether they were ever downloaded on
        # this host; only the shape of the flag is contractual.
        assert isinstance(body["voice_prompt_enabled"], bool)


@pytest.mark.asyncio
async def test_api_config_demo_controls_when_write_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write-controls on → demo bar presets are listed for the Go2 walk POC."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.delenv("OPENRAL_CRICKET_IDLE_S", raising=False)
    monkeypatch.delenv("OPENRAL_CRICKET_INSTANCE", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["demo_controls_enabled"] is True
        ids = {p["id"] for p in body["demo_presets"]}
        assert ids == {"go2", "go2_z1"}
        by_id = {p["id"]: p for p in body["demo_presets"]}
        assert by_id["go2"]["resume"] == "stand"
        assert by_id["go2"]["story"] == "bare"
        assert by_id["go2_z1"]["resume"] == ""
        assert by_id["go2_z1"]["story"] == "armed"
        assert body["robot_embodiment_tags"] == []
        assert "OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32" in body["walk_skill_ids"]
        cricket = body["cricket"]
        assert cricket["can_start_from_cold"] is False
        assert cricket["role"] == "host"
        assert cricket["instance"] == "abundant-turquoise-cricket"
        assert cricket["idle_timeout_s"] == 900.0
        assert cricket["idle_enabled"] is True
        assert cricket["foxglove_url"] == "ws://127.0.0.1:8765"
        assert "brev start" in cricket["start_from_cold_hint"]


@pytest.mark.asyncio
async def test_demo_stand_requires_write_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/stand")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_stop_requires_write_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/stop")
        assert resp.status_code == 403


def test_cancel_goal_succeeded_parses_return_code() -> None:
    from openral_observability.dashboard.demo_controls import (
        _cancel_goal_succeeded,
        _trigger_success,
    )

    assert _cancel_goal_succeeded("response:\n  return_code: 0\n") is True
    assert _cancel_goal_succeeded("return_code=3") is True  # already terminated
    assert _cancel_goal_succeeded("return_code: 2") is True  # nothing in flight
    assert _cancel_goal_succeeded("return_code: 1") is False  # rejected
    assert _cancel_goal_succeeded("no return code here") is False
    assert _trigger_success("response:\n  success: True\n") is True
    assert _trigger_success("success=True") is True
    assert _trigger_success("success: false") is False


@pytest.fixture
def ros2_demo_stop_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Fake ``ros2`` that accepts CancelGoal then ResetToPose, in that order."""
    log = tmp_path / "ros2_calls.txt"
    shim = tmp_path / "ros2"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib\n"
        + f"path = pathlib.Path({str(log)!r})\n"
        + "prev = path.read_text() if path.exists() else ''\n"
        + "path.write_text(prev + json.dumps(sys.argv[1:]) + '\\n')\n"
        + "argv = ' '.join(sys.argv)\n"
        + "if 'cancel_goal' in argv:\n"
        + "    print('response:')\n"
        + "    print('  return_code: 0')\n"
        + "    print('  goals_canceling: []')\n"
        + "elif 'ResetToPose' in argv or 'reset_to_pose' in argv:\n"
        + "    print('response:')\n"
        + "    print('  success: True')\n"
        + "else:\n"
        + "    print('unexpected', argv)\n"
        + "    raise SystemExit(1)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


@pytest.mark.asyncio
async def test_demo_stop_cancels_then_stands(
    monkeypatch: pytest.MonkeyPatch, ros2_demo_stop_shim: Path
) -> None:
    """Stop cancels ExecuteRskill (no e-stop) then snaps Hub home so Apply can re-run."""
    from openral_observability.dashboard import demo_controls

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2")
    monkeypatch.setattr(demo_controls, "_CANCEL_THEN_STAND_S", 0.0)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/stop")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["action"] == "stop"
    assert body["canceled"] is True
    assert body["robot_id"] == "go2"
    raw = await asyncio.to_thread(ros2_demo_stop_shim.read_text)
    lines = [json.loads(line) for line in raw.splitlines() if line]
    assert len(lines) == 2
    joined = [" ".join(args) for args in lines]
    assert "cancel_goal" in joined[0]
    assert "/openral/execute_rskill/_action/cancel_goal" in joined[0]
    assert "goal_info" in joined[0]
    assert "ResetToPose" in joined[1]
    assert "/openral/go2/reset_to_pose" in joined[1]
    assert all("estop" not in " ".join(args).lower() for args in lines)


@pytest.mark.asyncio
async def test_demo_load_rejects_unknown_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/load", json={"preset": "not_a_robot"})
        assert resp.status_code == 400
        assert "preset" in resp.json()["error"]


def _patch_demo_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    from openral_observability.dashboard import demo_controls

    def _fake_spawn(preset_id: str) -> tuple[bool, str]:
        return True, demo_controls.DEMO_PRESETS[preset_id]["label"]

    monkeypatch.setattr(demo_controls, "_spawn_scene_reload", _fake_spawn)


@pytest.mark.asyncio
async def test_demo_load_bare_go2_auto_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wizard: after Bare Go2 load, next beat is auto-stand (not Recalibrate)."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    _patch_demo_spawn(monkeypatch)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/load", json={"preset": "go2"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["next"] == "auto_stand"
    assert body["resume"] == "stand"
    assert body["robot_id"] == "go2"
    assert body["story"] == "bare"
    assert "auto-calibrates" in body["detail"]
    assert "select a skill and Apply" in body["detail"]
    assert "~30" in body["detail"]


@pytest.mark.asyncio
async def test_demo_load_go2_z1_asks_for_recalibrate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switching to Go2+Z1 forces Recalibrate before Apply skill (no auto-walk)."""
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    _patch_demo_spawn(monkeypatch)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/load", json={"preset": "go2_z1"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["next"] == "recalibrate"
    assert body["resume"] == ""
    assert body["robot_id"] == "go2_z1"
    assert body["story"] == "armed"
    assert "Recalibrate" in body["detail"]


@pytest.mark.asyncio
async def test_cricket_routes_require_write_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/demo/cricket")).status_code == 403
        assert (await client.post("/api/demo/cricket/start")).status_code == 403
        assert (await client.post("/api/demo/cricket/end")).status_code == 403
        assert (await client.post("/api/demo/cricket/touch")).status_code == 403


@pytest.mark.asyncio
async def test_cricket_start_already_running_does_not_respawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openral_observability.dashboard import cricket_session, demo_controls

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setattr(cricket_session, "deploy_sim_pids", lambda: [4242])
    spawned: list[str] = []
    monkeypatch.setattr(
        demo_controls, "_spawn_scene_reload", lambda preset: spawned.append(preset) or (True, "x")
    )
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_running"] is True
    assert body["action"] == "start"
    assert spawned == []


@pytest.mark.asyncio
async def test_cricket_start_spawns_graph_when_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openral_observability.dashboard import cricket_session, demo_controls

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2_z1")
    monkeypatch.setattr(cricket_session, "deploy_sim_pids", lambda: [])
    spawned: list[str] = []
    monkeypatch.setattr(
        demo_controls,
        "_spawn_scene_reload",
        lambda preset: (
            spawned.append(preset) or (True, demo_controls.DEMO_PRESETS[preset]["label"])
        ),
    )
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/demo/cricket/start")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["already_running"] is False
    assert body["preset"] == "go2_z1"
    assert body["can_start_from_cold"] is False
    assert body["role"] == "host"
    assert spawned == ["go2_z1"]


@pytest.mark.asyncio
async def test_cricket_end_cancels_skill_then_spawns_end_script(
    monkeypatch: pytest.MonkeyPatch, ros2_demo_stop_shim: Path
) -> None:
    """End Cricket cancels ExecuteRskill (no e-stop) then detaches the end script."""
    from openral_observability.dashboard import cricket_session

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_HALT_HOST", "0")
    spawned: list[bool] = []
    monkeypatch.setattr(cricket_session, "_spawn_cricket_end", lambda: spawned.append(True) or True)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/cricket/end")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["action"] == "end"
    assert body["accepted"] is True
    assert "E-STOP" not in body["detail"] or "no E-STOP" in body["detail"]
    assert spawned == [True]
    raw = await asyncio.to_thread(ros2_demo_stop_shim.read_text)
    lines = [json.loads(line) for line in raw.splitlines() if line]
    assert lines, "expected a CancelGoal ros2 call"
    assert "cancel_goal" in " ".join(lines[0])
    assert all("estop" not in " ".join(args).lower() for args in lines)
    assert all("ResetToPose" not in " ".join(args) for args in lines)


@pytest.mark.asyncio
async def test_cricket_touch_resets_idle_and_get_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openral_observability.dashboard.cricket_session import CricketIdleWatch, bind_watch

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_IDLE_S", "100")
    clock = {"t": 0.0}
    watch = CricketIdleWatch(monotonic=lambda: clock["t"], poll_s=1.0)
    app = create_app(TelemetryStore())
    app.state.cricket = watch
    bind_watch(watch)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = (await client.get("/api/demo/cricket")).json()
        assert first["idle_remaining_s"] == 100.0
        clock["t"] = 40.0
        polled = (await client.get("/api/demo/cricket")).json()
        assert polled["idle_remaining_s"] == 60.0
        touched = await client.post("/api/demo/cricket/touch")
        assert touched.status_code == 200
        after = (await client.get("/api/demo/cricket")).json()
        assert after["idle_remaining_s"] == 100.0


def test_demo_reload_script_does_not_pkill_self() -> None:
    """bash -c + pkill -f 'openral deploy sim' matches the killer argv."""
    from openral_observability.dashboard.demo_controls import _build_demo_reload_script

    script = _build_demo_reload_script(
        preset_id="go2",
        repo=Path("/openral"),
        scene=Path("/openral/scenes/deploy/go2_walk.yaml"),
        robot_id="go2",
        domain="77",
        openral_bin="/openral/.venv/bin/openral",
    )
    assert "pkill" not in script
    assert "[o]penral deploy sim" in script
    assert "bash -c" not in script
    assert ". /opt/ros/jazzy/setup.bash" in script
    assert "ulimit -c 0" in script
    assert "OPENRAL_CRICKET_INSTANCE" in script
    assert "OPENRAL_CRICKET_HALT_HOST" in script


def test_spawn_scene_reload_execs_script_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Spawn argv is ``bash /tmp/openral_demo_relaunch.sh``, not bash -c."""
    from openral_observability.dashboard import demo_controls

    popped: list[list[str]] = []
    script_path = tmp_path / "openral_demo_relaunch.sh"
    repo = tmp_path / "openral"
    (repo / "scenes" / "deploy").mkdir(parents=True)
    (repo / "scenes" / "deploy" / "go2_walk.yaml").write_text("scene: go2_walk\n")
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "openral").write_text("")
    monkeypatch.setattr(demo_controls, "_RELOAD_SCRIPT_PATH", script_path)
    monkeypatch.setattr(demo_controls, "_repo_root", lambda: repo)

    def _fake_popen(argv: list[str], **kwargs: object) -> object:
        del kwargs
        popped.append(list(argv))

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(demo_controls.subprocess, "Popen", _fake_popen)
    ok, label = demo_controls._spawn_scene_reload("go2")
    assert ok is True
    assert label == "Bare Go2"
    assert popped == [["bash", str(script_path)]]
    body = script_path.read_text(encoding="utf-8")
    assert "pkill" not in body
    assert "[o]penral deploy sim" in body
    assert "go2_walk.yaml" in body


def test_dashboard_js_reload_poll_requires_healthz_gap() -> None:
    """Poll must wait for healthz to drop, then allow up to 180s."""
    js = (
        Path(__file__).resolve().parents[1]
        / "src/openral_observability/dashboard/static/dashboard.js"
    )
    text = js.read_text(encoding="utf-8")
    assert "sawDown" in text
    assert "DEMO_RELOAD_MAX_TRIES = 90" in text
    assert "tries > 45" not in text


def test_dashboard_js_bare_go2_auto_stands_armed_asks_recalibrate() -> None:
    """Bare Go2 auto-stands after load; Go2+Z1 confirms Recalibrate; skill is saved."""
    js = (
        Path(__file__).resolve().parents[1]
        / "src/openral_observability/dashboard/static/dashboard.js"
    )
    text = js.read_text(encoding="utf-8")
    assert "autoCalibrateBareGo2" in text
    assert 'resume || "") === "stand"' in text
    assert "Go2+Z1 needs Recalibrate before you can apply a skill" in text
    assert "openral.demo.skill." in text
    assert "calibrated — select skill and Apply" in text
    assert "Never auto-walk" in text
    assert "/api/demo/cricket/start" in text
    assert "/api/demo/cricket/end" in text
    assert "auto-stop paused — skill running" in text
    assert "This is not E-STOP" in text
    assert 'fetch("/api/demo/cricket"' in text
    assert "CRICKET_TOUCH_MIN_MS" in text
    assert "offerCricketViewers" in text
    assert "foxglove_open_url" in text
    assert 'data.role === "laptop"' in text
    assert "ws://localhost:8765" in text
    assert "savedIsWalk" in text
    assert "if (preferWalk && walkId) selectEl.value = walkId;" in text
    assert 'demoPost("/api/demo/walk", { skill_id: skillId })' in text


def test_dashboard_js_mjpeg_is_streaming_without_img_load() -> None:
    """Opaque placeholder must drop when the stream URL is set, not on img.onload.

    Multipart MJPEG often never fires load; that left tiles on
    "waiting for camera" while /api/camera/{front,top}/stream was live.
    """
    root = Path(__file__).resolve().parents[1] / "src/openral_observability/dashboard/static"
    js = (root / "dashboard.js").read_text(encoding="utf-8")
    css = (root / "dashboard.css").read_text(encoding="utf-8")
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "if (img.getAttribute(\"src\")) div.classList.add(\"is-streaming\")" in js
    assert "if (hasFrame) tile.root.classList.add(\"is-streaming\")" in js
    assert "cam.age_ms != null && cam.age_ms < 2000" in js
    assert ".camera:has(img[src]) .camera-placeholder" in css
    assert 'class="camera is-streaming"' in html
    assert 'src="/api/camera/front/stream"' in html
    assert 'src="/api/camera/top/stream"' in html


def test_go2_z1_embodiment_tags_intersect_go2_walk_skill() -> None:
    """Loader gate is tag intersection: go2 walk skill fits go2_z1."""
    from openral_observability.dashboard.demo_controls import robot_embodiment_tags

    tags = robot_embodiment_tags("go2_z1")
    assert "go2" in tags
    assert "go2_z1" in tags


def test_is_walk_skill_id_matches_intree_and_hub() -> None:
    """Apply routes the rsl-rl walk skill through walk_response, not a second API."""
    from openral_observability.dashboard.demo_controls import is_walk_skill_id

    assert is_walk_skill_id("OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32")
    assert is_walk_skill_id("Acquire/rskill-rsl-rl-onnx-go2-velocity-flat")
    assert is_walk_skill_id("rsl-rl-onnx-go2-velocity-flat")
    assert not is_walk_skill_id("OpenRAL/rskill-zero-go2_z1-arm_ready-fp32")
    assert not is_walk_skill_id("")


def test_walk_skill_dispatch_ids_puts_selected_first() -> None:
    """Picker Acquire/… id must lead so Apply does not skip the live Hub skill."""
    from openral_observability.dashboard.demo_controls import walk_skill_dispatch_ids

    acquire = "Acquire/rskill-rsl-rl-onnx-go2-velocity-flat"
    ids = walk_skill_dispatch_ids(acquire)
    assert ids[0] == acquire
    assert "OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32" in ids
    assert walk_skill_dispatch_ids("")[0] == acquire
    assert walk_skill_dispatch_ids("OpenRAL/rskill-zero-go2_z1-arm_ready-fp32")[0] == acquire


def test_go2_z1_recalibrate_pose_is_arm_ready() -> None:
    """Recalibrate must park the Z1 at ARM_READY so Walk hold-snaps that pose."""
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY
    from openral_observability.dashboard.demo_controls import _HOME_POSE_BY_ROBOT

    expected = (*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY)
    assert _HOME_POSE_BY_ROBOT["go2_z1"] == expected
    assert _HOME_POSE_BY_ROBOT["go2"] == tuple(GO2_HOME_JOINT_TARGETS)


@pytest.mark.asyncio
async def test_demo_page_hides_run_strip_and_offers_apply_skill() -> None:
    """Operator surface is one Apply button + skill picker, not Run plus Walk."""
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="demo-skill"' in html
    assert 'id="demo-apply"' in html
    assert "Apply skill" in html
    assert 'id="demo-stop"' in html
    assert 'id="demo-cricket-start"' in html
    assert 'id="demo-cricket-end"' in html
    assert 'id="demo-cricket-links"' in html
    assert "Start Cricket" in html
    assert "End Cricket" in html
    assert 'id="demo-walk"' not in html
    assert "▶ Run" in html  # fallback strip still in the page, hidden when demo shows
    assert 'id="card-runskill"' in html


@pytest.mark.asyncio
async def test_api_config_go2_z1_tags_include_go2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2_z1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        body = (await client.get("/api/config")).json()
    assert body["robot_id"] == "go2_z1"
    assert "go2" in body["robot_embodiment_tags"]
    assert "go2_z1" in body["robot_embodiment_tags"]


@pytest.mark.asyncio
async def test_api_config_reflects_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured OPENRAL_JAEGER_UI_URL is surfaced via /api/config (trailing slash stripped)."""
    monkeypatch.setenv("OPENRAL_JAEGER_UI_URL", "https://jaeger.example/")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        assert resp.json()["jaeger_ui_url"] == "https://jaeger.example"


@pytest.mark.asyncio
async def test_subscriber_queue_receives_ingest_payload(
    _otlp_traces_payload: Callable[[], bytes],
) -> None:
    """The SSE wiring at the store level: subscribers see ingest deltas.

    The actual ``/api/stream`` HTTP framing is exercised in the
    integration test on a real uvicorn socket
    (``tests.integration.test_dashboard_end_to_end``); httpx's
    ``ASGITransport`` buffers the full response body so a streaming
    endpoint deadlocks against it. Here we validate the store-level
    publish channel that the SSE generator awaits on.
    """
    store = TelemetryStore()
    queue = store.subscribe()
    try:
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest,
        )

        req = ExportTraceServiceRequest.FromString(_otlp_traces_payload())
        store.ingest_spans(list(req.resource_spans))
        payload = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert "rskill_execute" in payload["cards"]
    finally:
        store.unsubscribe(queue)


# ─────────────────────────── POST /api/prompt ────────────────────────────────
#
# These tests exercise the real subprocess-spawn path. Per CLAUDE.md §1.11 /
# §5.4 we do not mock `subprocess` / `asyncio.create_subprocess_exec`; instead
# we shadow `openral` on PATH with a tiny real script that records its argv to
# a log file. That gives us a green test only if the production code actually
# spawns a child with the expected args.


@pytest.fixture
def openral_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install an `openral` shim on PATH that logs its argv and exits 0.

    Yields the log file. Tests read the file to confirm the dashboard
    spawned `openral prompt <text> --topic /openral/prompt_in/dashboard`.
    """
    log = tmp_path / "openral_calls.txt"
    shim = tmp_path / "openral"
    # Real shim — records argv (minus script path) as JSON and prints a
    # line matching the canonical `openral prompt` stdout so the dashboard
    # endpoint surfaces it back to the operator unchanged.
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib\n"
        + f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        + "topic = sys.argv[sys.argv.index('--topic') + 1]\n"
        + "print(f'openral prompt: published on {topic} text={sys.argv[2]!r}')\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


def _read_shim_argv(log: Path) -> list[str]:
    """Sync helper so the async test stays clear of ASYNC240."""
    import json as _json

    return list(_json.loads(log.read_text()))


@pytest.mark.asyncio
async def test_post_prompt_invokes_openral_with_dashboard_topic(openral_shim: Path) -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/prompt", json={"text": "pick the red cube"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert "published on /openral/prompt_in/dashboard" in body["stdout"]
    # The shim logged the real argv — confirms we shelled out to `openral
    # prompt` with --topic pointing at the dashboard source.
    argv = _read_shim_argv(openral_shim)
    assert argv == ["prompt", "pick the red cube", "--topic", "/openral/prompt_in/dashboard"]


@pytest.mark.asyncio
async def test_post_prompt_rejects_empty_text(openral_shim: Path) -> None:
    del openral_shim  # fixture present so PATH is shimmed, but no call expected
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for payload in ({}, {"text": ""}, {"text": "   "}, {"text": 42}):
            resp = await client.post("/api/prompt", json=payload)
            assert resp.status_code == 400, payload


@pytest.mark.asyncio
async def test_post_prompt_propagates_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real shim, but exits non-zero — exercises the 502 path without mocks.
    shim = tmp_path / "openral"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import sys\n"
        + "print('boom', file=sys.stderr)\n"
        + "sys.exit(7)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/prompt", json={"text": "go"})
        assert resp.status_code == 502
        body = resp.json()
        assert body["returncode"] == 7
        assert "boom" in body["stderr"]


@pytest.mark.asyncio
async def test_post_prompt_returns_503_when_openral_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force an empty PATH so `shutil.which("openral")` returns None.
    monkeypatch.setenv("PATH", str(tmp_path))
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/prompt", json={"text": "go"})
        assert resp.status_code == 503
        assert "not on PATH" in resp.json()["error"]


# ───────────────────────── POST /api/transcribe (STT) ────────────────────────
#
# Operator voice prompt: the dashboard mic POSTs captured audio here and the
# endpoint runs a local faster-whisper model (ships with the dashboard extra).
# Per CLAUDE.md §1.11 we use the real model on a real (public-domain) speech
# clip — no mocked transcriber. The heavy end-to-end test importorskips
# faster-whisper (it is a default dep, so it runs in a normal env; the skip is
# only the CI-without-the-dashboard-extra path, §1.12); the contract tests
# (empty body, dependency-stripped 503) run everywhere with no model download.

_JFK_WAV = Path(__file__).parent / "fixtures" / "jfk.wav"


@pytest.mark.asyncio
async def test_post_transcribe_rejects_empty_body() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/transcribe", content=b"")
        assert resp.status_code == 400
        assert "empty audio" in resp.json()["error"]


@pytest.mark.asyncio
async def test_post_transcribe_returns_503_when_faster_whisper_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real import failure (not a mocked transcriber): shadow `faster_whisper`
    # with None in sys.modules so the in-function import raises ImportError,
    # exercising the graceful-degradation path exactly as an uninstalled host.
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/transcribe", content=b"\x00\x01\x02\x03")
        assert resp.status_code == 503
        assert "speech-to-text unavailable" in resp.json()["error"]


@pytest.mark.asyncio
async def test_post_transcribe_real_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    # End-to-end with the real model on a real public-domain JFK clip
    # ("...ask not what your country can do for you..."). tiny.en keeps the
    # one-time model download light; it transcribes this clean 16 kHz clip
    # reliably. Skips only if faster-whisper is absent (non-dashboard install).
    pytest.importorskip("faster_whisper")
    monkeypatch.setenv("OPENRAL_STT_MODEL", "tiny.en")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=120.0
    ) as client:
        resp = await client.post(
            "/api/transcribe",
            content=_JFK_WAV.read_bytes(),
            headers={"content-type": "audio/wav"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["model"] == "tiny.en"
        assert "country" in body["text"].lower(), body["text"]


@pytest.fixture
def _otlp_camera_payload(av: Callable[[object], AnyValue]) -> Callable[[str, str], bytes]:
    def _otlp_camera_payload(source: str, thumb_b64: str) -> bytes:
        from openral_observability import semconv

        return ExportTraceServiceRequest(
            resource_spans=[
                ResourceSpans(
                    resource=Resource(attributes=[KeyValue(key="service.name", value=av("ral"))]),
                    scope_spans=[
                        ScopeSpans(
                            scope=InstrumentationScope(name="test"),
                            spans=[
                                Span(
                                    name=semconv.SPAN_SENSORS_READ_LATEST,
                                    trace_id=b"\x11" * 16,
                                    span_id=b"\x22" * 8,
                                    attributes=[
                                        KeyValue(key=semconv.SENSORS_SOURCE, value=av(source)),
                                        KeyValue(
                                            key=semconv.SENSORS_THUMBNAIL_JPEG_B64,
                                            value=av(thumb_b64),
                                        ),
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ]
        ).SerializeToString()

    return _otlp_camera_payload


@pytest.mark.asyncio
async def test_camera_stream_emits_jpeg_part(
    _otlp_camera_payload: Callable[[str, str], bytes],
) -> None:
    # httpx.ASGITransport buffers the full response body before returning,
    # so a true infinite MJPEG StreamingResponse deadlocks it (same limitation
    # noted in test_subscriber_queue_receives_ingest_payload for SSE). We
    # therefore exercise the two helpers directly — the same bytes the live
    # server would push over the wire — confirming the store ingest → b64
    # thumbnail → MJPEG part bytes round-trip produces valid framing.
    # Wire-format coverage (route response headers, Content-Type boundary,
    # 404 for unknown sources over a real socket) lives in
    # test_dashboard_mjpeg_integration.py which launches a real uvicorn server.
    import base64

    from openral_observability.dashboard.app import _camera_thumb, _mjpeg_part

    store = TelemetryStore()
    app = create_app(store)
    jpeg = b"\xff\xd8\xff\xe0jpegbytes\xff\xd9"
    thumb_b64 = base64.b64encode(jpeg).decode("ascii")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post("/v1/traces", content=_otlp_camera_payload("wrist", thumb_b64))

    # Helpers: round-trip through the store → b64 → MJPEG part bytes.
    thumb = _camera_thumb(store, "wrist")
    assert thumb == thumb_b64
    chunk = _mjpeg_part(thumb)
    assert b"Content-Type: image/jpeg" in chunk
    assert b"Content-Length: " in chunk
    assert jpeg in chunk


@pytest.mark.asyncio
async def test_camera_stream_unknown_source_404() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/camera/nope/stream")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_empty_store_still_exposes_go2_hero_cameras() -> None:
    """WAITING with no OTLP still advertises front (main) and top (side)."""
    from openral_observability.dashboard.app import cricket_camera_stream_url
    from openral_observability.dashboard.cricket_session import (
        DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT,
        on_cricket_host,
    )

    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        state = (await client.get("/api/state")).json()
    cameras = state["topics"]["perception"]["cameras"]
    assert cameras["front"]["role"] == "main"
    assert cameras["top"]["role"] == "side"
    assert "thumbnail_jpeg_b64" not in cameras["front"]
    if on_cricket_host():
        assert cricket_camera_stream_url("front") is None
    else:
        assert cricket_camera_stream_url("front") == (
            f"http://127.0.0.1:{DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT}/api/camera/front/stream"
        )
        assert cricket_camera_stream_url("top") == (
            f"http://127.0.0.1:{DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT}/api/camera/top/stream"
        )


@pytest.mark.asyncio
async def test_api_robots_disabled_when_no_discovery() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/robots")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False, "robots": []}


@pytest.mark.asyncio
async def test_api_robots_lists_registry() -> None:
    from openral_observability.dashboard.discovery import DiscoveredRobot, Discovery, RobotRegistry

    reg = RobotRegistry()
    reg.upsert(
        DiscoveredRobot(name="arm", addresses=["10.0.0.5"], port=4318, properties={}, last_seen=1.0)
    )
    disc = Discovery(registry=reg)
    disc.enabled = True
    app = create_app(TelemetryStore())
    app.state.discovery = disc
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/robots")
    body = resp.json()
    assert body["enabled"] is True
    assert body["robots"][0]["name"] == "arm"
    assert body["robots"][0]["port"] == 4318


# ─────────────────────────── GET /api/skills ─────────────────────────────────
#
# Read-only index backing the page's Run-skill picker. Validated against the
# REAL in-tree rskills/ manifests (CLAUDE.md §1.11) — the ids must be the
# `manifest.name` values the skill_runner's in-tree resolver indexes, or the
# operator's pick 403s/ROSConfigErrors on dispatch.


@pytest.mark.asyncio
async def test_skills_lists_intree_manifests() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/skills")
    assert resp.status_code == 200
    skills = resp.json()["skills"]
    if not skills:
        pytest.skip("in-tree rskills/ not discoverable from this install (no repo root)")
    by_dir = {s["dir"]: s for s in skills}
    # The Go2 locomotion policy is the deploy-sim quadruped path the Run-skill
    # control exists for: proprio-only ONNX, one declared goal param.
    go2 = by_dir["rsl-rl-onnx-go2-velocity-flat"]
    assert go2["id"] == "OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32"
    assert go2["role"] == "s1"
    assert go2["embodiment_tags"] == ["go2", "go2_z1"]
    assert go2["model_family"] == "rsl_rl_onnx"
    assert go2["description"]


@pytest.mark.asyncio
async def test_skills_expose_goal_params_schema_for_the_ui() -> None:
    """The picker renders its param boxes from the manifest schema, not a hardcode."""
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/skills")
    skills = {s["dir"]: s for s in resp.json()["skills"]}
    if "rsl-rl-onnx-go2-velocity-flat" not in skills:
        pytest.skip("in-tree rskills/ not discoverable from this install (no repo root)")
    schema = skills["rsl-rl-onnx-go2-velocity-flat"]["goal_params_schema"]
    vel = schema["properties"]["velocity_commands"]
    assert vel["type"] == "array"
    assert vel["minItems"] == vel["maxItems"] == 3
    assert vel["items"]["type"] == "number"


@pytest.mark.asyncio
async def test_skills_survives_missing_rskill_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dashboard-only install has no openral_rskill; the picker degrades, not 500s."""
    monkeypatch.setitem(sys.modules, "openral_rskill.loader", None)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/skills")
    assert resp.status_code == 200
    assert resp.json() == {"skills": []}


# ─────────────────────── POST /api/skill/execute ─────────────────────────────
#
# issue #75c — flag-gated skill switch. DEFAULT OFF. Tests are
# written BEFORE the implementation (TDD — safety-touching per CLAUDE.md §4.2).
# The "no ros2" case reuses the empty-PATH trick from
# test_post_prompt_returns_503_when_openral_missing above.


@pytest.mark.asyncio
async def test_skill_execute_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "x"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skill_execute_requires_skill_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "  "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_skill_execute_503_without_ros2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("PATH", str(tmp_path))  # empty PATH → shutil.which("ros2") is None
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 503


# ── async accept-then-track tests (issue #75c) ────────────────────────────────
#
# Fake `ros2` shims (process-boundary doubles, allowed per CLAUDE.md §1.11)
# that simulate: goal accepted, goal rejected, slow action server (accept
# timeout). Mirror the openral_shim pattern above.


@pytest.fixture
def ros2_accepted_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install a fake `ros2` that prints 'Goal accepted with ID: test-123' then exits 0."""
    log = tmp_path / "ros2_calls.txt"
    shim = tmp_path / "ros2"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib\n"
        + f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        + "print('Waiting for an action server to become available...', flush=True)\n"
        + "print('Sending goal:', flush=True)\n"
        + "print('Goal accepted with ID: test-123', flush=True)\n"
        # Simulate some trailing output that the background drain reads
        + "print('Result:', flush=True)\n"
        + "print('  success: True', flush=True)\n"
        + "print('  trace_id: abc-trace-1', flush=True)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


@pytest.fixture
def ros2_rejected_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install a fake `ros2` that prints 'Goal was rejected' then exits 1."""
    log = tmp_path / "ros2_calls.txt"
    shim = tmp_path / "ros2"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib\n"
        + f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        + "print('Waiting for an action server to become available...', flush=True)\n"
        + "print('Sending goal:', flush=True)\n"
        + "print('Goal was rejected :(', flush=True)\n"
        + "sys.exit(1)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


@pytest.fixture
def ros2_slow_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install a fake `ros2` that sleeps 5 s without printing any acceptance line."""
    log = tmp_path / "ros2_calls.txt"
    shim = tmp_path / "ros2"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib, time\n"
        + f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        + "time.sleep(5)\n"
        + "print('Goal accepted with ID: too-late', flush=True)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


@pytest.mark.asyncio
async def test_skill_execute_accepted_returns_202(
    monkeypatch: pytest.MonkeyPatch, ros2_accepted_shim: Path
) -> None:
    """A fake ros2 that prints 'Goal accepted with ID: test-123' → HTTP 202 with goal_id."""
    del ros2_accepted_shim  # fixture installs the shim on PATH; log file not needed here
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["goal_id"] == "test-123"
    assert "detail" in body
    # Give the background drain task a tick to complete (it's fire-and-forget)
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_skill_execute_rejected_returns_409(
    monkeypatch: pytest.MonkeyPatch, ros2_rejected_shim: Path
) -> None:
    """A fake ros2 that prints 'Goal was rejected' → HTTP 409 status=rejected."""
    del ros2_rejected_shim  # fixture installs the shim on PATH
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["status"] == "rejected"


@pytest.mark.asyncio
async def test_skill_execute_accept_timeout_returns_504(
    monkeypatch: pytest.MonkeyPatch, ros2_slow_shim: Path
) -> None:
    """A fake ros2 that sleeps 5 s without printing acceptance → HTTP 504 (accept timeout)."""
    del ros2_slow_shim  # fixture installs the shim on PATH
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    # Set a very short acceptance timeout so the test runs fast
    monkeypatch.setenv("OPENRAL_DASHBOARD_SKILL_ACCEPT_TIMEOUT_S", "1")
    app = create_app(TelemetryStore())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=10.0
    ) as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 504, resp.text
    body = resp.json()
    assert "accept" in body["error"].lower(), body


@pytest.mark.asyncio
async def test_skill_execute_rejects_non_one_truthy_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the exact string "1" enables write-controls.

    Common truthy strings ("true", "yes", "on", "True") must NOT unlock the
    endpoint. This locks the safety default against a future refactor that
    loosens the check from a strict equality to a broader truthiness test.
    """
    for truthy_non_one in ("true", "True", "yes", "on", "1 ", " 1", "2"):
        monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", truthy_non_one)
        app = create_app(TelemetryStore())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            resp = await client.post("/api/skill/execute", json={"skill_id": "x"})
        assert resp.status_code == 403, (
            f"expected 403 for OPENRAL_DASHBOARD_WRITE_CONTROLS={truthy_non_one!r}, "
            f"got {resp.status_code}"
        )


# ─────────────────────── POST /api/param/set ─────────────────────────────────
#
# issue #75c — flag-gated param tune. DEFAULT OFF; safety params
# refused via denylist. Tests written BEFORE implementation (TDD — safety-
# touching per CLAUDE.md §4.2).


@pytest.mark.asyncio
async def test_param_set_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", raising=False)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/param/set", json={"node": "/n", "name": "rate_hz", "value": "20"}
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_param_set_refuses_safety_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/param/set", json={"node": "/n", "name": "max_velocity", "value": "9.9"}
        )
    assert resp.status_code == 403
    assert "safety" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_param_set_allowed_param_503_without_ros2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("PATH", str(tmp_path))
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/param/set", json={"node": "/n", "name": "rate_hz", "value": "20"}
        )
    assert resp.status_code == 503


# ── Denylist gap regression (issue #75c) ──────────────────────────────────────
#
# Before this fix, "estop" did not match "e_stop_enable" and "deadman" did not
# match "dead_man_timeout" because the substring "estop" ∉ "e_stop_enable" and
# "deadman" ∉ "dead_man_timeout".  Likewise "safety" ∉ "safe_mode".  The new
# tokens e_stop / dead_man / safe close all three gaps fail-closed.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "param_name",
    [
        "e_stop_enable",  # was bypassing denylist (e_stop gap)
        "dead_man_timeout",  # was bypassing denylist (dead_man gap)
        "safe_mode",  # was bypassing denylist (safe/safety gap)
        "VELOCITY_LIMIT",  # existing token, verifies case-insensitivity still works
    ],
)
async def test_param_set_refuses_underscored_safety_params(
    monkeypatch: pytest.MonkeyPatch, param_name: str
) -> None:
    """Underscored ROS 2 safety param names must return 403 and never shell out.

    Regression lock for issue #75c: the original denylist missed
    e_stop_enable, dead_man_timeout, and safe_mode because substring matching
    on the compact tokens (estop, deadman, safety) does not cover the
    underscored ROS 2 naming convention.
    """
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    # No ros2 shim on PATH — a correct impl must refuse before shelling out.
    # If a bug lets the name through, the subprocess path hits 503 (no ros2),
    # not 403, so the assertion below catches the bypass clearly.
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/param/set",
            json={"node": "/safety_kernel", "name": param_name, "value": "1"},
        )
    assert resp.status_code == 403, (
        f"expected 403 (denylist) for param {param_name!r}, got {resp.status_code} — "
        "underscored safety param bypassed the denylist"
    )
    body = resp.json()
    assert "safety" in body["error"].lower() or "refused" in body["error"].lower(), body


@pytest.mark.asyncio
async def test_vad_static_text_assets_served_offline() -> None:
    # The small browser glue files stay committed and must serve with
    # browser-loadable MIME types. Large ONNX/WASM binaries are fetched by
    # vad_assets.ensure_vad_assets() at dashboard startup, so this app-level
    # static route test must not require them to exist in a fresh checkout.
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    expected = {
        "bundle.min.js": "javascript",
        "vad.worklet.bundle.min.js": "javascript",
        "ort.wasm.min.js": "javascript",
        "ort-wasm-simd-threaded.mjs": "javascript",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for name, ctype in expected.items():
            resp = await client.get(f"/static/vendor/vad/{name}")
            assert resp.status_code == 200, name
            if ctype is not None:
                assert ctype in resp.headers["content-type"], (name, resp.headers["content-type"])


# ─────────────────────── GET /api/config — write_controls_enabled ────────────


@pytest.mark.asyncio
async def test_api_config_reports_write_controls_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        body = (await client.get("/api/config")).json()
    assert body["write_controls_enabled"] is True
    assert body["demo_controls_enabled"] is True
    assert {p["id"] for p in body["demo_presets"]} == {"go2", "go2_z1"}
    assert "OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32" in body["walk_skill_ids"]
