"""Streaming operator chat for ``GET /simple``.

``POST /api/chat`` probes the sibling Acquire API (fit / adapt-offer /
reject) and streams mixed text + JSONL SpecStream for Vercel
``json-render`` ``useChatUI``. Probe and ask turns do **not** publish
``/openral/prompt`` — that path can skip-LLM execute.

``POST /api/prompt`` still uses :func:`publish_operator_prompt` (the only
``openral prompt`` shell-out). Do not add a second LLM here.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from openral_observability.dashboard.acquire_client import (
    AcquireClient,
    AcquireIntent,
    AcquirePropose,
    classify_acquire,
    classify_reply,
    occupant_robot_id,
    parse_intent,
    propose_from_probe,
    session_id_for,
)
from openral_observability.dashboard.store import TelemetryStore

__all__ = [
    "PromptPublishResult",
    "chat_response",
    "prompt_from_body",
    "publish_operator_prompt",
]

_PROMPT_TOPIC: Final[str] = "/openral/prompt_in/dashboard"
_PUBLISH_TIMEOUT_S: Final[float] = 10.0
_UNIT_CHANGED_LINE: Final[str] = "unit changed."
_CHAT_STREAM_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


@dataclass(frozen=True)
class PromptPublishResult:
    """Outcome of one ``openral prompt`` shell-out."""

    ok: bool
    status_code: int
    payload: dict[str, object]


def _stripped(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _text_from_parts(parts: object) -> str | None:
    if not isinstance(parts, list):
        return None
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        piece = _stripped(part.get("text"))
        if piece is not None:
            chunks.append(piece)
    return "\n".join(chunks) if chunks else None


def _text_from_message(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    if item.get("role") not in (None, "user"):
        return None
    for key in ("content", "text"):
        found = _stripped(item.get(key))
        if found is not None:
            return found
    return _text_from_parts(item.get("parts"))


def prompt_from_body(payload: object) -> str | None:
    """Pull the operator utterance from a chat or prompt JSON body.

    Accepts ``prompt`` (json-render ``useUIStream``), ``text`` (``POST
    /api/prompt``), or the last user ``content`` / text parts in ``messages``
    (``useChatUI`` / AI SDK).

    Example:
        >>> prompt_from_body({"prompt": "walk forward"})
        'walk forward'
        >>> prompt_from_body({"text": "  sit  "})
        'sit'
        >>> prompt_from_body({"messages": [{"role": "user", "content": "hop"}]})
        'hop'
        >>> prompt_from_body({"text": ""}) is None
        True
    """
    if not isinstance(payload, dict):
        return None
    for key in ("prompt", "text"):
        found = _stripped(payload.get(key))
        if found is not None:
            return found
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None
    for item in reversed(messages):
        found = _text_from_message(item)
        if found is not None:
            return found
    return None


async def publish_operator_prompt(text: str) -> PromptPublishResult:
    """Shell out to ``openral prompt`` on the dashboard source topic.

    Same argv as ``POST /api/prompt``. Callers must not invent a second
    publisher. Chat probe/ask must not call this.

    Example:
        >>> import asyncio
        >>> from openral_observability.dashboard.chat import PromptPublishResult
        >>> isinstance(PromptPublishResult(True, 200, {"status": "ok"}), PromptPublishResult)
        True
    """
    openral = shutil.which("openral")
    if openral is None:
        return PromptPublishResult(
            ok=False,
            status_code=503,
            payload={"error": "`openral` not on PATH; source the workspace install first"},
        )
    proc = await asyncio.create_subprocess_exec(
        openral,
        "prompt",
        text,
        "--topic",
        _PROMPT_TOPIC,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=_PUBLISH_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return PromptPublishResult(
            ok=False,
            status_code=504,
            payload={"error": "openral prompt timed out after 10 s"},
        )
    stdout = stdout_b.decode("utf-8", errors="replace").strip()
    stderr = stderr_b.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        return PromptPublishResult(
            ok=False,
            status_code=502,
            payload={
                "error": "openral prompt failed",
                "returncode": proc.returncode if proc.returncode is not None else -1,
                "stderr": stderr,
            },
        )
    return PromptPublishResult(
        ok=True,
        status_code=200,
        payload={"status": "ok", "stdout": stdout, "stderr": stderr},
    )


async def chat_response(request: Request, store: TelemetryStore) -> Response:
    """Body of ``POST /api/chat`` — 400 JSON or a mixed text/JSONL stream.

    Example:
        >>> from openral_observability.dashboard.chat import prompt_from_body
        >>> prompt_from_body({"messages": [{"role": "user", "content": "stand"}]})
        'stand'
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        return JSONResponse({"error": f"invalid json: {exc}"}, status_code=400)
    text = prompt_from_body(payload)
    if text is None:
        return JSONResponse(
            {"error": "field 'prompt' or 'text' required (non-empty string)"},
            status_code=400,
        )
    client = getattr(request.app.state, "acquire_client", None)
    return StreamingResponse(
        _chat_stream(text, store, client if isinstance(client, AcquireClient) else None),
        media_type="text/plain; charset=utf-8",
        headers=_CHAT_STREAM_HEADERS,
    )


