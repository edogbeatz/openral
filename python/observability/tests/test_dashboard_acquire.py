"""Acquire probe/ask on ``POST /api/chat`` — fake HTTP at the network boundary."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.responses import JSONResponse
from openral_observability.dashboard import TelemetryStore, create_app
from openral_observability.dashboard.acquire_client import (
    HOP_EXECUTE_ID,
    HOP_SEED_ID,
    WALK_EXECUTE_ID,
    WALK_SEED_ID,
    AcquireClient,
    classify_acquire,
    classify_reply,
    client_from_env,
    parse_intent,
    velocity_for_walk_command,
)

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from fakes.acquire_api import WALK_FORK, fake_acquire_app  # noqa: E402


@pytest.fixture
def openral_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install an ``openral`` shim so a leaked prompt publish is visible."""
    log = tmp_path / "openral_calls.txt"
    shim = tmp_path / "openral"
    shim.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, sys, pathlib\n"
        + f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    yield log


def _shim_wrote(log: Path) -> bool:
    return log.is_file()


def _wire(
    occupant: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: TelemetryStore | None = None,
) -> tuple[httpx.AsyncClient, object, TelemetryStore]:
    monkeypatch.setattr(
        "openral_observability.dashboard.chat.occupant_robot_id",
        lambda env=None: occupant,
    )
    fake = fake_acquire_app()
    acquire = AcquireClient(
        base_url="http://acquire.test",
        transport=httpx.ASGITransport(app=fake),
    )
    store = store or TelemetryStore()
    app = create_app(store)
    app.state.acquire_client = acquire
    return (
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"),
        fake,
        store,
    )


def test_parse_intent_and_reply() -> None:
    walk = parse_intent("walk forward")
    assert walk is not None
    assert walk.skill_id == WALK_SEED_ID
    assert walk.execute_id == WALK_EXECUTE_ID
    assert walk.walk_command == "forward"
    turn = parse_intent("turn left")
    assert turn is not None and turn.walk_command == "turn_left"
    go_left = parse_intent("go left")
    assert go_left is not None and go_left.walk_command == "turn_left"
    walk_left = parse_intent("walk left")
    assert walk_left is not None and walk_left.walk_command == "turn_left"
    go_right = parse_intent("go right")
    assert go_right is not None and go_right.walk_command == "turn_right"
    bare_left = parse_intent("left")
    assert bare_left is not None and bare_left.walk_command == "turn_left"
    strafe = parse_intent("strafe left")
    assert strafe is not None and strafe.walk_command == "strafe_left"
    hop = parse_intent("hop")
    assert hop is not None
    assert hop.skill_id == HOP_SEED_ID
    assert hop.execute_id == HOP_EXECUTE_ID
    assert parse_intent("sit") is None
    assert classify_reply("yes") == "affirm"
    assert classify_reply("adapt it") == "affirm"
    assert classify_reply("Adapt it") == "affirm"
    assert classify_reply("nope") == "deny"
    assert classify_reply("walk forward") == "task"
    assert velocity_for_walk_command("turn_left") == [0.0, 0.0, 0.6]


def test_client_from_env_and_classify() -> None:
    assert client_from_env({}) is None
    client = client_from_env({"ACQUIRE_API_URL": "http://127.0.0.1:8000"})
    assert client is not None and client.base_url == "http://127.0.0.1:8000"
    assert classify_acquire(404, {}, family="walk")[0] == "none"
    assert (
        classify_acquire(
            200,
            {
                "status": "rejected",
                "mismatch_report": {"reasons": [{"check": "embodiment", "message": "go2 only"}]},
            },
            family="walk",
        )[0]
        == "adapt_offer"
    )
    assert (
        classify_acquire(
            200,
            {
                "status": "rejected",
                "mismatch_report": {
                    "reasons": [{"check": "payload", "message": "arm on the head"}]
                },
            },
            family="hop",
        )[0]
        == "reject"
    )
    assert (
        classify_acquire(
            200,
            {
                "status": "rejected",
                "mismatch_report": {"reasons": [{"check": "embodiment", "message": "go2 only"}]},
            },
            family="hop",
        )[0]
        == "reject"
    )


