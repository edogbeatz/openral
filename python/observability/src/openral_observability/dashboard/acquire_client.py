"""HTTP client for the sibling Acquire API (probe, then opt-in remap).

``/simple`` chat is the only caller. Do not add a second client, and do
not reimplement ``evaluate_gate`` / ``adapt.py`` — those live in
``edogbeatz/robo-skill-acquire``. Embodiment is the UNIT id only
(``go2`` / ``go2_z1``); extra OpenRAL tags would hide adopt.

Probe uses ``allow_adapt=false`` so the operator can be asked. Remap is
a later turn. Chat never starts motors.
"""

from __future__ import annotations

import http
import os
import re
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

__all__ = [
    "ACQUIRE_API_KEY_ENV",
    "ACQUIRE_API_URL_ENV",
    "DASHBOARD_ACQUIRE_ENV_KEYS",
    "DASHBOARD_ENV_FILE_ENV",
    "HOP_EXECUTE_ID",
    "HOP_SEED_ID",
    "RAILWAY_ACQUIRE_API_URL",
    "WALK_EXECUTE_ID",
    "WALK_SEED_ID",
    "WALK_VELOCITY_COMMANDS",
    "AcquireClient",
    "AcquireIntent",
    "AcquirePropose",
    "apply_dashboard_env",
    "classify_acquire",
    "classify_reply",
    "client_from_env",
    "default_dashboard_env_path",
    "execute_id_for",
    "occupant_robot_id",
    "parse_dashboard_env",
    "parse_intent",
    "propose_from_probe",
    "resolve_dashboard_env_path",
    "session_id_for",
    "velocity_for_walk_command",
    "write_dashboard_acquire_env",
]

ACQUIRE_API_URL_ENV: Final[str] = "ACQUIRE_API_URL"
ACQUIRE_API_KEY_ENV: Final[str] = "ACQUIRE_API_KEY"
DASHBOARD_ENV_FILE_ENV: Final[str] = "OPENRAL_DASHBOARD_ENV"
DASHBOARD_ACQUIRE_ENV_KEYS: Final[frozenset[str]] = frozenset(
    {ACQUIRE_API_URL_ENV, ACQUIRE_API_KEY_ENV},
)
# Documented Railway origin for ``write_dashboard_acquire_env`` / the
# example file. ``client_from_env`` does not fall back to this.
RAILWAY_ACQUIRE_API_URL: Final[str] = "https://acquire-api-production.up.railway.app"

_ENV_ASSIGN = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")

WALK_SEED_ID: Final[str] = "seed/rskill-rsl-rl-onnx-go2-velocity-flat"
HOP_SEED_ID: Final[str] = "seed/rskill-rsl-rl-onnx-go2-hop-flat"
WALK_FORK_PREFIX: Final[str] = f"fork/{WALK_SEED_ID}"
WALK_EXECUTE_ID: Final[str] = "Acquire/rskill-rsl-rl-onnx-go2-velocity-flat"
HOP_EXECUTE_ID: Final[str] = "OpenRAL/rskill-rsl_rl_onnx-go2-spring_jump-fp32"

# Copied from openral_reasoner.typesafe_policy.WALK_VELOCITY_COMMANDS — do
# not import the reasoner package from observability (layer 4 vs 7).
WALK_VELOCITY_COMMANDS: Final[dict[str, list[float]]] = {
    "forward": [0.5, 0.0, 0.0],
    "backward": [-0.3, 0.0, 0.0],
    "strafe_left": [0.0, 0.25, 0.0],
    "strafe_right": [0.0, -0.25, 0.0],
    "turn_left": [0.0, 0.0, 0.6],
    "turn_right": [0.0, 0.0, -0.6],
    "stop": [0.0, 0.0, 0.0],
}

Verdict = Literal["fit", "adapt_offer", "adapted", "reject", "none", "error"]
ReplyKind = Literal["affirm", "deny", "task"]
WalkCommand = Literal[
    "forward",
    "backward",
    "strafe_left",
    "strafe_right",
    "turn_left",
    "turn_right",
    "stop",
]

_TOKEN = re.compile(r"[a-z0-9]+")
_AFFIRM: Final[frozenset[str]] = frozenset(
    {"yes", "y", "ok", "okay", "adapt", "adaptit", "apply", "doit"},
)
_DENY: Final[frozenset[str]] = frozenset({"no", "nope", "cancel"})
_OCCUPANTS: Final[frozenset[str]] = frozenset({"go2", "go2_z1"})
_TIMEOUT_S: Final[float] = 10.0


