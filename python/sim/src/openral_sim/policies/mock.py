"""Mock scene + policies — no physics, no weights.

Used by unit tests and as a wiring smoketest. The mock scene exposes a fixed
observation schema and a configurable action dimensionality, and the mock
policies emit deterministic actions so end-to-end tests can pass on CPU-only
runners without downloading any HF weights.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
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
_GO2_LEG_DOF = 12  # Go2 locomotion width; the scripted trot / hop only apply here.

# Measured 2026-09-19 on the go2_walk floor with HAL walk PD (1 rad saturates
# ctrlrange), policy_dt=0.02. A 0.16 s extend aborted at takeoff (calves still
# ~−1.4 vs cmd −0.86) so the dog only bounced (~0.12 m COM, foot ≈0.17 m).
# Crouch-extend-tuck-land lets the calves finish the push, then folds the
# feet up in flight. Manifest ``policy_extras.jump_*`` may override these.
# mjlab hop ONNX at trained scale 0.25 never commands this much calf travel.
_GO2_JUMP_CROUCH: tuple[float, ...] = (
    0.1,
    1.70,
    -2.65,
    -0.1,
    1.70,
    -2.65,
    0.1,
    1.90,
    -2.65,
    -0.1,
    1.90,
    -2.65,
)
_GO2_JUMP_EXTEND: tuple[float, ...] = (
    0.1,
    0.05,
    -0.84,
    -0.1,
    0.05,
    -0.84,
    0.1,
    0.10,
    -0.84,
    -0.1,
    0.10,
    -0.84,
)
_GO2_JUMP_TUCK: tuple[float, ...] = (
    0.1,
    1.40,
    -2.30,
    -0.1,
    1.40,
    -2.30,
    0.1,
    1.60,
    -2.30,
    -0.1,
    1.60,
    -2.30,
)
# Land / recover. Same 12-D as ``GO2_HOP_JOINT_TARGETS``; pinned in
# ``test_jump_stand_matches_hal_hop_stand`` — do not invent a fifth row.
_GO2_JUMP_STAND: tuple[float, ...] = (
    0.1,
    0.8,
    -1.5,
    -0.1,
    0.8,
    -1.5,
    0.1,
    1.0,
    -1.5,
    -0.1,
    1.0,
    -1.5,
)
_JUMP_CROUCH_S: float = 0.30
_JUMP_EXTEND_S: float = 0.24
_JUMP_TUCK_S: float = 0.22
_JUMP_RECOVER_S: float = 0.40


def _jump_phase_ticks(
    *,
    dt: float,
    crouch_s: float = _JUMP_CROUCH_S,
    extend_s: float = _JUMP_EXTEND_S,
    tuck_s: float = _JUMP_TUCK_S,
    recover_s: float = _JUMP_RECOVER_S,
) -> tuple[int, int, int, int]:
    """Integer crouch / extend / tuck / recover tick counts for ``dt``."""
    if dt <= 0.0:
        return 1, 1, 0, 1
    crouch = max(1, round(float(crouch_s) / dt))
    extend = max(1, round(float(extend_s) / dt))
    tuck = 0 if float(tuck_s) <= 0.0 else max(1, round(float(tuck_s) / dt))
    recover = max(1, round(float(recover_s) / dt))
    return crouch, extend, tuck, recover


def _jump_leg_targets(
    tick: int,
    *,
    dt: float,
    crouch: NDArray[np.float32] | Sequence[float] | None = None,
    extend: NDArray[np.float32] | Sequence[float] | None = None,
    tuck: NDArray[np.float32] | Sequence[float] | None = None,
    stand: NDArray[np.float32] | Sequence[float] | None = None,
    crouch_s: float = _JUMP_CROUCH_S,
    extend_s: float = _JUMP_EXTEND_S,
    tuck_s: float = _JUMP_TUCK_S,
    recover_s: float = _JUMP_RECOVER_S,
) -> NDArray[np.float32]:
    """One 12-D crouch / extend / tuck / land row for scripted Go2 hop.

    ``tick`` is 1-based (``_ZeroPolicy.step`` increments first). Phase
    lengths come from the measured go2_walk floor rollout. A zero
    ``tuck_s`` skips the flight fold.
    """
    n_crouch, n_extend, n_tuck, n_recover = _jump_phase_ticks(
        dt=dt,
        crouch_s=crouch_s,
        extend_s=extend_s,
        tuck_s=tuck_s,
        recover_s=recover_s,
    )
    crouch_row = np.asarray(_GO2_JUMP_CROUCH if crouch is None else crouch, dtype=np.float32)
    extend_row = np.asarray(_GO2_JUMP_EXTEND if extend is None else extend, dtype=np.float32)
    tuck_row = np.asarray(_GO2_JUMP_TUCK if tuck is None else tuck, dtype=np.float32)
    stand_row = np.asarray(_GO2_JUMP_STAND if stand is None else stand, dtype=np.float32)
    period = n_crouch + n_extend + n_tuck + n_recover
    index = max(tick - 1, 0) % period
    if index < n_crouch:
        return crouch_row
    if index < n_crouch + n_extend:
        return extend_row
    if n_tuck and index < n_crouch + n_extend + n_tuck:
        return tuck_row
    return stand_row


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
    """N-D scripted hold (optional trot / hop). Defaults to zeros when no targets.

    In-tree factory key ``zero``. Used by unit tests and by scripted pose
    rSkills (Go2+Z1 arm ready, Go2 hop). Not a learned VLA — ``hold_targets``
    / ``gait`` / named ``poses`` / ``jump_*`` come from ``VLASpec.extra``
    (manifest ``policy_extras``) or ``controller.json``.
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
    jump_crouch: NDArray[np.float32] | None = None
    jump_extend: NDArray[np.float32] | None = None
    jump_tuck: NDArray[np.float32] | None = None
    jump_crouch_s: float = _JUMP_CROUCH_S
    jump_extend_s: float = _JUMP_EXTEND_S
    jump_tuck_s: float = _JUMP_TUCK_S
    jump_recover_s: float = _JUMP_RECOVER_S
    _default_hold: NDArray[np.float32] | None = None
    _tick: int = field(default=0)

    def __post_init__(self) -> None:
        if self._default_hold is None and self.hold_targets is not None:
            self._default_hold = np.array(self.hold_targets, dtype=np.float32, copy=True)
        if self.jump_crouch is None:
            self.jump_crouch = np.asarray(_GO2_JUMP_CROUCH, dtype=np.float32)
        if self.jump_extend is None:
            self.jump_extend = np.asarray(_GO2_JUMP_EXTEND, dtype=np.float32)
        if self.jump_tuck is None:
            self.jump_tuck = np.asarray(_GO2_JUMP_TUCK, dtype=np.float32)

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
            raise ROSConfigError(f"zero policy unknown pose {name!r}; known poses: {known}")
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
        if self.gait == "jump" and action.shape[0] >= _GO2_LEG_DOF:
            stand = (
                action[:_GO2_LEG_DOF]
                if self.hold_targets is not None and self.hold_targets.shape[0] >= _GO2_LEG_DOF
                else None
            )
            action[:_GO2_LEG_DOF] = _jump_leg_targets(
                self._tick,
                dt=self.dt,
                crouch=self.jump_crouch,
                extend=self.jump_extend,
                tuck=self.jump_tuck,
                stand=stand,
                crouch_s=self.jump_crouch_s,
                extend_s=self.jump_extend_s,
                tuck_s=self.jump_tuck_s,
                recover_s=self.jump_recover_s,
            )
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