@pytest.mark.asyncio
async def test_probe_go2_walk_fits_without_remap_or_prompt(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    client, fake, store = _wire("go2", monkeypatch)
    async with client:
        resp = await client.post("/api/chat", json={"prompt": "walk forward"})
        assert resp.status_code == 200, resp.text
        body = resp.text
    assert "We have the Go2 walk" in body
    assert "Apply it?" in body
    assert '"kind":"propose"' in body
    assert '"type":"Button"' in body
    assert '"action":"apply"' in body
    assert '"label":"Apply it"' in body
    assert WALK_EXECUTE_ID in body
    assert "adapt" not in str(fake.state.calls[0].get("adapt"))
    assert fake.state.calls[0]["allow_adapt"] is False
    assert fake.state.calls[0]["verify"] is False
    assert fake.state.calls[0]["skill_id"] == WALK_SEED_ID
    assert fake.state.calls[0]["embodiment"] == "go2"
    propose = store.acquire_propose()
    assert propose is not None
    assert propose["verdict"] == "fit"
    assert propose["execute_id"] == WALK_EXECUTE_ID
    assert propose["walk_command"] == "forward"
    assert not _shim_wrote(openral_shim)


@pytest.mark.asyncio
async def test_probe_go_left_is_turn_left(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    client, fake, store = _wire("go2", monkeypatch)
    async with client:
        resp = await client.post("/api/chat", json={"prompt": "go left"})
        assert resp.status_code == 200, resp.text
        assert "We have the Go2 walk" in resp.text
        assert fake.state.calls[0]["skill_id"] == WALK_SEED_ID
        assert fake.state.calls[0]["task"] == "go left"
    propose = store.acquire_propose()
    assert propose is not None
    assert propose["walk_command"] == "turn_left"
    assert not _shim_wrote(openral_shim)


@pytest.mark.asyncio
async def test_probe_go2_z1_walk_asks_then_yes_remaps(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    client, fake, store = _wire("go2_z1", monkeypatch)
    async with client:
        first = await client.post("/api/chat", json={"text": "walk forward"})
        assert first.status_code == 200, first.text
        assert "adapt it?" in first.text
        assert '"kind":"propose"' in first.text
        assert '"type":"Button"' in first.text
        assert '"action":"adapt"' in first.text
        assert '"label":"Adapt it"' in first.text
        assert fake.state.calls[0]["allow_adapt"] is False
        assert "adapt" not in fake.state.calls[0] or fake.state.calls[0].get("adapt") in {
            None,
            False,
        }
        pending = store.acquire_propose()
        assert pending is not None and pending["verdict"] == "adapt_offer"

        yes = await client.post("/api/chat", json={"prompt": "yes"})
        assert yes.status_code == 200, yes.text
        assert "Adapted onto Go2+Z1" in yes.text
        assert '"action":"apply"' in yes.text
        assert '"label":"Apply it"' in yes.text
        assert len(fake.state.calls) == 2
        assert fake.state.calls[1]["adapt"] == "remap"
        assert fake.state.calls[1]["verify"] is True
        assert fake.state.calls[1]["skill_id"] == WALK_SEED_ID
        assert fake.state.calls[1]["task"] == "walk forward"
        done = store.acquire_propose()
        assert done is not None
        assert done["verdict"] == "adapted"
        assert done["skill_id"] == WALK_FORK
        assert done["execute_id"] == WALK_EXECUTE_ID
    assert not _shim_wrote(openral_shim)


@pytest.mark.asyncio
async def test_adapt_it_typed_label_remaps(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    client, fake, _store = _wire("go2_z1", monkeypatch)
    async with client:
        await client.post("/api/chat", json={"text": "walk forward"})
        typed = await client.post("/api/chat", json={"prompt": "Adapt it"})
        assert typed.status_code == 200, typed.text
        assert "Adapted onto Go2+Z1" in typed.text
        assert '"action":"apply"' in typed.text
        assert fake.state.calls[1]["adapt"] == "remap"
        assert fake.state.calls[1]["task"] == "walk forward"
    assert not _shim_wrote(openral_shim)


@pytest.mark.asyncio
async def test_hop_on_go2_z1_is_payload_reject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, fake, store = _wire("go2_z1", monkeypatch)
    async with client:
        resp = await client.post("/api/chat", json={"prompt": "hop"})
        assert resp.status_code == 200, resp.text
        assert "Nothing fits" in resp.text
        assert "arm on the head" in resp.text
        assert "adapt it?" not in resp.text
        assert '"type":"Button"' not in resp.text
        assert fake.state.calls[0]["skill_id"] == HOP_SEED_ID
        assert store.acquire_propose() is None


@pytest.mark.asyncio
async def test_no_unit_and_unknown_intent_do_not_call_acquire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, fake, _store = _wire("", monkeypatch)
    async with client:
        empty = await client.post("/api/chat", json={"prompt": "walk forward"})
        assert empty.status_code == 200, empty.text
        assert "Load the unit first" in empty.text
        assert fake.state.calls == []

        monkeypatch.setattr(
            "openral_observability.dashboard.chat.occupant_robot_id",
            lambda env=None: "go2",
        )
        sit = await client.post("/api/chat", json={"prompt": "sit"})
        assert sit.status_code == 200, sit.text
        assert "Nothing fits" in sit.text
        assert fake.state.calls == []


@pytest.mark.asyncio
async def test_deny_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _fake, store = _wire("go2", monkeypatch)
    async with client:
        await client.post("/api/chat", json={"prompt": "walk forward"})
        assert store.acquire_propose() is not None
        deny = await client.post("/api/chat", json={"prompt": "no"})
        assert deny.status_code == 200, deny.text
        assert "no skill selected" in deny.text
        assert store.acquire_propose() is None


@pytest.mark.asyncio
async def test_state_exposes_acquire_propose(monkeypatch: pytest.MonkeyPatch) -> None:
    store = TelemetryStore()
    store.set_acquire_propose(
        {
            "verdict": "fit",
            "skill_id": WALK_SEED_ID,
            "execute_id": WALK_EXECUTE_ID,
            "embodiment": "go2",
            "session_id": "simple-go2",
            "walk_command": "turn_right",
            "check": None,
            "detail": "",
        }
    )
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/state")
        assert resp.status_code == 200
        assert resp.json()["acquire_propose"]["walk_command"] == "turn_right"


@pytest.mark.asyncio
async def test_walk_forwards_velocity_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, list[float] | None]] = []

    async def _fake_walk(
        skill_id: str = "",
        velocity_commands: list[float] | None = None,
    ) -> JSONResponse:
        seen.append((skill_id, velocity_commands))
        return JSONResponse({"status": "ok", "accepted": True})

    monkeypatch.setenv("OPENRAL_DASHBOARD_WRITE_CONTROLS", "1")
    monkeypatch.setattr(
        "openral_observability.dashboard.demo_controls.walk_response",
        _fake_walk,
    )
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/demo/walk",
            json={
                "skill_id": WALK_EXECUTE_ID,
                "velocity_commands": [0.0, 0.0, 0.6],
            },
        )
        assert resp.status_code == 200, resp.text
    assert seen == [(WALK_EXECUTE_ID, [0.0, 0.0, 0.6])]


def test_dashboard_env_file_roundtrip(tmp_path: Path) -> None:
    from openral_observability.dashboard.acquire_client import (
        ACQUIRE_API_KEY_ENV,
        ACQUIRE_API_URL_ENV,
        DASHBOARD_ENV_FILE_ENV,
        RAILWAY_ACQUIRE_API_URL,
        apply_dashboard_env,
        parse_dashboard_env,
        resolve_dashboard_env_path,
        write_dashboard_acquire_env,
    )

    parsed = parse_dashboard_env(
        "export ACQUIRE_API_URL=https://example.test\n"
        "# comment\n"
        "TOKEN=nope\n"
        "ACQUIRE_API_KEY='secret-key'\n"
    )
    assert parsed == {
        ACQUIRE_API_URL_ENV: "https://example.test",
        ACQUIRE_API_KEY_ENV: "secret-key",
    }
    path = tmp_path / "dashboard.env"
    written = write_dashboard_acquire_env(
        path,
        url=RAILWAY_ACQUIRE_API_URL,
        api_key="k" * 8,
    )
    assert written == path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    dest: dict[str, str] = {}
    loaded, keys = apply_dashboard_env(dest, path=path)
    assert loaded == path
    assert set(keys) == {ACQUIRE_API_URL_ENV, ACQUIRE_API_KEY_ENV}
    assert dest[ACQUIRE_API_URL_ENV] == RAILWAY_ACQUIRE_API_URL
    already = {ACQUIRE_API_URL_ENV: "http://already.set"}
    _, keys2 = apply_dashboard_env(already, path=path)
    assert already[ACQUIRE_API_URL_ENV] == "http://already.set"
    assert keys2 == (ACQUIRE_API_KEY_ENV,)
    missing = tmp_path / "missing"
    assert resolve_dashboard_env_path(env={}, home=missing, cwd=missing) is None
    override = tmp_path / "override.env"
    override.write_text(f"{ACQUIRE_API_URL_ENV}=https://override.test\n", encoding="utf-8")
    resolved = resolve_dashboard_env_path(
        env={DASHBOARD_ENV_FILE_ENV: str(override)},
        home=missing,
        cwd=missing,
    )
    assert resolved == override
