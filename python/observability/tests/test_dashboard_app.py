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
import time
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
from opentelemetry.proto.common.v1.common_pb2 import (
    AnyValue,
    ArrayValue,
    InstrumentationScope,
    KeyValue,
)
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
    Status,
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
async def test_index_redirects_to_simple() -> None:
    """GET / does not start the classic root UI; it sends you to /simple."""
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/simple"
        simple = await client.get("/simple")
        assert simple.status_code == 200
        assert "OpenRAL · Simple".encode() in simple.content
        assert "OpenRAL · Live Dashboard".encode() not in simple.content
        assert b'id="demo-cricket-start"' not in simple.content


@pytest.mark.asyncio
async def test_simple_serves_html() -> None:
    """GET /simple is the only operator UI."""
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/simple")
        assert resp.status_code == 200
        assert "OpenRAL · Simple".encode() in resp.content
        assert "<title>OpenRAL · Simple</title>".encode() in resp.content
        assert b"/static/simple-ui/_next/" in resp.content
        assert b'data-slot="button"' in resp.content
        assert b"Start engine" in resp.content
        assert b"GO2 CHAT" in resp.content
        assert b"Ask for a walk or hop" in resp.content
        assert b"Operator dashboard" not in resp.content
        assert b"dashboard.js" not in resp.content
        assert b"simple.js" not in resp.content
        assert b"/static/simple-ui/assets/" not in resp.content


def test_simple_chat_bar_uses_json_render() -> None:
    """GET /simple has a right Go2 chat sidebar with json-render."""
    ui_root = Path(__file__).resolve().parents[1] / "simple_ui"
    pkg = (ui_root / "package.json").read_text(encoding="utf-8")
    app = (ui_root / "components" / "simple-play.tsx").read_text(encoding="utf-8")
    bar = (ui_root / "components" / "go2-chat-bar.tsx").read_text(encoding="utf-8")
    catalog = (ui_root / "lib" / "chat-catalog.ts").read_text(encoding="utf-8")
    registry = (ui_root / "lib" / "chat-registry.tsx").read_text(encoding="utf-8")

    assert '"@json-render/react"' in pkg
    assert '"@json-render/core"' in pkg
    assert '"streamdown"' in pkg
    assert "from '@/components/go2-chat-bar'" in app
    assert "<Go2ChatBar />" in app
    assert "lg:flex-row" in app
    assert app.find("<main") < app.find("<Go2ChatBar")
    assert 'id="go2-chat"' in bar
    assert 'id="go2-chat-input"' in bar
    assert 'id="go2-chat-send"' in bar
    assert "<aside" in bar
    assert "lg:w-80" in bar
    assert "lg:border-l" in bar
    assert "sticky bottom-0" not in bar
    assert "useChatUI" in bar
    assert "function chatApi()" in bar
    assert "`${window.location.origin}/api/chat`" in bar
    assert "from 'streamdown'" in bar
    assert "from '@json-render/react'" in bar
    assert "isAnimating=" in bar
    assert 'caret="block"' in bar
    assert "TextShimmer" in bar
    assert 'id="go2-chat-pulling"' in bar
    assert "pulling" in bar
    assert "waitingOnPull" in bar
    assert "StatusCard" in catalog
    assert "propose" in catalog
    assert "hydrateAcquirePropose" in bar
    assert "Ask for a walk or hop" in bar
    assert "UNIT_CHANGED_LINE" in bar
    assert "subscribeUnitChanged" in bar
    assert "FELL_LINE" in bar
    assert "subscribeFallen" in bar
    assert "withUnitNotices" in bar
    assert "defineRegistry" in registry
    assert "go2ChatRegistry" in registry
    assert "action: z.enum(['apply', 'adapt', 'stop'])" in catalog
    assert 'id={id}' in registry
    assert 'id = isAdapt ? \'chat-adapt\' : \'chat-apply\'' in registry
    assert "await onApply()" in registry
    assert "await onStop()" in registry
    assert "chatApplyPhase" in registry
    assert "APPLYING…" in registry
    assert "STANDING…" in registry
    assert "STOPPING…" in registry
    assert "subscribePlay" in registry
    assert "void onApply()" in registry
    assert "void onStop()" in registry
    shimmer = (ui_root / "components" / "ui" / "text-shimmer.tsx").read_text(
        encoding="utf-8"
    )
    css = (ui_root / "app" / "globals.css").read_text(encoding="utf-8")
    assert "export function TextShimmer" in shimmer
    assert "text-shimmer" in shimmer
    assert "@keyframes text-shimmer" in css
    assert "prefers-reduced-motion" in css


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
    assert _cancel_goal_succeeded("return_code: 2") is True  # specific id missing
    assert _cancel_goal_succeeded("return_code: 1") is True  # cancel-all, nothing cancelable
    assert _cancel_goal_succeeded("return_code: ERROR_REJECTED") is True
    assert _cancel_goal_succeeded("return_code=ERROR_NONE") is True
    assert _cancel_goal_succeeded("goals_canceling: []") is True
    assert _cancel_goal_succeeded("no return code here") is False
    assert _trigger_success("response:\n  success: True\n") is True
    assert _trigger_success("success=True") is True
    assert _trigger_success("success: false") is False


