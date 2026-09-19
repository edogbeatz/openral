"""``openral viz mujoco`` — laptop-side kinematic MuJoCo viewer.

Polls the dashboard ``GET /api/qpos`` stream and applies it to a local
``mjModel`` with ``mj_forward`` only. Physics, contacts, and the policy stay
on the remote HAL. This is the lag-free native-MuJoCo path: kilobytes of
``qpos``, not 640x480 JPEG pixels, and no extra EGL render on cricket.

Example:
    ``openral viz mujoco --dashboard http://127.0.0.1:4318``
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import typer
from openral_core.assets import AssetRefError, resolve_asset
from openral_core.exceptions import ROSConfigError
from rich.console import Console

__all__ = [
    "apply_qpos",
    "fetch_qpos",
    "resolve_viz_mjcf",
    "viz_app",
]

viz_app = typer.Typer(
    name="viz",
    help=(
        "Laptop-side visualisation. ``mujoco`` opens a kinematic viewer fed "
        "by the dashboard pose stream (no cricket EGL cameras)."
    ),
    no_args_is_help=True,
)
_console = Console()

_DEFAULT_DASHBOARD = "http://127.0.0.1:4318"
_DEFAULT_HZ = 50.0
_HTTP_NO_CONTENT = 204


class _QposBuf(Protocol):
    def __setitem__(self, key: slice, value: list[float]) -> None: ...


class _MjModel(Protocol):
    nq: int


class _MjData(Protocol):
    qpos: _QposBuf


class _MujocoApi(Protocol):
    def mj_forward(self, model: _MjModel, data: _MjData) -> object: ...


def fetch_qpos(dashboard_url: str, *, timeout_s: float = 2.0) -> dict[str, object] | None:
    """GET ``/api/qpos``. ``None`` on 204 (no sample yet).

    Raises:
        ROSConfigError: HTTP error other than 204, or a malformed JSON body.
    """
    url = urljoin(dashboard_url.rstrip("/") + "/", "api/qpos")
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            if response.status == _HTTP_NO_CONTENT:
                return None
            payload: object = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == _HTTP_NO_CONTENT:
            return None
        raise ROSConfigError(f"GET {url} failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ROSConfigError(f"GET {url} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ROSConfigError(f"GET {url} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ROSConfigError(f"GET {url} returned a non-object JSON body")
    return payload


def apply_qpos(model: _MjModel, data: _MjData, qpos: list[float], *, mujoco: _MujocoApi) -> None:
    """Copy ``qpos`` into ``data`` and run ``mj_forward``. Never ``mj_step``.

    Raises:
        ROSConfigError: ``len(qpos)`` does not match ``model.nq``.
    """
    nq = int(model.nq)
    if len(qpos) != nq:
        raise ROSConfigError(
            f"qpos width {len(qpos)} does not match model.nq={nq}; "
            "load the same MJCF the HAL composed (pass --robot / --scene)."
        )
    data.qpos[:] = qpos
    mujoco.mj_forward(model, data)


def resolve_viz_mjcf(
    *,
    robot_yaml: Path,
    scene_yaml: Path | None = None,
) -> Path:
    """Resolve the MJCF the HAL would load for this robot (+ optional scene).

    Scene ``composition`` wins over ``scene_defaults.composition``, matching
    ``ManifestHALLifecycleNode._create_hal``. Bare ``assets.mjcf`` is used
    when neither declares a composer (Go2 menagerie file; nq still matches
    ``go2_walk`` because that scene only adds a ground plane).
    """
    from openral_core import RobotDescription

    if not robot_yaml.is_file():
        raise ROSConfigError(f"robot manifest not found: {robot_yaml}")
    description = RobotDescription.from_yaml(str(robot_yaml))
    composition = None
    if scene_yaml is not None:
        from openral_core import DeployScene, load_scene_strict

        scene = load_scene_strict(str(scene_yaml), DeployScene)
        composition = scene.composition
    if composition is None and description.scene_defaults is not None:
        composition = description.scene_defaults.composition
    if composition is None:
        if not description.assets.mjcf:
            raise ROSConfigError(f"RobotDescription '{description.name}' has no assets.mjcf")
        try:
            path = resolve_asset(description.assets.mjcf, "mjcf")
        except AssetRefError as exc:
            raise ROSConfigError(str(exc)) from exc
        if path is None:
            raise ROSConfigError(
                f"assets.mjcf={description.assets.mjcf!r} did not resolve to a file"
            )
        return Path(path)
    import importlib

    module_path, _, fn_name = composition.composer.partition(":")
    composer = getattr(importlib.import_module(module_path), fn_name)
    xml, meshdir = composer(**composition.params)
    scene_path = Path(meshdir).parent / f"{description.name}_composed_scene.xml"
    scene_path.write_text(xml)
    return scene_path


def _robot_yaml_for(robot_id: str) -> Path:
    from openral_core.assets import _REPO_ROOT

    path = _REPO_ROOT / "robots" / robot_id / "robot.yaml"
    if not path.is_file():
        raise ROSConfigError(
            f"robot manifest not found at {path}; expected robots/{robot_id}/robot.yaml"
        )
    return path


def _ensure_glfw() -> None:
    """This command draws a window on the operator GPU; EGL is headless."""
    if os.environ.get("MUJOCO_GL", "").lower() == "egl":
        os.environ["MUJOCO_GL"] = "glfw"


def _qpos_list(payload: dict[str, object]) -> list[float] | None:
    raw = payload.get("qpos")
    if not isinstance(raw, list):
        return None
    return [float(v) for v in raw]


@viz_app.command("mujoco")
def viz_mujoco(
    dashboard: str = typer.Option(
        _DEFAULT_DASHBOARD,
        "--dashboard",
        help="Dashboard origin that serves GET /api/qpos (cricket tunnel).",
    ),
    robot: Path | None = typer.Option(
        None,
        "--robot",
        exists=True,
        dir_okay=False,
        help="robots/<id>/robot.yaml. Default: identity robot_id from /api/qpos.",
    ),
    scene: Path | None = typer.Option(
        None,
        "--scene",
        exists=True,
        dir_okay=False,
        help="Optional DeployScene YAML whose composition wins (ground plane).",
    ),
    hz: float = typer.Option(
        _DEFAULT_HZ,
        "--hz",
        min=1.0,
        max=200.0,
        help="Viewer poll rate. Does not change cricket publish_rate_hz.",
    ),
) -> None:
    """Open a kinematic MuJoCo window driven by the live dashboard pose stream."""
    _ensure_glfw()
    try:
        import mujoco
        import mujoco.viewer
    except ImportError as exc:
        _console.print(f"[red]mujoco is not installed:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        payload = fetch_qpos(dashboard)
        robot_yaml = robot
        if robot_yaml is None:
            robot_id = None
            if payload is not None:
                raw_id = payload.get("robot_id")
                robot_id = raw_id if isinstance(raw_id, str) and raw_id else None
            if not robot_id:
                raise ROSConfigError(
                    "no robot_id yet (dashboard WAITING). Pass --robot robots/<id>/robot.yaml."
                )
            robot_yaml = _robot_yaml_for(robot_id)
        mjcf_path = resolve_viz_mjcf(robot_yaml=robot_yaml, scene_yaml=scene)
        model = mujoco.MjModel.from_xml_path(str(mjcf_path))
        data = mujoco.MjData(model)
        first = _qpos_list(payload) if payload is not None else None
        if first is not None:
            apply_qpos(model, data, first, mujoco=mujoco)
    except ROSConfigError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    _console.print(
        f"[bold]openral viz mujoco[/bold]  {mjcf_path.name}  nq={int(model.nq)}  "
        f"{dashboard}/api/qpos @ {hz:.0f} Hz  (mj_forward only)"
    )
    period = 1.0 / hz
    with mujoco.viewer.launch_passive(
        model, data, show_left_ui=False, show_right_ui=False
    ) as viewer:
        while viewer.is_running():
            tick = time.monotonic()
            try:
                sample = fetch_qpos(dashboard)
            except ROSConfigError as exc:
                _console.print(f"[yellow]{exc}[/yellow]")
                sample = None
            qpos = _qpos_list(sample) if sample is not None else None
            if qpos is not None:
                try:
                    apply_qpos(model, data, qpos, mujoco=mujoco)
                except ROSConfigError as exc:
                    _console.print(f"[red]{exc}[/red]")
                    raise typer.Exit(1) from exc
            viewer.sync(state_only=True)
            leftover = period - (time.monotonic() - tick)
            if leftover > 0:
                time.sleep(leftover)