def _pending(store: TelemetryStore) -> AcquirePropose | None:
    raw = store.acquire_propose()
    if raw is None:
        return None
    try:
        return AcquirePropose.model_validate(raw)
    except ValueError:
        return None


def _card_kind(verdict: str) -> str:
    if verdict in {"reject", "none", "error"}:
        return "err"
    if verdict in {"adapt_offer", "fit"}:
        return "propose"
    return "ok"


async def _chat_stream(  # noqa: PLR0912
    text: str,
    store: TelemetryStore,
    client: AcquireClient | None,
) -> AsyncIterator[bytes]:
    """Acquire probe/ask stream. Never publishes a reasoner prompt."""
    reply = classify_reply(text)
    pending = _pending(store)
    occupant = occupant_robot_id()

    if reply == "deny":
        store.set_acquire_propose(None)
        for chunk in _emit(
            "Okay — no skill selected.",
            title="Cleared",
            detail="SKILL stays empty",
            kind="info",
            rows=[("prompt", text)],
        ):
            yield chunk
        return

    if reply == "affirm":
        async for chunk in _affirm_stream(text, store, client, pending, occupant):
            yield chunk
        return

    if not occupant:
        for chunk in _emit(
            "Load the unit first.",
            title="No unit",
            detail="Pick Bare Go2 or Go2 + Z1, then ask chat.",
            kind="err",
            rows=[("prompt", text)],
        ):
            yield chunk
        return

    intent = parse_intent(text)
    if intent is None:
        store.set_acquire_propose(None)
        for chunk in _emit(
            "Nothing fits.",
            title="No skill",
            detail="Acquire has no card for that on this unit.",
            kind="err",
            rows=[("prompt", text), ("unit", occupant)],
        ):
            yield chunk
        return

    if client is None:
        for chunk in _emit(
            "Acquire is not configured. Set ACQUIRE_API_URL.",
            title="Fault",
            detail="ACQUIRE_API_URL is empty",
            kind="err",
            rows=[("prompt", text), ("unit", occupant)],
        ):
            yield chunk
        return

    session = session_id_for(occupant)
    try:
        status, body = await client.probe(
            task=text,
            embodiment=occupant,
            skill_id=intent.skill_id,
            session_id=session,
        )
    except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
        for chunk in _emit(
            f"Acquire did not answer: {exc}",
            title="Fault",
            detail=str(exc),
            kind="err",
            rows=[("prompt", text), ("unit", occupant)],
        ):
            yield chunk
        return

    async for chunk in _verdict_stream(
        text=text,
        store=store,
        intent=intent,
        occupant=occupant,
        session=session,
        status=status,
        body=body,
        propose_task=text,
    ):
        yield chunk


async def _affirm_stream(  # noqa: PLR0912
    text: str,
    store: TelemetryStore,
    client: AcquireClient | None,
    pending: AcquirePropose | None,
    occupant: str,
) -> AsyncIterator[bytes]:
    if pending is None:
        for chunk in _emit(
            "Nothing to adapt yet.",
            title="Idle",
            detail="Ask for a walk or hop first.",
            kind="info",
            rows=[("prompt", text)],
        ):
            yield chunk
        return
    if occupant and pending.embodiment and occupant != pending.embodiment:
        store.set_acquire_propose(None)
        for chunk in _emit(
            _UNIT_CHANGED_LINE,
            title="unit changed",
            detail=_UNIT_CHANGED_LINE,
            kind="info",
            rows=[("prompt", text), ("unit", occupant)],
        ):
            yield chunk
        return
    if pending.verdict == "adapt_offer":
        if client is None:
            for chunk in _emit(
                "Acquire is not configured. Set ACQUIRE_API_URL.",
                title="Fault",
                detail="ACQUIRE_API_URL is empty",
                kind="err",
                rows=[("prompt", text)],
            ):
                yield chunk
            return
        if not occupant:
            for chunk in _emit(
                "Load the unit first.",
                title="No unit",
                detail="UNIT dropped before adapt.",
                kind="err",
                rows=[("prompt", text)],
            ):
                yield chunk
            return
        remap_task = _remap_task(pending)
        try:
            status, body = await client.remap(
                task=remap_task,
                embodiment=occupant,
                skill_id=pending.skill_id,
                session_id=pending.session_id,
            )
        except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            for chunk in _emit(
                f"Acquire remap failed: {exc}",
                title="Fault",
                detail=str(exc),
                kind="err",
                rows=[("prompt", text)],
            ):
                yield chunk
            return
        intent = AcquireIntent(
            family="walk",
            skill_id=pending.skill_id,
            execute_id=pending.execute_id,
            walk_command=pending.walk_command,
        )
        async for chunk in _verdict_stream(
            text=text,
            store=store,
            intent=intent,
            occupant=occupant,
            session=pending.session_id,
            status=status,
            body=body,
            expect_remap=True,
            propose_task=remap_task,
        ):
            yield chunk
        return
    for chunk in _emit(
        "Skill is selected. Stand if needed, then Apply.",
        title="Ready",
        detail=pending.execute_id,
        kind="ok",
        rows=[
            ("prompt", text),
            ("rskill", pending.execute_id),
            ("verdict", pending.verdict),
        ],
        cta=("Apply it", "apply"),
    ):
        yield chunk