@pytest.mark.asyncio
async def test_ros2_cancel_call_ignores_cli_exit_on_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jazzy ``ros2 service call`` may exit 1 on ERROR_REJECTED; checker wins."""
    from openral_observability.dashboard.demo_controls import (
        _cancel_goal_succeeded,
        _ros2_service_call,
    )

    shim = tmp_path / "ros2"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "print('response:')\n"
        + "print('  return_code: 1')\n"
        + "raise SystemExit(1)\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
    ok, out = await _ros2_service_call(
        "/openral/execute_rskill/_action/cancel_goal",
        "action_msgs/srv/CancelGoal",
        "{goal_info: {}}",
        succeeded=_cancel_goal_succeeded,
    )
    assert ok is True
    assert "return_code: 1" in out


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
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
    yield log


@pytest.mark.asyncio
async def test_demo_stop_cancels_then_stands(
    monkeypatch: pytest.MonkeyPatch, ros2_demo_stop_shim: Path
) -> None:
    """Stop cancels ExecuteRskill (no e-stop) then snaps Hub home so Apply can re-run."""
    from openral_observability.dashboard import cricket_session as cs
    from openral_observability.dashboard import demo_controls

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2")
    monkeypatch.setattr(demo_controls, "_CANCEL_THEN_STAND_S", 0.0)
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
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
async def test_demo_stop_rejected_cancel_still_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel-all with nothing cancelable is ERROR_REJECTED — Stop still Hub-stands."""
    from openral_observability.dashboard import cricket_session as cs
    from openral_observability.dashboard import demo_controls

    calls: list[str] = []

    async def _fake_call(
        service: str,
        srv_type: str,
        args: str,
        *,
        succeeded: object | None = None,
    ) -> tuple[bool, str]:
        del srv_type, args
        calls.append(service)
        if "cancel_goal" in service:
            text = "response:\n  return_code: 1\n  goals_canceling: []\n"
            check = succeeded if callable(succeeded) else None
            ok = bool(check(text)) if check is not None else False
            return ok, text
        return True, "success=True"

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2")
    monkeypatch.setattr(demo_controls, "_CANCEL_THEN_STAND_S", 0.0)
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
    monkeypatch.setattr(demo_controls, "_ros2_service_call", _fake_call)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/stop")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["canceled"] is True
    assert body["action"] == "stop"
    assert any("cancel_goal" in item for item in calls)
    assert any("reset_to_pose" in item for item in calls)


@pytest.mark.asyncio
async def test_demo_stop_unparsed_cancel_still_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken CancelGoal dump must not OP_FAULT — Hub stand still runs."""
    from openral_observability.dashboard import cricket_session as cs
    from openral_observability.dashboard import demo_controls

    async def _fake_call(
        service: str,
        srv_type: str,
        args: str,
        *,
        succeeded: object | None = None,
    ) -> tuple[bool, str]:
        del srv_type, args, succeeded
        if "cancel_goal" in service:
            return False, "Failed to populate message from YAML"
        return True, "success=True"

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_ROBOT_ID", "go2")
    monkeypatch.setattr(demo_controls, "_CANCEL_THEN_STAND_S", 0.0)
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: True)
    monkeypatch.setattr(demo_controls, "_ros2_service_call", _fake_call)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/stop")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["canceled"] is False
    assert "did not confirm" in body["detail"]


@pytest.mark.asyncio
async def test_laptop_stop_graph_down_is_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dead graph: Stop 503s once and must not SSH CancelGoal or ResetToPose."""
    from openral_observability.dashboard import cricket_session as cs
    from openral_observability.dashboard import demo_controls

    calls: list[str] = []

    async def _boom(*args: object, **kwargs: object) -> tuple[bool, str]:
        calls.append(str(args[0]) if args else "call")
        return False, "should not run"

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    monkeypatch.setattr(demo_controls, "_ros2_service_call", _boom)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/stop")
    assert resp.status_code == 503, resp.text
    assert resp.json()["error"] == "cricket is disconnected"
    assert calls == []


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
    assert "OPENRAL_CRICKET_ROLE=host" in script
    assert "OPENRAL_CRICKET_IDLE_S" in script


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
    """Laptop /healthz never drops; poll waits for /api/config robot_id."""
    js = (
        Path(__file__).resolve().parents[1]
        / "src/openral_observability/dashboard/static/dashboard.js"
    )
    text = js.read_text(encoding="utf-8")
    load_fn = text[text.find("function wireDemoLoad") : text.find('wireDemoLoad("demo-go2")')]
    assert "sawGap" in load_fn
    assert "/api/config" in load_fn
    assert 'fetch("/healthz"' not in load_fn
    assert "DEMO_RELOAD_MAX_TRIES = 90" in load_fn
    assert "tries > 45" not in load_fn


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
    assert "savedIsWalk" not in text
    assert "isArmReadySkillId" in text
    assert "if (preferWalk && walkId && (!keep || isArmReadySkillId(keep))) selectEl.value = walkId;" in text
    assert 'demoPost("/api/demo/walk", { skill_id: skillId })' in text
    assert "switching skill — stopping the current one" in text
    assert 'rid === "go2" || rid === "go2_z1"' in text
    assert "sessionStorage.setItem(DEMO_ROBOT_KEY, rid)" in text
    assert 'if (rid && !demoRobot())' not in text
    assert "1 · Load the unit" in text
    assert "Nothing is loaded. Pick Bare Go2 or Go2 + Z1" in text