class AcquireIntent(BaseModel):
    """Token-map result for one operator utterance (no LLM)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Literal["walk", "hop"]
    skill_id: str
    execute_id: str
    walk_command: str | None = None


class AcquirePropose(BaseModel):
    """Pending chat propose stored on ``TelemetryStore``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Literal["fit", "adapt_offer", "adapted"]
    skill_id: str
    execute_id: str
    embodiment: str
    session_id: str
    walk_command: str | None = None
    check: str | None = None
    detail: str = ""
    task: str = ""

    def as_state(self) -> dict[str, object]:
        """JSON object for ``GET /api/state`` ``acquire_propose``."""
        return self.model_dump()


class AcquireClient:
    """One ``POST /v1/skills/acquire`` helper. Tests inject ``transport``."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Bind one base URL. ``transport`` is the httpx test hook."""
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"ACQUIRE_API_URL must be an http(s) URL, got {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport
        self.calls: list[dict[str, object]] = []

    async def acquire(self, body: Mapping[str, object]) -> tuple[int, dict[str, object]]:
        """POST ``/v1/skills/acquire``. Returns ``(status_code, json)``."""
        payload = dict(body)
        self.calls.append(payload)
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        timeout = httpx.Timeout(_TIMEOUT_S)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            resp = await client.post("/v1/skills/acquire", json=payload, headers=headers)
        raw: object
        try:
            raw = resp.json()
        except ValueError:
            raw = {"error": resp.text}
        data = raw if isinstance(raw, dict) else {"error": "non-object acquire response"}
        return resp.status_code, {str(k): v for k, v in data.items()}

    async def probe(
        self,
        *,
        task: str,
        embodiment: str,
        skill_id: str,
        session_id: str,
    ) -> tuple[int, dict[str, object]]:
        """First turn: no remap, no verify."""
        return await self.acquire(
            {
                "session_id": session_id,
                "task": task,
                "embodiment": embodiment,
                "skill_id": skill_id,
                "allow_adapt": False,
                "verify": False,
            },
        )

    async def remap(
        self,
        *,
        task: str,
        embodiment: str,
        skill_id: str,
        session_id: str,
    ) -> tuple[int, dict[str, object]]:
        """Operator said yes — contract remap + inline verify."""
        scene = "go2_z1_walk" if embodiment == "go2_z1" else "go2_velocity_flat"
        return await self.acquire(
            {
                "session_id": session_id,
                "task": task,
                "embodiment": embodiment,
                "skill_id": skill_id,
                "adapt": "remap",
                "verify": True,
                "scene_id": scene,
            },
        )


