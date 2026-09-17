"""Mock scene + policies — no physics, no weights.

Used by unit tests and as a wiring smoketest. The mock scene exposes a fixed
observation schema and a configurable action dimensionality, and the mock
policies emit deterministic actions so end-to-end tests can pass on CPU-only
runners without downloading any HF weights.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from openral_sim.registry import POLICIES, SCENES
from openral_sim.rollout import StepResult

if TYPE_CHECKING:
    from openral_core import SceneSpec, SimEnvironment, TaskSpec, VLASpec

    from openral_sim.rollout import Observation


_MOCK_ACTION_DIM = 7
_MOCK_STATE_DIM = 8


@dataclass
class _MockSim:
    """Tiny gym-like env used for tests.

    The "physics" is just a step counter; success fires after
    ``success_step`` steps. Image observations are zeros of the right
    shape so any downstream image preprocessing path runs end-to-end.
    """

    scene: SceneSpec
    task: TaskSpec
    success_step: int = 5
    action_dim: int = _MOCK_ACTION_DIM
    _step: int = 0
    _rng: np.random.Generator | None = None

    def reset(self, seed: int | None = None) -> Observation:
        self._step = 0
        self._rng = np.random.default_rng(seed)
        return self._observe()

    def step(self, action: NDArray[np.float32]) -> StepResult:
        if action.shape[-1] != self.action_dim:
            raise ValueError(f"mock scene expects action_dim={self.action_dim}, got {action.shape}")
        self._step += 1
        terminated = self._step >= self.success_step
        success = terminated  # mock success: terminate after N steps
        mock_info: dict[str, object] = {}
        if self.task.success_key is not None:
            mock_info[self.task.success_key] = success
        return StepResult(
            observation=self._observe(),
            reward=1.0 if success else 0.0,
            terminated=terminated,
            truncated=False,
            info=mock_info,
        )

    def render(self) -> NDArray[np.uint8] | None:
        h = self.scene.observation_height
        w = self.scene.observation_width
        return np.zeros((h, w, 3), dtype=np.uint8)

    def close(self) -> None:
        return None

    def _observe(self) -> Observation:
        h = self.scene.observation_height
        w = self.scene.observation_width
        return {
            "images": {
                "camera1": np.zeros((h, w, 3), dtype=np.uint8),
            },
            "state": np.zeros(_MOCK_STATE_DIM, dtype=np.float32),
            "task": self.task.instruction,
        }


def _coerce_int(value: object, default: int) -> int:
    """Best-effort int coercion for values pulled from a dict[str, object]."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError(f"cannot coerce {value!r} to int")


def _coerce_float(value: object, default: float) -> float:
    """Best-effort float coercion for values pulled from a dict[str, object]."""
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"cannot coerce {value!r} to float")


@SCENES.register("mock")
def _build_mock_scene(env_cfg: SimEnvironment) -> _MockSim:
    """Build the mock scene from the SimEnvironment.

    The optional ``backend_options`` dict supports:
        ``success_step`` (int): step at which the mock task succeeds.
        ``action_dim``   (int): action vector dimensionality.
    """
    opts = env_cfg.scene.backend_options
    return _MockSim(
        scene=env_cfg.scene,
        task=env_cfg.task,
        success_step=_coerce_int(opts.get("success_step"), 5),
        action_dim=_coerce_int(opts.get("action_dim"), _MOCK_ACTION_DIM),
    )


def _float_list(value: object, *, n: int) -> list[float] | None:
    if not isinstance(value, list) or len(value) != n:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _load_controller_json(spec: VLASpec) -> dict[str, Any]:
    """Read ``controller.json`` next to a local rSkill package when present."""
    extra = spec.extra or {}
    explicit = extra.get("controller_json")
    candidates: list[Path] = []
    if isinstance(explicit, str) and explicit.strip():
        candidates.append(Path(explicit))
    uri = str(getattr(spec, "weights_uri", "") or "")
    if uri:
        root = Path(uri)
        candidates.append(root / "controller.json")
        if root.name == "controller.json":
            candidates.append(root)
        parent = root.parent
        candidates.append(parent / "controller.json")
    for path in candidates:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
    return {}


@dataclass
class _ZeroPolicy:
    """N-D scripted hold (optional trot). Defaults to zeros when no targets.

    In-tree factory key ``zero``. Used by unit tests and by Acquire's
    12-DoF Go2 locomotion rSkill (menagerie home + small diagonal trot).
    Not a learned VLA — ``hold_targets`` / ``gait`` come from
    ``VLASpec.extra`` (manifest ``policy_extras``) or ``controller.json``.
    """

    spec: VLASpec
    device: str
    action_dim: int = _MOCK_ACTION_DIM
    hold_targets: NDArray[np.float32] | None = None
    gait: str = "hold"
    gait_amp: float = 0.0
    gait_hz: float = 1.5
    dt: float = 1.0 / 30.0
    _tick: int = field(default=0)

    def reset(self) -> None:
        self._tick = 0

    def step(self, observation: Observation, instruction: str) -> NDArray[np.float32]:
        del observation, instruction
        self._tick += 1
        if self.hold_targets is not None:
            action = np.array(self.hold_targets, dtype=np.float32, copy=True)
        else:
            action = np.zeros(self.action_dim, dtype=np.float32)
        if self.gait == "trot" and self.gait_amp and action.shape[0] >= 12:
            phase = 2.0 * math.pi * self.gait_hz * float(self._tick) * self.dt
            delta = float(self.gait_amp) * math.sin(phase)
            action[1] += delta
            action[10] += delta
            action[4] -= delta
            action[7] -= delta
            action[2] -= 0.5 * delta
            action[11] -= 0.5 * delta
            action[5] += 0.5 * delta
            action[8] += 0.5 * delta
        return action

    def close(self) -> None:
        return None