def test_simple_js_engine_robot_calibrate_then_apply() -> None:
    """Simple page: engine → UNIT + skill dropdowns; Apply lives in chat.

    Header primary is Start / Load / Stop only. Load auto-stands so
    Apply is ready. Footer RESET is ``POST /api/demo/recalibrate``.
    Chat Apply stands first only if the dog is not already stood.
    Never auto-walk. Abort is Hub stand, not End Cricket.
    """
    ui_root = Path(__file__).resolve().parents[1] / "simple_ui"
    pkg = (ui_root / "package.json").read_text(encoding="utf-8")
    components = (ui_root / "components.json").read_text(encoding="utf-8")
    js = (ui_root / "lib" / "play.ts").read_text(encoding="utf-8")
    app = (ui_root / "components" / "simple-play.tsx").read_text(encoding="utf-8")
    tile = (ui_root / "components" / "camera-tile.tsx").read_text(encoding="utf-8")
    css = (ui_root / "app" / "globals.css").read_text(encoding="utf-8")
    button = (ui_root / "components" / "ui" / "button.tsx").read_text(encoding="utf-8")
    select = (ui_root / "components" / "ui" / "select.tsx").read_text(encoding="utf-8")
    layout = (ui_root / "app" / "layout.tsx").read_text(encoding="utf-8")
    go2 = ui_root / "public" / "robots" / "go2.svg"
    z1 = ui_root / "public" / "robots" / "go2-z1.svg"

    assert '"next": "16.3.3"' in pkg
    assert '"react": "19.2.6"' in pkg
    assert '"geist"' in pkg
    assert '"tw-animate-css"' in pkg
    assert '"@tailwindcss/postcss"' in pkg
    assert '"vite"' not in pkg
    assert '"style": "new-york"' in components
    assert '"rsc": true' in components
    assert "geist/font/sans" in layout
    assert "@import 'tw-animate-css'" in css
    assert go2.is_file()
    assert z1.is_file()

    assert "/api/demo/cricket/start" in js
    assert "Start engine" in app
    assert "Starting…" in app
    assert "Loader2" in app
    assert "animate-spin" in app
    assert "Operator dashboard" not in app
    assert "id: 'go2'" in js
    assert "id: 'go2_z1'" in js
    assert "/static/simple-ui/robots/go2.svg" in js
    assert "/static/simple-ui/robots/go2-z1.svg" in js
    assert 'loadPreset' not in js
    assert 'demoPost("/api/demo/load"' in js or "demoPost('/api/demo/load'" in js
    assert "{ preset }" in js or "{ preset: preset }" in js
    assert "/api/demo/recalibrate" in js
    assert "RECAL_WAITS_MS" not in js
    cal_fn = js[js.find("async function calibrate()") : js.find("async function applySkill")]
    assert cal_fn.count("demoPost('/api/demo/recalibrate')") == 1
    assert "for (const waitMs" not in cal_fn
    assert "RESETTING…" in app
    assert "STANDING…" not in app
    assert "Stopping…" in app
    assert "ctaBusy" in app
    assert "/api/demo/walk" in js
    assert "/api/demo/stop" in js
    assert "Never auto-walk" in js
    assert "WALK_MS" not in js
    assert "await walkThenStop()" not in js

    assert "primaryAction" in js
    assert "step === 'calibrate'" in js
    assert "step === 'apply'" in js
    assert "return 'calibrate'" not in js
    assert "return 'stop'" in js
    assert "id=\"reset\"" in app
    assert "id=\"stand\"" not in app
    assert "RESET" in app
    assert "STAND" not in app
    assert "calibrate: 'Calibrate'" not in app
    assert "apply: 'Apply'" not in app
    save_cal = js.find("savePlay('calibrate'")
    save_apply = js.find("savePlay('apply'")
    assert save_cal != -1 and save_apply != -1

    assert "is-streaming" in tile
    assert 'src="/api/camera/top/stream"' in app
    assert 'src="/api/camera/front/stream"' not in app
    assert "img.onload" not in js
    assert "img.onload" not in app
    assert ".camera.has-mjpeg .camera-placeholder" in css
    assert ".camera:has(img[src]):not(.has-no-signal) .camera-placeholder" in css
    assert ".camera:has(canvas.camera-stream)" not in css
    assert "from '@/components/ui/button'" in app
    assert "from '@/components/ui/badge'" in app
    assert "from '@/components/ui/select'" in app
    assert 'data-slot="button"' in button
    assert 'data-slot="select"' in select
    assert 'id="unit-select"' in app
    assert 'id="skill-select"' in app
    assert "Acquire/rskill-rsl-rl-onnx-go2-velocity-flat" in js
    assert "OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32" in js
    assert "OpenRAL/rskill-zero-go2_z1-arm_ready-fp32" in js
    assert "label: 'move'" in js
    assert "label: 'hop'" in js
    assert "label: 'arm'" in js
    assert "export function skillsForRobot" in js
    assert "export function clampSkillForRobot" in js
    assert "export function copyFor" in js
    assert "export function isHopSkillId" in js
    assert "export function isArmReadySkillId" in js
    assert "if (!robot || !offered) return []" in js
    assert "export const DEFAULT_SKILL: SkillId = ''" in js
    assert "export function applyAcquirePropose" in js
    assert "export async function hydrateAcquirePropose" in js
    assert "export function subscribePlay" in js
    assert "export function chatApplyPhase" in js
    assert "export async function onStop" in js
    assert "embodimentTags: ['go2_z1']" in js
    assert "offeredSkills" in app
    assert "skillsForRobot(robot, skill)" in app
    assert "no skill yet — ask chat" in app
    assert "copyFor(step, skill, robot)" in app
    assert "export function chooseSkill" in js
    assert "export function isWalkSkillId" in js
    apply_fn = js[js.find("async function applySkill") : js.find("async function watchSkill")]
    assert "velocity_commands" in apply_fn
    assert "demoPost('/api/demo/walk', walkBody)" in apply_fn
    assert "'/api/skill/execute'" in apply_fn
    assert "goal_params_json" in apply_fn
    assert "await applyWalk()" not in js

    abort_at = js.find("async function stopSkill")
    assert abort_at != -1
    abort_fn = js[abort_at : abort_at + 900]
    assert "/api/demo/stop" in abort_fn
    assert "data.accepted" in abort_fn
    assert "/api/demo/cricket/end" not in js
    assert "PLAY_KEY = 'openral.simple.play'" in js
    assert "skill: sid" in js
    assert "function persistPlay" in js
    assert "export function reconcileRestoredPlay" in js
    assert "skillRunning" in js
    assert "graphRunning" in js
    assert "play.step === 'running' ? 'apply'" not in js
    assert "paint(play.step," not in js
    assert "function fail(" in js
    assert "export function messageFromBody" in js
    assert "export function unreachableMessage" in js
    assert "WRITE_CONTROLS_MSG" in js
    assert "UNREACHABLE_MSG" in js
    assert "write-controls disabled; set OPENRAL_DASHBOARD_WRITE_CONTROLS=1" in js
    assert "can't reach the dashboard" in js
    assert "export async function onCalibrate" in js
    assert "export async function onApply" in js
    assert "export async function onStop" in js
    assert "export function canCalibrate" in js
    assert "export function canApply" in js
    assert 'id="primary"' in app
    assert 'id="reset"' in app
    assert 'id="stand"' not in app
    assert 'id="calibrate"' not in app
    assert 'id="apply"' not in app
    assert "PRIMARY_LABEL" in app
    assert "headerAction" in app
    assert "stop: 'Stop'" in app
    assert "const needsStand = snapshot.step !== 'apply'" in js
    assert "await calibrate()" in js[js.find("export async function onApply") :]
    reload_fn = js[
        js.find("async function reloadAfterLoad") : js.find("function startErrorFrom")
    ]
    finish_fn = js[
        js.find("async function finishLoad") : js.find("export async function onCalibrate")
    ]
    assert "await calibrate()" in reload_fn
    assert "await calibrate()" in finish_fn
    assert "Stand if tipped" not in js
    assert "Reset if tipped" in js
    assert "fail(recoverStep(action)" not in js
    assert "fail('choose'" in js
    assert "fail('running'" in js
    assert "savePlay('error'" not in js
    assert 'data-slot="alert"' in (ui_root / "components" / "ui" / "alert.tsx").read_text(
        encoding="utf-8"
    )
    assert "from '@/components/ui/alert'" in app
    assert 'variant="destructive"' in app