def client_from_env(
    env: Mapping[str, str] | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AcquireClient | None:
    """Build a client when ``ACQUIRE_API_URL`` is set; else ``None``.

    Example:
        >>> client_from_env({}) is None
        True
        >>> c = client_from_env({"ACQUIRE_API_URL": "http://127.0.0.1:8000"})
        >>> c is not None and c.base_url == "http://127.0.0.1:8000"
        True
    """
    src = os.environ if env is None else env
    url = src.get(ACQUIRE_API_URL_ENV, "").strip()
    if not url:
        return None
    key = src.get(ACQUIRE_API_KEY_ENV, "").strip() or None
    return AcquireClient(base_url=url, api_key=key, transport=transport)


def default_dashboard_env_path(*, home: Path | None = None) -> Path:
    """``~/.openral/dashboard.env`` (or ``home/.openral/dashboard.env``)."""
    root = home if home is not None else Path.home()
    return root / ".openral" / "dashboard.env"


def resolve_dashboard_env_path(
    env: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
    cwd: Path | None = None,
) -> Path | None:
    """First Acquire env file: override, then home, repo, cwd.

    ``OPENRAL_DASHBOARD_ENV`` is the only path when set (even if missing).
    """
    src = os.environ if env is None else env
    override = src.get(DASHBOARD_ENV_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    home_path = default_dashboard_env_path(home=home)
    if home_path.is_file():
        return home_path
    repo = src.get("OPENRAL_REPO_ROOT", "").strip()
    if repo:
        repo_file = Path(repo) / ".env.dashboard"
        if repo_file.is_file():
            return repo_file
    here = cwd if cwd is not None else Path.cwd()
    local = here / ".env.dashboard"
    return local if local.is_file() else None


def parse_dashboard_env(text: str) -> dict[str, str]:
    """Parse allowlisted ``KEY=VALUE`` lines for the dashboard env file.

    Example:
        >>> parse_dashboard_env("export ACQUIRE_API_URL=https://example.test")
        {'ACQUIRE_API_URL': 'https://example.test'}
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_ASSIGN.match(line)
        if match is None:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key not in DASHBOARD_ACQUIRE_ENV_KEYS:
            continue
        quote = value[:1]
        if quote in {"'", '"'} and value.endswith(quote) and value != quote:
            value = value[1:-1]
        if value:
            out[key] = value
    return out


def apply_dashboard_env(
    dest: MutableMapping[str, str] | None = None,
    *,
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    cwd: Path | None = None,
) -> tuple[Path | None, tuple[str, ...]]:
    """Fill empty ``ACQUIRE_API_*`` dest keys from the dashboard env file.

    Existing dest values win. ``create_app`` / ``client_from_env`` do not
    call this — only ``run_dashboard`` and ``--init-acquire-env``.

    Example:
        >>> apply_dashboard_env({}, env={}, home=Path("/no/such/home"), cwd=Path("/no/such/cwd"))
        (None, ())
    """
    target: MutableMapping[str, str] = os.environ if dest is None else dest
    resolved = path if path is not None else resolve_dashboard_env_path(env, home=home, cwd=cwd)
    if resolved is None:
        return None, ()
    if not resolved.is_file():
        return resolved, ()
    parsed = parse_dashboard_env(resolved.read_text(encoding="utf-8"))
    applied: list[str] = []
    for key, value in parsed.items():
        if target.get(key, "").strip():
            continue
        target[key] = value
        applied.append(key)
    return resolved, tuple(applied)


def write_dashboard_acquire_env(
    path: Path,
    *,
    url: str,
    api_key: str,
) -> Path:
    """Write ``ACQUIRE_API_URL`` + ``ACQUIRE_API_KEY`` at 0600. Never logs the key."""
    url = url.strip()
    api_key = api_key.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"ACQUIRE_API_URL must be an http(s) URL, got {url!r}")
    if not api_key:
        raise ValueError("ACQUIRE_API_KEY is empty")
    dest = path.expanduser()
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    body = (
        "# OpenRAL laptop dashboard — sibling Acquire. Do not commit.\n"
        f"{ACQUIRE_API_URL_ENV}={url}\n"
        f"{ACQUIRE_API_KEY_ENV}={api_key}\n"
    )
    dest.write_text(body, encoding="utf-8")
    dest.chmod(0o600)
    return dest


def occupant_robot_id(env: Mapping[str, str] | None = None) -> str:
    """``go2`` / ``go2_z1`` from ``OPENRAL_ROBOT_ID`` or tunneled cricket."""
    src = os.environ if env is None else env
    rid = src.get("OPENRAL_ROBOT_ID", "").strip()
    if rid in _OCCUPANTS:
        return rid
    from openral_observability.dashboard.cricket_session import cricket_live_robot_id

    live = cricket_live_robot_id()
    return live if live in _OCCUPANTS else ""


def classify_reply(text: str) -> ReplyKind:
    """Affirm / deny / task for a follow-up turn.

    Example:
        >>> classify_reply("yes")
        'affirm'
        >>> classify_reply("adapt it")
        'affirm'
        >>> classify_reply("nope")
        'deny'
        >>> classify_reply("walk forward")
        'task'
    """
    compact = "".join(_TOKEN.findall(text.lower()))
    if compact in _AFFIRM:
        return "affirm"
    if compact in _DENY:
        return "deny"
    return "task"


def parse_intent(text: str) -> AcquireIntent | None:
    """Map an utterance onto the presentation walk/hop seeds.

    Example:
        >>> parse_intent("walk forward").skill_id == WALK_SEED_ID
        True
        >>> parse_intent("go left").walk_command
        'turn_left'
        >>> parse_intent("sit") is None
        True
    """
    tokens = set(_TOKEN.findall(text.lower()))
    if not tokens:
        return None
    if tokens & {"hop", "jump"}:
        return AcquireIntent(
            family="hop",
            skill_id=HOP_SEED_ID,
            execute_id=HOP_EXECUTE_ID,
        )
    walk_command = _walk_command(tokens)
    if walk_command is None:
        return None
    return AcquireIntent(
        family="walk",
        skill_id=WALK_SEED_ID,
        execute_id=WALK_EXECUTE_ID,
        walk_command=walk_command,
    )


def _walk_command(tokens: set[str]) -> WalkCommand | None:
    """Joystick direction. Bare ``left`` / ``go left`` is yaw, not a sidestep."""
    has_left = "left" in tokens
    has_right = "right" in tokens
    strafe = bool(tokens & {"strafe", "sidestep"})
    rules: tuple[tuple[bool, WalkCommand], ...] = (
        (strafe and has_left, "strafe_left"),
        (strafe and has_right, "strafe_right"),
        (has_left, "turn_left"),
        (has_right, "turn_right"),
        (bool(tokens & {"back", "backward", "backwards"}), "backward"),
        ("stop" in tokens and bool(tokens & {"walk", "stand"}), "stop"),
        (bool(tokens & {"walk", "forward", "fwd", "go"}), "forward"),
    )
    for matched, command in rules:
        if matched:
            return command
    return None


def execute_id_for(skill_id: str, *, family: Literal["walk", "hop"]) -> str:
    """Map an Acquire card / fork id onto the OpenRAL execute id."""
    if family == "hop":
        return HOP_EXECUTE_ID
    if skill_id == WALK_SEED_ID or skill_id.startswith(WALK_FORK_PREFIX):
        return WALK_EXECUTE_ID
    return WALK_EXECUTE_ID


def velocity_for_walk_command(command: str | None) -> list[float] | None:
    """Isaac joystick for a named walk command, or ``None``."""
    if command is None:
        return None
    vec = WALK_VELOCITY_COMMANDS.get(command)
    return list(vec) if vec is not None else None


def classify_acquire(
    status_code: int,
    payload: Mapping[str, object],
    *,
    family: Literal["walk", "hop"],
) -> tuple[Verdict, str | None, str]:
    """Turn one Acquire HTTP result into a chat verdict.

    Hop never becomes ``adapt_offer`` — payload / embodiment miss is reject.

    Example:
        >>> classify_acquire(404, {}, family="walk")[0]
        'none'
    """
    if status_code == int(http.HTTPStatus.NOT_FOUND):
        return "none", None, "no matching skill cards"
    if status_code != int(http.HTTPStatus.OK):
        err = payload.get("error") or payload.get("detail")
        detail = err if isinstance(err, str) and err.strip() else f"Acquire HTTP {status_code}"
        return "error", None, detail
    status = payload.get("status")
    if status == "rejected":
        check, detail = _mismatch(payload)
        if check == "embodiment" and family != "hop":
            return "adapt_offer", check, detail
        return "reject", check, detail
    if payload.get("adapted") is True:
        return "adapted", None, ""
    return "fit", None, ""


def _mismatch(payload: Mapping[str, object]) -> tuple[str | None, str]:
    report = payload.get("mismatch_report")
    if not isinstance(report, dict):
        return None, "rejected"
    reasons = report.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        return None, "rejected"
    first = reasons[0]
    if not isinstance(first, dict):
        return None, "rejected"
    check_raw = first.get("check")
    check = str(check_raw) if isinstance(check_raw, str) else None
    message = first.get("message")
    detail = message if isinstance(message, str) and message.strip() else (check or "rejected")
    if check == "payload":
        for row in reasons:
            if isinstance(row, dict) and row.get("check") == "payload":
                msg = row.get("message")
                if isinstance(msg, str) and msg.strip():
                    return "payload", msg
    return check, detail


def propose_from_probe(
    *,
    verdict: Literal["fit", "adapt_offer", "adapted"],
    intent: AcquireIntent,
    embodiment: str,
    session_id: str,
    skill_id: str,
    check: str | None,
    detail: str,
    task: str = "",
) -> AcquirePropose:
    """Build the store row after a successful probe / remap."""
    return AcquirePropose(
        verdict=verdict,
        skill_id=skill_id,
        execute_id=execute_id_for(skill_id, family=intent.family),
        embodiment=embodiment,
        session_id=session_id,
        walk_command=intent.walk_command,
        check=check,
        detail=detail,
        task=task,
    )


def session_id_for(embodiment: str) -> str:
    """Stable Acquire session per occupant."""
    return f"simple-{embodiment}"
