"""Dashboard Go2 tip gate for ``/simple`` chat."""

from __future__ import annotations

import math

import httpx
import pytest
from openral_observability.dashboard import TelemetryStore, create_app
from openral_observability.dashboard._fall import (
    TIP_TILT_RAD,
    fallen_from_snapshot,
    qpos_is_fallen,
    tilt_off_vertical_wxyz,
)
from openral_observability.dashboard.cricket_session import overlay_cricket_ingest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status


def _upright_qpos() -> list[float]:
    return [0.0, 0.0, 0.33, 1.0, 0.0, 0.0, 0.0] + [0.1, 0.9, -1.8] * 4


def _pitched_qpos(*, radians: float) -> list[float]:
    half = radians / 2.0
    return [0.0, 0.0, 0.08, math.cos(half), 0.0, math.sin(half), 0.0] + [0.1, 0.9, -1.8] * 4


def _ingest_qpos(store: TelemetryStore, qpos: list[float]) -> None:
    qpos_values = [AnyValue(double_value=v) for v in qpos]
    span = Span(
        trace_id=b"\x21" * 16,
        span_id=b"\x21" * 8,
        name="hal.read_state",
        start_time_unix_nano=1,
        end_time_unix_nano=2,
        attributes=[
            KeyValue(key="openral.hal.robot.model", value=AnyValue(string_value="go2_z1")),
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
            KeyValue(key="openral.hal.nq", value=AnyValue(int_value=len(qpos))),
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


def test_identity_quat_is_upright() -> None:
    assert tilt_off_vertical_wxyz(1.0, 0.0, 0.0, 0.0) == 0.0
    assert qpos_is_fallen(_upright_qpos()) is False


def test_ninety_degree_pitch_is_fallen() -> None:
    assert qpos_is_fallen(_pitched_qpos(radians=math.pi / 2)) is True


def test_tip_gate_matches_mass_balance_radian() -> None:
    assert TIP_TILT_RAD == 1.0
    assert qpos_is_fallen(_pitched_qpos(radians=0.99)) is False
    assert qpos_is_fallen(_pitched_qpos(radians=1.01)) is True


def test_short_or_bad_qpos_is_not_fallen() -> None:
    assert qpos_is_fallen([0.0, 0.0, 0.33]) is False
    assert qpos_is_fallen("nope") is False
    assert qpos_is_fallen(None) is False


def test_fallen_from_snapshot_prefers_bool() -> None:
    assert fallen_from_snapshot({"fallen": True}) is True
    assert fallen_from_snapshot({"fallen": False, "topics": {}}) is False
    assert fallen_from_snapshot({}) is False
    assert (
        fallen_from_snapshot({"topics": {"robot_state": {"qpos": _pitched_qpos(radians=1.2)}}})
        is True
    )


def test_store_snapshot_and_qpos_frame_flag_a_tip() -> None:
    store = TelemetryStore()
    assert store.snapshot()["fallen"] is False
    _ingest_qpos(store, _upright_qpos())
    assert store.snapshot()["fallen"] is False
    assert store.qpos_frame() is not None
    assert store.qpos_frame()["fallen"] is False
    _ingest_qpos(store, _pitched_qpos(radians=1.2))
    assert store.snapshot()["fallen"] is True
    assert store.qpos_frame()["fallen"] is True


@pytest.mark.asyncio
async def test_api_state_and_qpos_expose_fallen() -> None:
    store = TelemetryStore()
    _ingest_qpos(store, _pitched_qpos(radians=math.pi / 2))
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        state = (await client.get("/api/state")).json()
        qpos = (await client.get("/api/qpos")).json()
    assert state["fallen"] is True
    assert qpos["fallen"] is True


def test_overlay_copies_cricket_fallen(monkeypatch: pytest.MonkeyPatch) -> None:
    import openral_observability.dashboard.cricket_session as cs

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        cs,
        "cricket_tunneled_state",
        lambda: {
            "last_ingest_ts": 10.0,
            "now_unix": 11.0,
            "identity": {"openral.hal.robot.model": "go2_z1"},
            "fallen": True,
        },
    )
    out = overlay_cricket_ingest({"last_ingest_ts": 0.0, "now_unix": 1.0, "identity": {}})
    assert out["fallen"] is True


def test_overlay_computes_fallen_from_old_cricket_qpos(monkeypatch: pytest.MonkeyPatch) -> None:
    import openral_observability.dashboard.cricket_session as cs

    monkeypatch.setenv("OPENRAL_CRICKET_ROLE", "laptop")
    monkeypatch.setattr(
        cs,
        "cricket_tunneled_state",
        lambda: {
            "last_ingest_ts": 10.0,
            "now_unix": 11.0,
            "identity": {"openral.hal.robot.model": "go2"},
            "topics": {"robot_state": {"qpos": _pitched_qpos(radians=1.2)}},
        },
    )
    out = overlay_cricket_ingest({"last_ingest_ts": 0.0, "now_unix": 1.0, "identity": {}})
    assert out["fallen"] is True