def test_simple_unit_label_follows_live_occupant() -> None:
    """Empty /simple says Load the unit; UNIT follows cricket identity, not Bare Go2."""
    ui_root = Path(__file__).resolve().parents[1] / "simple_ui"
    js = (ui_root / "lib" / "play.ts").read_text(encoding="utf-8")
    app = (ui_root / "components" / "simple-play.tsx").read_text(encoding="utf-8")
    html = (
        Path(__file__).resolve().parents[1]
        / "src/openral_observability/dashboard/static/index.html"
    ).read_text(encoding="utf-8")

    assert "export function occupantRobot" in js
    assert "export function robotLabel" in js
    assert "export function parseRobotId" in js
    assert "export const UNIT_CHANGED_LINE = 'unit changed.'" in js
    assert "export const FELL_LINE =" in js
    assert "this skill needs retraining or finetuning" in js
    assert "export function shouldAnnounceUnitChange" in js
    assert "return Boolean(from && to && from !== to)" in js
    assert "noteUnitChanged(liveId || snapshot.robot, preset)" in js
    assert "export function watchFallen" in js
    assert "watchFallen()" in js
    assert "export function noteFallen" in js
    choose = js[js.find("export async function chooseRobot") : js.find("async function calibrate")]
    assert choose.find("this robot is already loaded") < choose.find("noteUnitChanged")
    assert "if (opts.graphRunning && opts.live) return opts.live" in js
    occupant = js[js.find("export function occupantRobot") : js.find("export function loadPlay")]
    assert "if (opts.loading && opts.stored) return opts.stored" in occupant
    assert "opts.live !== opts.stored" not in occupant
    assert "return opts.stored" in occupant
    assert "return ''" in occupant
    reconcile = js[
        js.find("export function reconcileRestoredPlay") : js.find("export function chooseSkill")
    ]
    assert "occupantRobot({" in reconcile
    assert "(stored && stored.robot) || opts.liveRobot" not in reconcile
    assert "return { step: 'idle', robot: '' }" in reconcile
    assert "stored.step === 'calibrate'" in reconcile
    assert "return { step: 'apply', robot }" in reconcile
    assert "stored.step === 'calibrate' || stored.step === 'loading'" not in reconcile
    assert "Load the unit" in js
    assert "Nothing is loaded. Pick Bare Go2 or Go2 + Z1 (~30–90s)." in js
    assert "loading ' + preset" not in js
    assert "loading ' + robotLabel(preset)" in js
    finish = js[js.find("async function finishLoad") : js.find("export async function onCalibrate")]
    assert "waitForOccupant(robot)" in finish
    assert "await calibrate()" in finish
    assert "waiting for healthz" not in finish
    assert "reloadAfterLoad(preset)" in js
    assert "location.reload()" not in js[js.find("async function reloadAfterLoad") : js.find("async function finishLoad")]
    boot = js[js.find("export function boot()") : js.find("async function probeGraphThenMaybeChoose")]
    assert "paint('choose', { robot: '', skill, status: '', kind: '' })" in boot
    assert "paint('idle', { robot: '', skill, status: '', kind: '' })" in boot
    assert "load: 'Load the unit'" in app
    assert 'placeholder="Load the unit"' in app
    assert "primaryAction(step, robot)" in app
    assert "1 · Load the unit" in html
    assert "Nothing is loaded. Pick Bare Go2 or Go2 + Z1" in html
    assert "1 · Choose robot" not in html


