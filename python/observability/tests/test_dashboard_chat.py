"""Tests for ``POST /api/chat`` body parsing and the prompt publisher."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from openral_observability.dashboard import TelemetryStore, create_app
from openral_observability.dashboard.acquire_client import AcquireClient
from openral_observability.dashboard.chat import prompt_from_body, publish_operator_prompt

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from fakes.acquire_api import fake_acquire_app  # noqa: E402


@pytest.fixture
def openral_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Install an ``openral`` shim on PATH that logs argv and exits 0."""
    log = tmp_path / "openral_calls.txt"
    shim = tmp_path / "openral"
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
    import json as _json

    return list(_json.loads(log.read_text()))


def _shim_wrote(log: Path) -> bool:
    return log.is_file()


def test_prompt_from_body_shapes() -> None:
    assert prompt_from_body({"prompt": "walk forward"}) == "walk forward"
    assert prompt_from_body({"text": "  sit  "}) == "sit"
    assert prompt_from_body({"messages": [{"role": "user", "content": "hop"}]}) == "hop"
    assert (
        prompt_from_body(
            {
                "messages": [
                    {"role": "assistant", "content": "Go2 here."},
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "stand up"}],
                    },
                ]
            }
        )
        == "stand up"
    )
    assert prompt_from_body({"text": ""}) is None
    assert prompt_from_body({"text": 42}) is None
    assert prompt_from_body({}) is None


@pytest.mark.asyncio
async def test_publish_operator_prompt_still_shells_out(openral_shim: Path) -> None:
    result = await publish_operator_prompt("walk forward")
    assert result.ok
    assert result.status_code == 200
    assert _read_shim_argv(openral_shim) == [
        "prompt",
        "walk forward",
        "--topic",
        "/openral/prompt_in/dashboard",
    ]


@pytest.mark.asyncio
async def test_post_chat_rejects_empty() -> None:
    app = create_app(TelemetryStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for payload in ({}, {"text": ""}, {"prompt": "   "}, {"messages": []}):
            resp = await client.post("/api/chat", json=payload)
            assert resp.status_code == 400, payload


@pytest.mark.asyncio
async def test_post_chat_without_acquire_url_does_not_publish(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    monkeypatch.setattr(
        "openral_observability.dashboard.chat.occupant_robot_id",
        lambda env=None: "go2",
    )
    monkeypatch.delenv("ACQUIRE_API_URL", raising=False)
    app = create_app(TelemetryStore())
    app.state.acquire_client = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"text": "walk forward"})
        assert resp.status_code == 200, resp.text
        assert "ACQUIRE_API_URL" in resp.text
        assert '"kind":"err"' in resp.text
    assert not _shim_wrote(openral_shim)


@pytest.mark.asyncio
async def test_affirm_after_unit_change_says_unit_changed(
    monkeypatch: pytest.MonkeyPatch,
    openral_shim: Path,
) -> None:
    """Yes/Adapt after UNIT actually switches streams ``unit changed.`` — not remap."""
    occupant = {"id": "go2"}
    monkeypatch.setattr(
        "openral_observability.dashboard.chat.occupant_robot_id",
        lambda env=None: occupant["id"],
    )
    fake = fake_acquire_app()
    acquire = AcquireClient(
        base_url="http://acquire.test",
        transport=httpx.ASGITransport(app=fake),
    )
    store = TelemetryStore()
    app = create_app(store)
    app.state.acquire_client = acquire
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/chat", json={"prompt": "walk forward"})
        assert first.status_code == 200, first.text
        assert store.acquire_propose() is not None
        occupant["id"] = "go2_z1"
        yes = await client.post("/api/chat", json={"prompt": "yes"})
        assert yes.status_code == 200, yes.text
        assert yes.text.startswith("unit changed.")
        assert "Ask chat again" not in yes.text
        assert '"title":"unit changed"' in yes.text
        assert '"detail":"unit changed."' in yes.text
        assert '"kind":"info"' in yes.text
        assert store.acquire_propose() is None
        assert len(fake.state.calls) == 1
        assert "adapt" not in fake.state.calls[0] or fake.state.calls[0].get("adapt") in {
            None,
            False,
        }
    assert not _shim_wrote(openral_shim)
