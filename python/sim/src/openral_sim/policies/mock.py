"""Mock scene + policies — no physics, no weights.

Used by unit tests and as a wiring smoketest. The mock scene exposes a fixed
observation schema and a configurable action dimensionality, and the mock
policies emit deterministic actions so end-to-end tests can pass on CPU-only
runners without downloading any HF weights.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray
from openral_core.exceptions import ROSConfigError

from openral_sim.registry import POLICIES, SCENES
from openral_sim.rollout import StepResult

if TYPE_CHECKING:
    from openral_core import SceneSpec, SimEnvironment, TaskSpec, VLASpec

    from openral_sim.rollout import Observation


_MOCK_ACTION_DIM = 7
_MOCK_STATE_DIM = 8
_GO2_LEG_DOF = 12  # Go2 locomotion width; the scripted trot only applies at this DoF.


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

    In-tree factory key ``zero``. Used by unit tests and by scripted pose
    rSkills (Go2+Z1 arm ready). Not a learned VLA — ``hold_targets`` /
    ``gait`` / named ``poses`` come from ``VLASpec.extra`` (manifest
    ``policy_extras``) or ``controller.json``.
    """

    spec: VLASpec
    device: str
    action_dim: int = _MOCK_ACTION_DIM
    hold_targets: NDArray[np.float32] | None = None
    gait: str = "hold"
    gait_amp: float = 0.0
    gait_hz: float = 1.5
    dt: float = 1.0 / 30.0
    poses: dict[str, list[float]] = field(default_factory=dict)
    _default_hold: NDArray[np.float32] | None = None
    _tick: int = field(default=0)

    def __post_init__(self) -> None:
        if self._default_hold is None and self.hold_targets is not None:
            self._default_hold = np.array(self.hold_targets, dtype=np.float32, copy=True)

    def reset(self) -> None:
        self._tick = 0

    def set_named_pose(self, name: str | None) -> NDArray[np.float32] | None:
        """Select a named pose from ``poses``, or restore the load-time hold.

        ``name is None`` restores :attr:`_default_hold` (empty
        ``goal_params_json`` on a resident skill). Unknown names raise.
        """
        if name is None:
            self.hold_targets = (
                None
                if self._default_hold is None
                else np.array(self._default_hold, dtype=np.float32, copy=True)
            )
            return self.hold_targets
        key = str(name).strip().lower()
        if key not in self.poses:
            known = ", ".join(sorted(self.poses)) or "(none)"
            raise ROSConfigError(
                f"zero policy unknown pose {name!r}; known poses: {known}"
            )
        return self.set_arm_targets(self.poses[key])

    def set_arm_targets(self, arm: Sequence[float] | None) -> NDArray[np.float32] | None:
        """Overlay an arm (or full-width) vector onto the default hold.

        A vector as wide as ``action_dim`` replaces the hold. A shorter
        vector writes the **trailing** slots (Go2+Z1: 7-D arm+jaw onto
        19-D) so a locomotion-shaped leading pad stays put.
        """
        if arm is None:
            return self.set_named_pose(None)
        values = [float(v) for v in arm]
        base = (
            np.array(self._default_hold, dtype=np.float32, copy=True)
            if self._default_hold is not None
            else np.zeros(self.action_dim, dtype=np.float32)
        )
        if len(values) == int(base.shape[0]):
            self.hold_targets = np.asarray(values, dtype=np.float32)
            return self.hold_targets
        if len(values) > int(base.shape[0]):
            raise ROSConfigError(
                f"zero policy arm length {len(values)} exceeds action_dim {int(base.shape[0])}"
            )
        base[-len(values) :] = np.asarray(values, dtype=np.float32)
        self.hold_targets = base
        return self.hold_targets

    def step(self, observation: Observation, instruction: str) -> NDArray[np.float32]:
        del observation, instruction
        self._tick += 1
        if self.hold_targets is not None:
            action = np.array(self.hold_targets, dtype=np.float32, copy=True)
        else:
            action = np.zeros(self.action_dim, dtype=np.float32)
        if self.gait == "trot" and self.gait_amp and action.shape[0] >= _GO2_LEG_DOF:
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