def test_simple_js_conn_pill_matches_operator_dashboard() -> None:
    """GET /simple header conn pill is the same 4-state ingest-age contract as `/`."""
    ui_root = Path(__file__).resolve().parents[1] / "simple_ui"
    dash = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "openral_observability"
        / "dashboard"
        / "static"
        / "dashboard.js"
    ).read_text(encoding="utf-8")
    conn = (ui_root / "lib" / "conn.ts").read_text(encoding="utf-8")
    indicator = (ui_root / "components" / "conn-indicator.tsx").read_text(encoding="utf-8")
    app = (ui_root / "components" / "simple-play.tsx").read_text(encoding="utf-8")
    css = (ui_root / "app" / "globals.css").read_text(encoding="utf-8")

    assert "<ConnIndicator" in app
    assert "from '@/components/conn-indicator'" in app
    assert app.find("<header") < app.find("<Mark")
    assert app.find("<header") < app.find("<ConnIndicator")
    assert app.find("<header") < app.find('id="live-band"')
    header = app[app.find("<header") : app.find("</header>")]
    assert "items-center justify-between" in header
    assert "w-full" in header
    assert "max-w-[22rem]" not in header
    assert "items-start" in header
    assert "<Mark" in header
    assert "<ConnIndicator" in header
    assert app.find('id="primary"') < app.find('id="live-band"')
    assert 'size="sm"' in app
    assert "text-left" in app
    assert "kind !== 'ok'" in app
    assert "TextShimmer" in app
    assert "No skill is applied" not in app

    assert "export function classifyConn" in conn
    assert "CONN_LIVE_S = 10" in conn
    assert "CONN_DEAD_S = 60" in conn
    assert "waiting…" in conn
    assert "label: 'live'" in conn
    assert "stale (" in conn
    assert "dead (" in conn
    assert "reconnecting…" in conn
    assert "last_ingest_ts" in conn
    assert "now_unix" in conn
    assert "now_unix - last_ingest_ts" in conn

    assert 'new EventSource("/api/stream")' in dash
    assert "new EventSource('/api/stream')" in indicator
    assert "CONN_RETRY_MS" in indicator
    assert "CONN_POLL_MS" in indicator
    assert "fetch('/api/state'" in indicator
    assert "classifyConn({ unreachable: true })" in indicator
    assert 'id="conn"' in indicator
    assert 'id="conn-label"' in indicator
    assert "TextShimmer" in indicator
    assert "conn.kind === 'wait'" in indicator
    assert 'className="conn-dot"' in indicator
    assert 'data-kind={conn.kind}' in indicator

    assert "dt < 10" in dash
    assert "dt < 60" in dash
    assert 'textContent = "waiting…"' in dash
    assert 'textContent = "live"' in dash
    assert "reconnecting…" in dash

    assert ".conn-dot" in css
    assert "border-radius: 50%" in css
    assert "conn-blink" in css
    assert "1.4s infinite" in css


def test_simple_js_engine_cameras_and_start_errors() -> None:
    """Engine screens hide pickers; top camera fills leftover viewport."""
    ui_root = Path(__file__).resolve().parents[1] / "simple_ui"
    js = (ui_root / "lib" / "play.ts").read_text(encoding="utf-8")
    app = (ui_root / "components" / "simple-play.tsx").read_text(encoding="utf-8")

    tile = (ui_root / "components" / "camera-tile.tsx").read_text(encoding="utf-8")
    css = (ui_root / "app" / "globals.css").read_text(encoding="utf-8")

    assert "LIVE_STEPS" in js
    assert "showLive" in app
    assert "CAM_TOP" in app
    assert "CAM_FRONT" not in app
    # Live order: compact primary under OP_CAL/conn, then UNIT + skill, top, LIVE.
    assert app.find("UNIT") < app.find("CAM_TOP")
    assert app.find('id="unit-select"') < app.find("CAM_TOP")
    assert app.find('id="skill-select"') < app.find("CAM_TOP")
    assert app.find("CAM_TOP") < app.find('id="live-pill"')
    assert app.find('src="/api/camera/top/stream"') > app.find('id="live-band"')
    assert 'src="/api/camera/front/stream"' not in app
    band = app[app.find('id="live-band"') : app.find('id="live-pill"')]
    assert "max-w-[22rem]" not in band
    assert "w-full" in band
    assert "grid-cols-1" in band
    assert "flex-1" in band
    cam_row = app[app.find('id="camera-top"') : app.find('id="live-pill"')]
    assert "grid-cols-2" not in cam_row
    assert "aspect-square" not in cam_row
    assert 'className="absolute inset-0"' in cam_row
    assert "RobotCard" not in app
    assert "<Mark>OPENRAL</Mark>" not in app
    assert "<Mark>SIMPLE</Mark>" not in app
    assert "powered by openral" in app
    assert "shrink-0" in app
    assert "h-dvh" in app
    assert "overflow-hidden" in app
    assert "waiting for camera" not in app
    assert "waiting for camera" not in tile
    assert "connecting" in tile
    assert "TextShimmer" not in tile
    assert "no signal" in tile
    assert "has-no-signal" in tile
    assert "camera-still" in tile
    assert "onError" not in tile
    assert "onLoad" not in tile
    assert "<img className=\"camera-stream\"" not in tile
    assert "consumeMjpegStream" in tile
    assert "createLatestFramePainter" in tile
    assert "paintJpegToCanvas" in tile
    mjpeg = (ui_root / "lib" / "mjpeg.ts").read_text(encoding="utf-8")
    assert "function splitMjpegBuffer" in mjpeg
    assert "function ownedBytes" in mjpeg
    assert "createImageBitmap" in mjpeg
    assert "frames[frames.length - 1]" in mjpeg
    assert "content-length" in mjpeg
    assert "fetch('/api/demo/cricket'" not in tile
    assert 'fetch("/api/demo/cricket"' not in tile
    assert "graph_running" not in tile
    assert "start_in_progress" not in tile
    assert "latest.jpg" in tile
    assert "204" in tile

    assert "has-no-signal" in css
    assert "camera-still" in css
    assert ":has(img[src])" in css
    assert ".camera.has-mjpeg" in css
    assert "min-height: 12rem" in css
    assert "object-fit: cover" in css
    assert ".hmi-mark" in css
    assert "background: transparent" in css
    assert "color: #fff" in css
    frame = (ui_root / "components" / "hmi-frame.tsx").read_text(encoding="utf-8")
    assert "hmi-mark hmi-mark-tl" in frame
    assert "bg-transparent" in frame
    assert "text-white" in frame
    assert "export function classifyStartError" in js
    assert "function startErrorFrom" in js
    assert "credit|insufficient|quota|billing" in js
    assert "not on path|source the workspace" in js
    assert "timed out calling|reset_to_pose failed" in js
    assert "cricket is disconnected" in js
    assert "starting cricket graph… (~30-90s)" in js
    assert "if (postedError)" in js
    start_fn = js[js.find("async function startCricket") : js.find("async function finishLoad")]
    assert start_fn.index("if (resp.ok && data.already_running)") < start_fn.index(
        "const postedError"
    )
    poll_loop = start_fn.split("if (resp.status === 202)")[1]
    assert poll_loop.index("if (st.graph_running)") < poll_loop.index("const pollError")
    assert "kind: 'ok'" not in start_fn.split("if (resp.status === 202)")[1].split("if (st.graph_running)")[0]
    assert "startInFlight" in js
    assert "probeGraphThenMaybeChoose" in js
    assert "async function watchIdleUntilGraph" in js
    assert "async function ingestLive" in js
    assert "void watchIdleUntilGraph()" in js
    assert "if (!busy && snapshot.step === 'idle') return" not in js
    assert "fail('idle'" in js
    assert "Starting…" in app
    assert "RESETTING…" in app
    assert "STANDING…" not in app
    assert "Loader2" in app
    assert "engineScreen" in app
    assert "COPY.idle" in app
    assert 'id="status-slot"' in app
    assert "min-h-[1.5rem]" in app