async def _verdict_stream(
    *,
    text: str,
    store: TelemetryStore,
    intent: AcquireIntent,
    occupant: str,
    session: str,
    status: int,
    body: dict[str, object],
    expect_remap: bool = False,
    propose_task: str = "",
) -> AsyncIterator[bytes]:
    skill_id = str(body.get("skill_id") or intent.skill_id)
    verdict, check, detail = classify_acquire(status, body, family=intent.family)
    if verdict == "fit" or verdict == "adapt_offer" or verdict == "adapted":  # noqa: PLR1714
        store.set_acquire_propose(
            propose_from_probe(
                verdict=verdict,
                intent=intent,
                embodiment=occupant,
                session_id=session,
                skill_id=skill_id,
                check=check,
                detail=detail,
                task=propose_task or text,
            ).as_state(),
        )
    else:
        store.set_acquire_propose(None)

    title, line = _operator_copy(
        verdict=verdict,
        family=intent.family,
        occupant=occupant,
        detail=detail,
        expect_remap=expect_remap,
    )
    rows: list[tuple[str, str]] = [
        ("prompt", text),
        ("unit", occupant),
        ("verdict", verdict),
    ]
    if skill_id:
        rows.append(("acquire", skill_id))
    rows.append(("rskill", intent.execute_id))
    if check:
        rows.append(("check", check))
    if intent.walk_command:
        rows.append(("cmd", intent.walk_command))
    for chunk in _emit(
        line,
        title=title,
        detail=detail or line,
        kind=_card_kind(verdict),
        rows=rows,
        cta=_cta_for(verdict, intent.family),
    ):
        yield chunk


def _remap_task(pending: AcquirePropose) -> str:
    stored = pending.task.strip()
    if stored:
        return stored
    command = (pending.walk_command or "").replace("_", " ").strip()
    if command:
        return f"walk {command}"
    return "walk forward"


def _cta_for(verdict: str, family: str) -> tuple[str, str] | None:
    if verdict == "adapt_offer":
        return ("Adapt it", "adapt")
    if verdict in {"fit", "adapted"}:
        if family == "hop":
            return ("Apply hop", "apply")
        return ("Apply it", "apply")
    return None


def _operator_copy(  # noqa: PLR0911
    *,
    verdict: str,
    family: str,
    occupant: str,
    detail: str,
    expect_remap: bool,
) -> tuple[str, str]:
    if verdict == "fit":
        if family == "hop":
            return (
                "Hop",
                "Acquire has an unladen hop. Apply runs the gym spring_jump ONNX.",
            )
        return "Fit", "We have the Go2 walk. Apply it?"
    if verdict == "adapt_offer":
        return (
            "Adapt?",
            "We have the Go2 walk. This body is Go2+Z1 — adapt it?",
        )
    if verdict == "adapted":
        return "Adapted", "Adapted onto Go2+Z1. Apply it?"
    if verdict == "reject":
        extra = f" {detail}" if detail else ""
        return "Nothing fits", f"Nothing fits.{extra}"
    if verdict == "none":
        return "Nothing fits", "Nothing fits."
    if expect_remap:
        return "Fault", detail or "Acquire remap failed"
    _ = occupant
    return "Fault", detail or "Acquire did not accept that"


def _emit(
    line: str,
    *,
    title: str,
    detail: str,
    kind: str,
    rows: list[tuple[str, str]],
    cta: tuple[str, str] | None = None,
) -> list[bytes]:
    out: list[bytes] = [f"{line}\n".encode()]
    children = [f"kv{idx}" for idx in range(len(rows))]
    if cta is not None:
        children.append("cta")
    patches: list[dict[str, object]] = [
        {"op": "add", "path": "/root", "value": "stack"},
        {
            "op": "add",
            "path": "/elements/stack",
            "value": {"type": "Stack", "props": {}, "children": ["card"]},
        },
        {
            "op": "add",
            "path": "/elements/card",
            "value": {
                "type": "StatusCard",
                "props": {
                    "mark": "ACQ",
                    "title": title,
                    "detail": detail,
                    "kind": kind,
                },
                "children": children,
            },
        },
    ]
    for idx, (label, value) in enumerate(rows):
        patches.append(
            {
                "op": "add",
                "path": f"/elements/kv{idx}",
                "value": {
                    "type": "Kv",
                    "props": {"label": label, "value": value},
                    "children": [],
                },
            }
        )
    if cta is not None:
        label, action = cta
        patches.append(
            {
                "op": "add",
                "path": "/elements/cta",
                "value": {
                    "type": "Button",
                    "props": {"label": label, "action": action},
                    "on": {"press": [{"action": action}]},
                    "children": [],
                },
            }
        )
    out.extend((json.dumps(patch, separators=(",", ":")) + "\n").encode() for patch in patches)
    return out