def _leg_row(
    extra: Mapping[str, object], file_cfg: Mapping[str, object], key: str
) -> NDArray[np.float32] | None:
    """Optional 12-D jump pose from ``policy_extras`` or ``controller.json``."""
    raw = extra.get(key)
    if raw is None:
        raw = file_cfg.get(key)
    values = _float_list(raw, n=_GO2_LEG_DOF)
    if values is None:
        return None
    return np.asarray(values, dtype=np.float32)


def _resolve_jump(
    extra: Mapping[str, object], file_cfg: Mapping[str, object]
) -> tuple[
    NDArray[np.float32] | None,
    NDArray[np.float32] | None,
    NDArray[np.float32] | None,
    float,
    float,
    float,
    float,
]:
    """Crouch / extend / tuck poses and phase times for ``gait: jump``."""

    def _seconds(key: str, default: float) -> float:
        raw = extra.get(key)
        if raw is None:
            raw = file_cfg.get(key)
        return _coerce_float(raw, default)

    return (
        _leg_row(extra, file_cfg, "jump_crouch"),
        _leg_row(extra, file_cfg, "jump_extend"),
        _leg_row(extra, file_cfg, "jump_tuck"),
        _seconds("jump_crouch_s", _JUMP_CROUCH_S),
        _seconds("jump_extend_s", _JUMP_EXTEND_S),
        _seconds("jump_tuck_s", _JUMP_TUCK_S),
        _seconds("jump_recover_s", _JUMP_RECOVER_S),
    )


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
        ...
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
    jump_crouch, jump_extend, jump_tuck, crouch_s, extend_s, tuck_s, recover_s = _resolve_jump(
        extra, file_cfg
    )
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
        jump_crouch=jump_crouch,
        jump_extend=jump_extend,
        jump_tuck=jump_tuck,
        jump_crouch_s=crouch_s,
        jump_extend_s=extend_s,
        jump_tuck_s=tuck_s,
        jump_recover_s=recover_s,
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