def test_dashboard_js_mjpeg_is_streaming_without_img_load() -> None:
    """Opaque placeholder must drop when the stream URL is set, not on img.onload.

    Multipart MJPEG often never fires load; that left tiles on
    "waiting for camera" while /api/camera/top/stream was live.
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
    assert 'src="/api/camera/front/stream"' not in html
    assert 'src="/api/camera/top/stream"' in html
    assert 'class="camera-stream"' in html
    assert 'class="camera-still"' in html
    assert "ensureCameraPixels" in js
    assert "/api/camera/" in js and "latest.jpg" in js
    assert "mjpegHasPixels" in js
    assert "has-mjpeg" in js
    assert "still.src = url" in js
    assert "img.src = url" not in js
    assert "if (mjpegHasPixels(img)) return;" in js
    assert "window.setInterval(kick, 1500)" in js
    assert "window.setInterval(kick, 300)" not in js
    assert 'fetch("/api/state", { cache: "no-store" })' not in js
    assert ".camera.has-mjpeg img.camera-still" in css


def test_go2_z1_embodiment_tags_intersect_go2_walk_skill() -> None:
    """Loader gate is tag intersection: go2 walk skill fits go2_z1."""
    from openral_core.schemas import RSkillManifest
    from openral_observability.dashboard.demo_controls import robot_embodiment_tags

    repo = Path(__file__).resolve().parents[3]
    walk = RSkillManifest.from_yaml(
        str(repo / "rskills" / "rsl-rl-onnx-go2-velocity-flat" / "rskill.yaml")
    )
    hop = RSkillManifest.from_yaml(
        str(repo / "rskills" / "rsl-rl-onnx-go2-spring-jump" / "rskill.yaml")
    )
    arm = RSkillManifest.from_yaml(
        str(repo / "rskills" / "rskill-zero-go2_z1-arm_ready-fp32" / "rskill.yaml")
    )
    go2 = set(robot_embodiment_tags("go2"))
    z1 = set(robot_embodiment_tags("go2_z1"))

    def fits(manifest: RSkillManifest, tags: set[str]) -> bool:
        return bool(set(manifest.embodiment_tags) & tags)

    assert "go2" in go2
    assert "go2_z1" not in go2
    assert "go2" in z1
    assert "go2_z1" in z1
    assert fits(walk, go2) and fits(walk, z1)
    assert fits(hop, go2) and fits(hop, z1)
    assert not fits(arm, go2)
    assert fits(arm, z1)


def test_is_walk_skill_id_matches_intree_and_hub() -> None:
    """Apply routes the rsl-rl walk skill through walk_response, not a second API."""
    from openral_observability.dashboard.demo_controls import is_walk_skill_id

    assert is_walk_skill_id("OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32")
    assert is_walk_skill_id("Acquire/rskill-rsl-rl-onnx-go2-velocity-flat")
    assert is_walk_skill_id("rsl-rl-onnx-go2-velocity-flat")
    assert not is_walk_skill_id("OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32")
    assert not is_walk_skill_id("OpenRAL/rskill-zero-go2-hop-fp32")
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
    assert walk_skill_dispatch_ids("OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32")[0] == acquire


@pytest.mark.asyncio
async def test_stand_response_passes_estop_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recalibrate must clear the runner latch via EstopPublisher, not shell-out alone."""
    from fastapi.responses import JSONResponse

    from openral_observability.dashboard import demo_controls

    seen: list[object] = []

    class _FakeEstop:
        available = True

    async def _fake_reset(estop: object = None) -> JSONResponse:
        seen.append(estop)
        return JSONResponse({"status": "ok", "accepted": True}, status_code=200)

    async def _fake_home() -> tuple[str, None]:
        return "go2", None

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setattr(
        "openral_observability.dashboard.app._estop_reset_response",
        _fake_reset,
    )
    monkeypatch.setattr(demo_controls, "_reset_to_home_pose", _fake_home)
    estop = _FakeEstop()
    resp = await demo_controls.stand_response(estop=estop)
    assert resp.status_code == 200
    assert seen == [estop]