def _named_poses(raw: object) -> dict[str, list[float]]:
    """Parse a ``poses: {name: [floats]}`` mapping; skip ill-typed entries."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[float]] = {}
    for name, values in raw.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(values, list) or not values:
            continue
        try:
            out[name.strip().lower()] = [float(v) for v in values]
        except (TypeError, ValueError):
            continue
    return out


def _goal_params_mapping(
    goal_params_json: str | dict[str, object] | None,
) -> dict[str, object] | None:
    if goal_params_json is None:
        return None
    if isinstance(goal_params_json, dict):
        return goal_params_json
    text = str(goal_params_json).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ROSConfigError(f"zero policy goal_params_json is not JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ROSConfigError(
            f"zero policy goal_params_json must be an object, got {type(parsed).__name__}"
        )
    return parsed


def apply_zero_pose_override(
    target: object,
    goal_params_json: str | dict[str, object] | None,
) -> NDArray[np.float32] | None:
    """Push a named / explicit arm pose onto a ``zero`` adapter.

    Looks for ``set_named_pose`` / ``set_arm_targets`` on ``target`` or
    ``target._adapter``. Empty payload restores the load-time hold. A 7-D
    ``arm`` vector wins over ``pose``. No-ops when the adapter is not a
    scripted hold (so the runner can call this next to the rsl-rl joystick
    override).

    Example:
        >>> class _Stub:
        ...     def set_named_pose(self, name):
        ...         self.pose = name
        ...         return None
        ...     def set_arm_targets(self, arm):
        ...         self.arm = list(arm)
        ...         return None
        >>> stub = _Stub()
        >>> apply_zero_pose_override(stub, {"pose": "ready"})
        >>> stub.pose
        'ready'
    """
    setter_pose = getattr(target, "set_named_pose", None)
    setter_arm = getattr(target, "set_arm_targets", None)
    if setter_pose is None:
        nested = getattr(target, "_adapter", None)
        setter_pose = getattr(nested, "set_named_pose", None)
        setter_arm = getattr(nested, "set_arm_targets", None)
    extra = _goal_params_mapping(goal_params_json)
    result: NDArray[np.float32] | None = None
    if extra is None or (extra.get("arm") is None and extra.get("pose") is None):
        if callable(setter_pose):
            result = setter_pose(None)
    elif extra.get("arm") is not None:
        if not callable(setter_arm):
            result = None
        elif not isinstance(extra["arm"], list):
            raise ROSConfigError(
                f"zero policy goal_params.arm must be a list, got {extra['arm']!r}"
            )
        else:
            result = setter_arm(extra["arm"])
    elif extra.get("pose") is not None:
        if not callable(setter_pose):
            result = None
        elif not isinstance(extra["pose"], str):
            raise ROSConfigError(
                f"zero policy goal_params.pose must be a string, got {extra['pose']!r}"
            )
        else:
            result = setter_pose(extra["pose"])
    return result


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
    poses = _named_poses(extra.get("poses"))
    if not poses:
        poses = _named_poses(file_cfg.get("poses"))
    policy = _ZeroPolicy(
        spec=env_cfg.vla,
        device="cpu",
        action_dim=action_dim,
        hold_targets=hold,
        gait=gait,
        gait_amp=gait_amp,
        gait_hz=gait_hz,
        dt=dt,
        poses=poses,
    )
    default_pose = extra.get("default_pose") or file_cfg.get("default_pose")
    if isinstance(default_pose, str) and default_pose.strip() and poses:
        policy.set_named_pose(default_pose)
        policy._default_hold = (
            None
            if policy.hold_targets is None
            else np.array(policy.hold_targets, dtype=np.float32, copy=True)
        )
    return policy


@POLICIES.register("random")
def _build_random_policy(env_cfg: SimEnvironment) -> _RandomPolicy:
    return _RandomPolicy(
        spec=env_cfg.vla,
        device="cpu",
        action_dim=_resolve_action_dim(env_cfg),
    )