@dataclass
class _RandomPolicy:
    """Emits actions sampled from a fixed-seed Gaussian."""

    spec: VLASpec
    device: str
    action_dim: int = _MOCK_ACTION_DIM
    _rng: np.random.Generator | None = None

    def reset(self) -> None:
        seed_extra = self.spec.extra.get("seed", 0)
        self._rng = np.random.default_rng(_coerce_int(seed_extra, 0))

    def step(self, observation: Observation, instruction: str) -> NDArray[np.float32]:
        del observation, instruction
        if self._rng is None:
            self.reset()
        assert self._rng is not None
        return self._rng.standard_normal(self.action_dim).astype(np.float32) * 0.01

    def close(self) -> None:
        return None


def _resolve_action_dim(env_cfg: SimEnvironment) -> int:
    explicit = env_cfg.vla.extra.get("action_dim")
    if explicit is not None:
        return _coerce_int(explicit, _MOCK_ACTION_DIM)
    explicit_scene = env_cfg.scene.backend_options.get("action_dim")
    if explicit_scene is not None:
        return _coerce_int(explicit_scene, _MOCK_ACTION_DIM)
    # Defaults for registered scenes so the mock zero policy works
    # end-to-end without forcing the user to pass `action_dim` overrides.
    scene_default = _SCENE_DEFAULT_ACTION_DIM.get(env_cfg.scene.id)
    if scene_default is not None:
        return scene_default
    # Isaac Sim serves two sidecar layouts under one scene id:
    # lift_cube is 8-D (7 arm joint deltas + gripper); bowl_plate is the
    # LIBERO 7-D OSC-pose delta. The dim is layout-, not id-, determined.
    if env_cfg.scene.id == "isaac_sim":
        layout = env_cfg.scene.backend_options.get("layout", "lift_cube")
        return 7 if layout == "bowl_plate" else 8
    # GR1 tabletop scenes share a single 29-D action shape (right arm 7
    # + left arm 7 + waist 3 + right Fourier hand 6 + left Fourier
    # hand 6); special-case the prefix so we don't enumerate all 24
    # task ids in _SCENE_DEFAULT_ACTION_DIM.
    if env_cfg.scene.id.startswith("robocasa/gr1/"):
        return 29
    return _MOCK_ACTION_DIM


# Per-scene action dims used by mock policies (zero/random) when no override
# is supplied. Values match each scene adapter's underlying gym/robosuite env.
_SCENE_DEFAULT_ACTION_DIM: dict[str, int] = {
    "pusht": 2,
    "libero_spatial": 7,
    "libero_object": 7,
    "libero_goal": 7,
    "libero_10": 7,
    "metaworld": 4,
    "aloha_bimanual": 14,
    # isaac_sim is intentionally absent — its dim is layout-determined; see
    # the layout branch in _resolve_action_dim.
}


def _resolve_hold(
    env_cfg: SimEnvironment, action_dim: int
) -> tuple[NDArray[np.float32] | None, str, float, float, float]:
    extra = env_cfg.vla.extra or {}
    file_cfg = _load_controller_json(env_cfg.vla)
    hold = _float_list(extra.get("hold_targets"), n=action_dim)
    if hold is None:
        hold = _float_list(file_cfg.get("hold_targets"), n=action_dim)
    gait = str(extra.get("gait") or file_cfg.get("gait") or "hold")
    gait_amp = _coerce_float(
        extra.get("gait_amp") if extra.get("gait_amp") is not None else file_cfg.get("gait_amp"),
        0.0,
    )
    gait_hz = _coerce_float(
        extra.get("gait_hz") if extra.get("gait_hz") is not None else file_cfg.get("gait_hz"),
        1.5,
    )
    dt = _coerce_float(
        extra.get("dt") if extra.get("dt") is not None else file_cfg.get("dt"),
        1.0 / 30.0,
    )
    targets = np.asarray(hold, dtype=np.float32) if hold is not None else None
    return targets, gait, gait_amp, gait_hz, dt


@POLICIES.register("zero")
def _build_zero_policy(env_cfg: SimEnvironment) -> _ZeroPolicy:
    action_dim = _resolve_action_dim(env_cfg)
    extra = env_cfg.vla.extra or {}
    file_cfg = _load_controller_json(env_cfg.vla)
    if extra.get("action_dim") is None and file_cfg.get("n_dof") is not None:
        action_dim = _coerce_int(file_cfg.get("n_dof"), action_dim)
    hold, gait, gait_amp, gait_hz, dt = _resolve_hold(env_cfg, action_dim)
    if hold is not None:
        action_dim = int(hold.shape[0])
    return _ZeroPolicy(
        spec=env_cfg.vla,
        device="cpu",
        action_dim=action_dim,
        hold_targets=hold,
        gait=gait,
        gait_amp=gait_amp,
        gait_hz=gait_hz,
        dt=dt,
    )


@POLICIES.register("random")
def _build_random_policy(env_cfg: SimEnvironment) -> _RandomPolicy:
    return _RandomPolicy(
        spec=env_cfg.vla,
        device="cpu",
        action_dim=_resolve_action_dim(env_cfg),
    )