def test_go2_z1_recalibrate_pose_is_arm_ready() -> None:
    """Recalibrate must park the Z1 at ARM_READY so Walk hold-snaps that pose."""
    from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY
    from openral_observability.dashboard.demo_controls import _HOME_POSE_BY_ROBOT

    expected = (*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY)
    assert _HOME_POSE_BY_ROBOT["go2_z1"] == expected
    assert _HOME_POSE_BY_ROBOT["go2"] == tuple(GO2_HOME_JOINT_TARGETS)


def test_classic_page_hides_run_strip_and_offers_apply_skill() -> None:
    """Retired classic HTML (not served at /) is one Apply + skill picker."""
    html = (
        Path(__file__).resolve().parents[1]
        / "src/openral_observability/dashboard/static/index.html"
    ).read_text(encoding="utf-8")
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


def test_mjpeg_part_bytes_frames_jpeg() -> None:
    import base64

    from openral_observability.dashboard.app import _mjpeg_part, _mjpeg_part_bytes

    jpeg = b"\xff\xd8\xff\xe0raw\xff\xd9"
    part = _mjpeg_part_bytes(jpeg)
    assert b"Content-Type: image/jpeg" in part
    assert jpeg in part
    assert _mjpeg_part(base64.b64encode(jpeg).decode("ascii")) == part


def test_mjpeg_canvas_player_splits_content_length_parts() -> None:
    """Wire format the /simple canvas player parses (lib/mjpeg.ts)."""
    import re

    from openral_observability.dashboard.app import _mjpeg_part_bytes

    first = b"\xff\xd8\x00\xff\xd9"
    second = b"\xff\xd8\x01\xff\xd9"
    buf = _mjpeg_part_bytes(first) + _mjpeg_part_bytes(second)
    frames: list[bytes] = []
    offset = 0
    while True:
        boundary = buf.find(b"--frame", offset)
        if boundary < 0:
            break
        headers_end = buf.find(b"\r\n\r\n", boundary)
        assert headers_end > 0
        header = buf[boundary:headers_end].decode("ascii")
        match = re.search(r"Content-Length:\s*(\d+)", header, re.I)
        assert match is not None
        size = int(match.group(1))
        body_start = headers_end + 4
        frames.append(buf[body_start : body_start + size])
        offset = body_start + size
    assert frames == [first, second]


def test_mjpeg_should_emit_heartbeats_identical_thumbs() -> None:
    from openral_observability.dashboard.app import (
        _MJPEG_HEARTBEAT_S,
        _mjpeg_should_emit,
    )

    assert _mjpeg_should_emit("a", None, elapsed_s=0.0) is True
    assert _mjpeg_should_emit("a", "a", elapsed_s=0.0) is False
    assert _mjpeg_should_emit("a", "a", elapsed_s=_MJPEG_HEARTBEAT_S) is True
    assert _mjpeg_should_emit("b", "a", elapsed_s=0.0) is True
    assert _mjpeg_should_emit(None, "a", elapsed_s=1.0) is False


@pytest.mark.asyncio
async def test_camera_latest_jpg_returns_jpeg(
    _otlp_camera_payload: Callable[[str, str], bytes],
) -> None:
    import base64

    store = TelemetryStore()
    app = create_app(store)
    jpeg = b"\xff\xd8\xff\xe0jpegbytes\xff\xd9"
    thumb_b64 = base64.b64encode(jpeg).decode("ascii")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        empty = await client.get("/api/camera/top/latest.jpg")
        assert empty.status_code == 204
        await client.post("/v1/traces", content=_otlp_camera_payload("wrist", thumb_b64))
        resp = await client.get("/api/camera/wrist/latest.jpg")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/jpeg")
        assert resp.content == jpeg
        missing = await client.get("/api/camera/nope/latest.jpg")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_camera_stream_unknown_source_404() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/camera/nope/stream")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_empty_store_still_exposes_go2_hero_cameras() -> None:
    """WAITING with no OTLP still advertises top (3/4 twin)."""
    from openral_observability.dashboard.app import (
        cricket_camera_latest_url,
        cricket_camera_stream_url,
    )
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
    assert "front" not in cameras
    assert cameras["top"]["role"] == "side"
    assert "thumbnail_jpeg_b64" not in cameras["top"]
    if on_cricket_host():
        assert cricket_camera_stream_url("top") is None
        assert cricket_camera_latest_url("top") is None
    else:
        assert cricket_camera_stream_url("top") == (
            f"http://127.0.0.1:{DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT}/api/camera/top/stream"
        )
        assert cricket_camera_latest_url("top") == (
            f"http://127.0.0.1:{DEFAULT_CRICKET_DASHBOARD_LOCAL_PORT}/api/camera/top/latest.jpg"
        )


@pytest.mark.asyncio
async def test_laptop_latest_jpg_uses_cricket_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openral_observability.dashboard import app as app_mod

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    jpeg = b"\xff\xd8\xff\xe0proxied\xff\xd9"

    async def _fake_proxy(source: str) -> bytes | None:
        return jpeg if source == "top" else None

    monkeypatch.setattr(app_mod, "_proxied_cricket_latest_jpeg", _fake_proxy)
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/camera/top/latest.jpg")
        assert resp.status_code == 200
        assert resp.content == jpeg
        missing = await client.get("/api/camera/nope/latest.jpg")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_laptop_latest_jpg_prefers_state_thumb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openral_observability.dashboard import app as app_mod

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    jpeg = b"\xff\xd8\xff\xe0state\xff\xd9"
    monkeypatch.setattr(
        app_mod, "_cricket_state_thumb_jpeg", lambda source: jpeg if source == "top" else None
    )

    async def _no_http(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("state thumb must win before cricket /latest.jpg")

    monkeypatch.setattr(app_mod.httpx, "AsyncClient", _no_http)
    got = await app_mod._proxied_cricket_latest_jpeg("top")
    assert got == jpeg


@pytest.mark.asyncio
async def test_laptop_config_robot_id_from_cricket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.delenv("OPENRAL_ROBOT_ID", raising=False)
    monkeypatch.setattr(
        "openral_observability.dashboard.cricket_session.cricket_live_robot_id",
        lambda: "go2",
    )
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        cfg = (await client.get("/api/config")).json()
    assert cfg["robot_id"] == "go2"


@pytest.mark.asyncio
async def test_laptop_state_overlays_cricket_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        "openral_observability.dashboard.cricket_session.overlay_cricket_ingest",
        lambda snap, **_kw: {
            **snap,
            "last_ingest_ts": 123.0,
            "now_unix": 124.0,
            "identity": {"openral.hal.robot.model": "go2"},
        },
    )
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        state = (await client.get("/api/state")).json()
    assert state["last_ingest_ts"] == 123.0
    assert state["now_unix"] == 124.0
    assert state["identity"]["openral.hal.robot.model"] == "go2"


@pytest.mark.asyncio
async def test_api_qpos_204_until_first_sample() -> None:
    store = TelemetryStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        empty = await client.get("/api/qpos")
        assert empty.status_code == 204


@pytest.mark.asyncio
async def test_api_qpos_returns_go2_width_vector() -> None:
    store = TelemetryStore()
    qpos = [0.0, 0.0, 0.33, 1.0, 0.0, 0.0, 0.0] + [0.01 * i for i in range(12)]
    qpos_values = [AnyValue(double_value=v) for v in qpos]
    now = time.time_ns()
    span = Span(
        trace_id=b"\x11" * 16,
        span_id=b"\x11" * 8,
        name="hal.read_state",
        start_time_unix_nano=now,
        end_time_unix_nano=now + 1_000_000,
        attributes=[
            KeyValue(key="openral.hal.robot.model", value=AnyValue(string_value="go2")),
            KeyValue(
                key="openral.hal.joint.names",
                value=AnyValue(
                    array_value=ArrayValue(values=[AnyValue(string_value="FL_hip_joint")])
                ),
            ),
            KeyValue(
                key="openral.hal.joint.positions",
                value=AnyValue(array_value=ArrayValue(values=[AnyValue(double_value=0.1)])),
            ),
            KeyValue(
                key="openral.hal.qpos",
                value=AnyValue(array_value=ArrayValue(values=qpos_values)),
            ),
            KeyValue(key="openral.hal.nq", value=AnyValue(int_value=19)),
        ],
        status=Status(code=0),
    )
    store.ingest_spans(
        [
            ResourceSpans(
                resource=Resource(
                    attributes=[KeyValue(key="service.name", value=AnyValue(string_value="ral"))]
                ),
                scope_spans=[ScopeSpans(spans=[span])],
            )
        ]
    )
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/qpos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nq"] == 19
    assert body["robot_id"] == "go2"
    assert body["qpos"] == qpos
    assert body["age_ms"] is not None
    assert body["fallen"] is False


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
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
    monkeypatch.setenv("PATH", str(tmp_path))  # empty PATH → shutil.which("ros2") is None
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 503
    assert "not on PATH" in resp.json()["error"]


@pytest.mark.asyncio
async def test_laptop_recalibrate_graph_down_is_disconnected_not_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Laptop Calibrate must not ask the operator to source local ros2."""
    from openral_observability.dashboard import cricket_session as cs

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/recalibrate")
    assert resp.status_code == 503, resp.text
    err = resp.json()["error"]
    assert "not on PATH" not in err
    assert "source the workspace" not in err
    assert "disconnected" in err.lower()


@pytest.mark.asyncio
async def test_recalibrate_disconnected_does_not_retry_reset_to_pose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One POST /api/demo/recalibrate; dead graph must not SSH ResetToPose."""
    from openral_observability.dashboard import cricket_session as cs
    from openral_observability.dashboard import demo_controls

    calls: list[str] = []

    async def boom(*args: object, **kwargs: object) -> tuple[bool, str]:
        calls.append(str(args[0]) if args else "call")
        return False, "should not run"

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    monkeypatch.setattr(demo_controls, "_ros2_service_call", boom)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/demo/recalibrate")
    assert resp.status_code == 503, resp.text
    assert resp.json()["error"] == "cricket is disconnected"
    assert calls == []


@pytest.mark.asyncio
async def test_laptop_skill_execute_graph_down_is_disconnected_not_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openral_observability.dashboard import cricket_session as cs

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(cs, "cricket_graph_running", lambda: False)
    monkeypatch.setattr(cs, "get_watch", lambda: None)
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/api/skill/execute", json={"skill_id": "openral/skill-pick"})
    assert resp.status_code == 503, resp.text
    err = resp.json()["error"]
    assert "not on PATH" not in err
    assert "source the workspace" not in err
    assert "disconnected" in err.lower()


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
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
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
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
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
    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "host")
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
