"""Isaac Lab / Unitree rsl-rl ONNX locomotion adapter.

Selected by the rSkill manifest ``model_family: "rsl_rl_onnx"``. This is a
proprio-only joint-position policy — **not** a VLM, and **not** SmolVLA.
SmolVLA cannot load ``policy.onnx``.

First customer: ``hf://diasAiMaster/unitree-go2-velocity-flat`` (45-D,
history 1, projected gravity). Second: mjlab hop
(``rskills/rsl-rl-onnx-go2-hop-flat``) — 47-D × 10 frames = 470-D,
term-major, ``gait_phase_2`` + euler RPY, action scale 0.25 (planted
crouch on this HAL). Third: gym ``spring_jump``
(``rskills/rsl-rl-onnx-go2-spring-jump``) — same 470-D width, **frame-
major** history with zero warmup, ``constants`` + ``joystick_buttons``
(jump trigger A). Observation term order, scales, history length,
``history_layout``, ``default_joint_pos``, action scale, and
``joint_ids_map`` are read from ``params/deploy.yaml``. Keys are never
invented. Hop / jump weights stay out of this repo (upstream has no
license); the rSkill fetches ``policy.onnx`` via ``policy_extras.onnx_url``
into ``~/.cache/openral``.

Velocity command
----------------
Isaac Lab ``velocity_commands`` is a 3-D joystick ``[vx, vy, yaw_rate]``.
The reasoner prompt is natural language and is **not** mapped onto that
vector. YAML ``policy_extras.velocity_commands`` (default ``[0.5, 0.0, 0.0]``)
is the load-time fallback so a locomotion tick can run without a nav stack.

Per-call override (does not require editing the rSkill YAML), highest wins:

1. ``observation["velocity_commands"]`` on this ``step()`` (runner / verify).
2. ``ExecuteRskill.goal_params_json`` ``{"velocity_commands": [vx, vy, yaw]}``
   applied onto the resident skill (see :func:`velocity_override_from_goal_params`).
3. ``VLASpec.extra["velocity_commands"]`` merged over the YAML extras at
   ``make_policy`` time.

Empty extras / empty goal_params keep the YAML default.

Coast to stand
--------------
Idle-holding a mid-gait waypoint after ``max_execution_s`` dumps the Go2
(frozen stride cannot balance). Last ``policy_extras.coast_to_stand_s``
seconds of the episode budget command ``[0, 0, 0]`` so the ONNX itself
stands the dog; ``horizon_s`` (when set) then succeeds instead of aborting
``deadline_exceeded``. Unset ``coast_to_stand_s`` on this family defaults
to 3.0 s; ``0`` disables. Budget is ``horizon_s`` else
``latency_budget.max_execution_s``.

Action
------
``q_des = default_joint_pos + scale * raw_action``, 12-D ``JOINT_POSITION``
only — no cartesian representation.

Joint order
-----------
``deploy.yaml``'s ``joint_ids_map`` is the **real-robot** permutation between
the policy's own joint order and the Unitree SDK's (``FR, FL, RR, RL`` against
menagerie's ``FL, FR, RL, RR``). A MuJoCo twin already speaks the policy's
order, so the map is not applied unless the manifest sets
``policy_extras.joint_order: unitree_sdk``. Applying it to a sim twin mirrors
every leg command and the robot falls within ~2 s — see ``_apply_joint_order``
for the measurements.
"""

from __future__ import annotations

import hashlib
import math
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import structlog
import yaml
from numpy.typing import NDArray
from openral_core.exceptions import ROSConfigError, ROSRuntimeError
from openral_core.schemas import RSkillManifest
from openral_observability import inference_span

from openral_sim.policies._policy_loading import load_manifest_for_spec
from openral_sim.registry import POLICIES

if TYPE_CHECKING:
    from openral_core import VLASpec

    from openral_sim.rollout import Observation

log = structlog.get_logger(__name__)

RSL_RL_ONNX_FAMILY: Final[str] = "rsl_rl_onnx"
"""Canonical ``ModelFamily`` / ``@POLICIES.register`` token Acquire must put
in ``rskill.yaml`` (``model_family: rsl_rl_onnx``)."""

_DEFAULT_ONNX_FILENAME: Final[str] = "policy.onnx"
_DEFAULT_DEPLOY_REL: Final[str] = "params/deploy.yaml"
_DEFAULT_VELOCITY_COMMANDS: tuple[float, float, float] = (0.5, 0.0, 0.0)
_STAND_VELOCITY_COMMANDS: tuple[float, float, float] = (0.0, 0.0, 0.0)
_DEFAULT_COAST_TO_STAND_S: float = 3.0
_GRAVITY_WORLD: NDArray[np.float32] = np.array([0.0, 0.0, -1.0], dtype=np.float32)
_OBS_FALLBACK_WARNED: set[str] = set()

# Whose joint order the caller feeds this policy. `deploy.yaml`'s
# `joint_ids_map` converts between the policy's own order and the Unitree SDK's
# real-robot order; a MuJoCo twin in menagerie order needs no conversion.
# See `_apply_joint_order` for the measured consequence of getting this wrong.
_JOINT_ORDERS: Final[frozenset[str]] = frozenset({"policy", "unitree_sdk"})
_JOINT_ORDER_DEFAULT: Final[str] = "policy"

# Isaac Lab term widths used only when ``deploy.yaml`` gives a scalar scale.
# Term *names* still come from the YAML observation block.
_ISAAC_TERM_WIDTHS: Final[dict[str, int]] = {
    "base_ang_vel": 3,
    "base_ang_vel_B": 3,
    "projected_gravity": 3,
    "velocity_commands": 3,
    "joint_pos_rel": 12,
    "joint_pos": 12,
    "joint_vel_rel": 12,
    "joint_vel": 12,
    "last_action": 12,
    "gait_phase_2": 2,
    "eulerZYX_rpy": 3,
}
_HISTORY_ORDERS: Final[frozenset[str]] = frozenset({"oldest_first", "newest_first"})
_HISTORY_WARMUPS: Final[frozenset[str]] = frozenset({"repeat_first", "zero"})
_HISTORY_LAYOUTS: Final[frozenset[str]] = frozenset({"term_major", "frame_major"})
_HISTORY_ORDER_DEFAULT: Final[str] = "oldest_first"
_HISTORY_WARMUP_DEFAULT: Final[str] = "repeat_first"
_HISTORY_LAYOUT_DEFAULT: Final[str] = "term_major"
_TWO_PI: Final[float] = 2.0 * math.pi


@dataclass(frozen=True, slots=True)
class RslRlOnnxDeployConfig:
    """Parsed ``params/deploy.yaml`` — keys taken from the Hub file, not invented.

    Attributes:
        observation_terms: Ordered ``(name, scale_vector)`` pairs from the
            YAML ``observations:`` block (dict insertion order).
        default_joint_pos: Robot-order default pose (menagerie-like stand).
        action_scale: Per-DoF ``JointPositionAction`` scale.
        joint_ids_map: Policy slot ``i`` reads/writes robot joint
            ``joint_ids_map[i]``. Identity when the YAML omits the key.
        step_dt: Control period from the YAML (informational).
        term_history_lengths: Per-term history, YAML order. Walk is all 1s;
            mjlab hop is all 10s.
        history_order: ``oldest_first`` or ``newest_first``; must be shared.
        history_warmup: ``repeat_first`` or ``zero``; must be shared.
        history_layout: ``term_major`` (mjlab hop) or ``frame_major``
            (Isaac Gym ``frame_stack`` / spring_jump).
        gait_cycle_s: ``gait_phase_2`` cycle time, or ``None`` when absent.
        action_clip: Symmetric clip on the raw ONNX action, or ``None``.
        constant_terms: YAML ``constants`` vectors keyed by term name.
    """

    observation_terms: tuple[tuple[str, NDArray[np.float32]], ...]
    default_joint_pos: NDArray[np.float32]
    action_scale: NDArray[np.float32]
    joint_ids_map: NDArray[np.intp]
    step_dt: float
    term_history_lengths: tuple[int, ...]
    history_order: str = _HISTORY_ORDER_DEFAULT
    history_warmup: str = _HISTORY_WARMUP_DEFAULT
    history_layout: str = _HISTORY_LAYOUT_DEFAULT
    gait_cycle_s: float | None = None
    action_clip: float | None = None
    constant_terms: tuple[tuple[str, NDArray[np.float32]], ...] = ()

    @property
    def observation_dim(self) -> int:
        """Concatenated rsl-rl observation width, including history."""
        return int(
            sum(
                scale.shape[0] * int(hist)
                for (_name, scale), hist in zip(
                    self.observation_terms, self.term_history_lengths, strict=True
                )
            )
        )

    @property
    def frame_dim(self) -> int:
        """One-tick concatenated width before history stacking."""
        return int(sum(scale.shape[0] for _name, scale in self.observation_terms))

    @property
    def action_dim(self) -> int:
        """Joint-position action width (12 for Unitree Go2)."""
        return int(self.action_scale.shape[0])


def load_rsl_rl_deploy_yaml(path: Path | str) -> RslRlOnnxDeployConfig:
    """Parse an Isaac Lab / mjlab ``params/deploy.yaml``.

    Args:
        path: Filesystem path to the Hub ``params/deploy.yaml``.

    Returns:
        A :class:`RslRlOnnxDeployConfig` whose observation terms follow the
        YAML key order.

    Raises:
        ROSConfigError: Missing file, missing required keys, or a
            ``joint_ids_map`` that is not a permutation of ``0..n-1``.

    Example:
        >>> from pathlib import Path
        >>> import tempfile, yaml
        >>> raw = {
        ...     "joint_ids_map": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        ...     "default_joint_pos": [0.0, 0.9, -1.8] * 4,
        ...     "actions": {"JointPositionAction": {"scale": [0.5] * 12}},
        ...     "observations": {
        ...         "base_ang_vel": {"scale": [1.0, 1.0, 1.0]},
        ...         "projected_gravity": {"scale": [1.0, 1.0, 1.0]},
        ...         "velocity_commands": {"scale": [1.0, 1.0, 1.0]},
        ...         "joint_pos_rel": {"scale": [1.0] * 12},
        ...         "joint_vel_rel": {"scale": [1.0] * 12},
        ...         "last_action": {"scale": [1.0] * 12},
        ...     },
        ... }
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "deploy.yaml"
        ...     p.write_text(yaml.safe_dump(raw))
        ...     cfg = load_rsl_rl_deploy_yaml(p)
        >>> cfg.observation_dim
        45
        >>> cfg.action_dim
        12
    """
    yaml_path = Path(path)
    if not yaml_path.is_file():
        raise ROSConfigError(f"rsl_rl_onnx: deploy.yaml not found at {yaml_path}")
    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ROSConfigError(f"rsl_rl_onnx: {yaml_path} is not a YAML mapping")

    default = _float_vec(loaded.get("default_joint_pos"), name="default_joint_pos")
    actions = loaded.get("actions")
    if not isinstance(actions, dict) or "JointPositionAction" not in actions:
        raise ROSConfigError(f"rsl_rl_onnx: {yaml_path} has no actions.JointPositionAction block")
    jp = actions["JointPositionAction"]
    if not isinstance(jp, dict):
        raise ROSConfigError(
            f"rsl_rl_onnx: {yaml_path} actions.JointPositionAction is not a mapping"
        )
    scale = _broadcast_scale(jp.get("scale"), width=default.shape[0], name="action.scale")
    if scale.shape[0] != default.shape[0]:
        raise ROSConfigError(
            f"rsl_rl_onnx: action scale dim {scale.shape[0]} != "
            f"default_joint_pos dim {default.shape[0]}"
        )

    n = int(default.shape[0])
    raw_map = loaded.get("joint_ids_map")
    joint_ids_map = np.arange(n, dtype=np.intp) if raw_map is None else _joint_ids_map(raw_map, n=n)

    observations = loaded.get("observations")
    if not isinstance(observations, dict) or not observations:
        raise ROSConfigError(f"rsl_rl_onnx: {yaml_path} has no observations: block")
    terms, hist_lengths, history_order, history_warmup, gait_cycle_s = _parse_observation_terms(
        observations
    )
    history_layout = _history_layout(loaded)
    if history_layout == "frame_major" and len(set(hist_lengths)) > 1:
        raise ROSConfigError(
            f"rsl_rl_onnx: history_layout=frame_major requires a uniform "
            f"history_length, got {hist_lengths}"
        )

    step_dt_raw = loaded.get("step_dt", 0.02)
    try:
        step_dt = float(step_dt_raw)
    except (TypeError, ValueError) as exc:
        raise ROSConfigError(f"rsl_rl_onnx: step_dt {step_dt_raw!r} is not a float") from exc

    return RslRlOnnxDeployConfig(
        observation_terms=tuple(terms),
        default_joint_pos=default,
        action_scale=scale,
        joint_ids_map=joint_ids_map,
        step_dt=step_dt,
        term_history_lengths=tuple(hist_lengths),
        history_order=history_order,
        history_warmup=history_warmup,
        history_layout=history_layout,
        gait_cycle_s=gait_cycle_s,
        action_clip=_action_clip(loaded, jp),
        constant_terms=_constant_terms(observations),
    )


def resolve_velocity_commands(
    extra: dict[str, object],
    *,
    default: tuple[float, float, float] = _DEFAULT_VELOCITY_COMMANDS,
) -> NDArray[np.float32]:
    """Read ``[vx, vy, yaw_rate]`` from ``policy_extras`` / ``VLASpec.extra``.

    The reasoner prompt is ignored. Missing / empty extras fall back to
    ``default`` (a modest forward walk). Per-call overrides belong in
    :func:`velocity_override_from_goal_params` or ``obs["velocity_commands"]``.

    Args:
        extra: Manifest ``policy_extras`` merged with ``VLASpec.extra``.
        default: Fallback joystick when the extras omit the key.

    Returns:
        Float32 vector of length 3.

    Raises:
        ROSConfigError: The extras value is present but not a 3-vector.

    Example:
        >>> resolve_velocity_commands({"velocity_commands": [1.0, 0.0, 0.2]})
        array([1. , 0. , 0.2], dtype=float32)
        >>> resolve_velocity_commands({})
        array([0.5, 0. , 0. ], dtype=float32)
    """
    raw = extra.get("velocity_commands", extra.get("velocity_command"))
    if raw is None:
        return np.asarray(default, dtype=np.float32)
    return _as_velocity_command_vec(raw)


def in_coast_to_stand_window(
    *,
    elapsed_s: float,
    budget_s: float | None,
    coast_to_stand_s: float | None,
) -> bool:
    """True when the remaining episode budget is the stand-down window."""
    if coast_to_stand_s is None or budget_s is None:
        return False
    coast = float(coast_to_stand_s)
    budget = float(budget_s)
    if coast <= 0.0 or budget <= 0.0:
        return False
    return float(elapsed_s) >= budget - coast


def coast_velocity_commands(
    commanded: Sequence[float],
    *,
    elapsed_s: float,
    budget_s: float | None,
    coast_to_stand_s: float | None,
) -> NDArray[np.float32]:
    """Keep ``commanded`` until the coast window, then return stand ``[0,0,0]``.

    Args:
        commanded: Isaac joystick ``[vx, vy, yaw_rate]``.
        elapsed_s: Time since the episode started.
        budget_s: ``horizon_s`` or ``max_execution_s``.
        coast_to_stand_s: Trailing stand-down duration. ``None`` / ``<=0`` keeps
            ``commanded``.

    Example:
        >>> coast_velocity_commands([0.5, 0.0, 0.0], elapsed_s=54.0,
        ...     budget_s=57.0, coast_to_stand_s=3.0)
        array([0., 0., 0.], dtype=float32)
        >>> coast_velocity_commands([0.5, 0.0, 0.0], elapsed_s=50.0,
        ...     budget_s=57.0, coast_to_stand_s=3.0)
        array([0.5, 0. , 0. ], dtype=float32)
    """
    vec = _as_velocity_command_vec(commanded)
    if in_coast_to_stand_window(
        elapsed_s=elapsed_s,
        budget_s=budget_s,
        coast_to_stand_s=coast_to_stand_s,
    ):
        return np.asarray(_STAND_VELOCITY_COMMANDS, dtype=np.float32)
    return vec


def resolve_coast_to_stand_s(
    extra: dict[str, object],
    *,
    family: str | None = None,
) -> float | None:
    """Trailing stand-down seconds from extras.

    Unset on ``rsl_rl_onnx`` defaults to 3.0 so a Hub walk still coasts.
    ``0`` / ``false`` disables.
    """
    raw = extra.get("coast_to_stand_s")
    if raw is None:
        return _DEFAULT_COAST_TO_STAND_S if family == RSL_RL_ONNX_FAMILY else None
    if raw is False:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0.0 else None


def resolve_coast_budget_s(
    extra: dict[str, object],
    *,
    horizon_s: float | None = None,
    max_execution_s: float | None = None,
) -> float | None:
    """Episode budget the coast window is measured against.

    ``policy_extras.horizon_s`` wins, then the caller ``horizon_s``, then
    ``max_execution_s`` from the manifest latency budget.
    """
    for raw in (extra.get("horizon_s"), horizon_s, max_execution_s):
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0.0:
            return value
    return None


def velocity_override_from_goal_params(
    goal_params_json: str | dict[str, object] | None,
) -> NDArray[np.float32] | None:
    """Parse an ``ExecuteRskill.goal_params_json`` velocity override.

    Empty / missing ``goal_params_json`` returns ``None`` so the caller keeps
    the YAML / ``policy_extras`` default. A present ``velocity_commands``
    3-vector wins over that default without editing the rSkill YAML.

    Args:
        goal_params_json: Raw goal JSON string, already-decoded mapping, or
            ``None``.

    Returns:
        Float32 ``[vx, vy, yaw_rate]`` or ``None`` when the payload omits
        the key.

    Raises:
        ROSConfigError: JSON is malformed or the value is not a 3-vector.

    Example:
        >>> velocity_override_from_goal_params('{"velocity_commands": [1, 0, 0.2]}')
        array([1. , 0. , 0.2], dtype=float32)
        >>> velocity_override_from_goal_params("") is None
        True
    """
    extra = _goal_params_mapping(goal_params_json)
    if extra is None:
        return None
    raw = extra.get("velocity_commands", extra.get("velocity_command"))
    if raw is None:
        return None
    return _as_velocity_command_vec(raw)


def apply_velocity_command_override(
    target: object,
    goal_params_json: str | dict[str, object] | None,
) -> NDArray[np.float32] | None:
    """Push a per-goal joystick onto an adapter or rSkill shim.

    Looks for ``set_velocity_commands`` on ``target`` and, if missing, on
    ``target._adapter``. ``None`` (empty goal_params) restores the YAML
    default on a resident skill so a later execute/verify call is not stuck
    on the previous override.

    Args:
        target: ``_RslRlOnnxAdapter`` or the runner's ``_PolicyAdapterSkill``.
        goal_params_json: ``ExecuteRskill.goal_params_json`` payload.

    Returns:
        The override vector, or ``None`` when the payload omitted the key
        (default restored).

    Example:
        >>> class _Stub:
        ...     def set_velocity_commands(self, commands):
        ...         self.commands = commands
        >>> stub = _Stub()
        >>> apply_velocity_command_override(stub, {"velocity_commands": [0.8, 0, 0]})
        array([0.8, 0. , 0. ], dtype=float32)
        >>> stub.commands.tolist()
        [0.8, 0.0, 0.0]
    """
    override = velocity_override_from_goal_params(goal_params_json)
    setter = getattr(target, "set_velocity_commands", None)
    if setter is None:
        nested = getattr(target, "_adapter", None)
        setter = getattr(nested, "set_velocity_commands", None)
    if callable(setter):
        setter(override)
    return override


def projected_gravity_from_quat_xyzw(quat_xyzw: NDArray[np.float32]) -> NDArray[np.float32]:
    """Express world gravity ``[0, 0, -1]`` in the base frame (Isaac Lab).

    ``quat_xyzw`` is the world-from-base orientation (OpenRAL ``Pose6D``).

    Example:
        >>> g = projected_gravity_from_quat_xyzw(np.array([0.0, 0.0, 0.0, 1.0], np.float32))
        >>> np.allclose(g, [0.0, 0.0, -1.0])
        True
    """
    q = np.asarray(quat_xyzw, dtype=np.float32).reshape(-1)
    if q.shape != (4,):
        raise ROSConfigError(f"rsl_rl_onnx: quat_xyzw must be length 4, got {q.shape}")
    rotation = _quat_xyzw_to_rotation(q)
    return rotation.T @ _GRAVITY_WORLD


def euler_rpy_from_quat_xyzw(quat_xyzw: NDArray[np.float32]) -> NDArray[np.float32]:
    """Roll-pitch-yaw from ``quat_xyzw`` (hop ``eulerZYX_rpy`` term).

    Matches ``PolicySlot::quatToRpy`` in
    `Renkunzhao/legged_rl_deploy` ``src/policy_slot.cpp``: aerospace
    intrinsic XYZ / extrinsic ZYX. Identity quaternion is zeros.

    Example:
        >>> rpy = euler_rpy_from_quat_xyzw(np.array([0.0, 0.0, 0.0, 1.0], np.float32))
        >>> np.allclose(rpy, [0.0, 0.0, 0.0])
        True
    """
    q = np.asarray(quat_xyzw, dtype=np.float32).reshape(-1)
    if q.shape != (4,):
        raise ROSConfigError(f"rsl_rl_onnx: quat_xyzw must be length 4, got {q.shape}")
    x, y, z, w = (float(v) for v in q)
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x))))
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return np.array([roll, pitch, yaw], dtype=np.float32)


def gait_phase_2(*, step_index: int, step_dt: float, cycle_s: float) -> NDArray[np.float32]:
    """``[sin(2π t / T), cos(2π t / T)]`` at policy tick ``step_index``.

    ``t = step_index * step_dt``. Tick 0 is ``[0, 1]``. The hop deploy
    clock is ``loop_cnt * ll_dt / cycle_time`` at the policy tick, which
    is the same series when ``policy_dt == step_dt``.

    Example:
        >>> gait_phase_2(step_index=0, step_dt=0.02, cycle_s=1.5).tolist()
        [0.0, 1.0]
    """
    if cycle_s <= 0.0:
        raise ROSConfigError(f"rsl_rl_onnx: gait cycle must be > 0, got {cycle_s}")
    phase = float(step_index) * float(step_dt) / float(cycle_s)
    angle = _TWO_PI * phase
    return np.array([math.sin(angle), math.cos(angle)], dtype=np.float32)


def build_rsl_rl_observation(
    *,
    config: RslRlOnnxDeployConfig,
    joint_pos: NDArray[np.float32],
    joint_vel: NDArray[np.float32],
    base_ang_vel: NDArray[np.float32],
    projected_gravity: NDArray[np.float32],
    velocity_commands: NDArray[np.float32],
    last_action: NDArray[np.float32],
    gait_phase: NDArray[np.float32] | None = None,
    euler_rpy: NDArray[np.float32] | None = None,
    joystick_buttons: NDArray[np.float32] | None = None,
) -> NDArray[np.float32]:
    """Concatenate one rsl-rl observation **frame** in ``deploy.yaml`` term order.

    Joint channels are remapped with ``config.joint_ids_map`` (policy slot
    ``i`` reads robot joint ``map[i]``). Other terms are used as given.
    History stacking is :func:`stack_rsl_rl_term_major_history` — this
    helper always returns ``config.frame_dim``.

    Example:
        >>> raw = {
        ...     "joint_ids_map": list(range(12)),
        ...     "default_joint_pos": [0.0, 0.9, -1.8] * 4,
        ...     "actions": {"JointPositionAction": {"scale": [0.5] * 12}},
        ...     "observations": {
        ...         "base_ang_vel": {"scale": [1.0, 1.0, 1.0]},
        ...         "projected_gravity": {"scale": [1.0, 1.0, 1.0]},
        ...         "velocity_commands": {"scale": [1.0, 1.0, 1.0]},
        ...         "joint_pos_rel": {"scale": [1.0] * 12},
        ...         "joint_vel_rel": {"scale": [1.0] * 12},
        ...         "last_action": {"scale": [1.0] * 12},
        ...     },
        ... }
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "d.yaml"
        ...     p.write_text(yaml.safe_dump(raw))
        ...     cfg = load_rsl_rl_deploy_yaml(p)
        >>> obs = build_rsl_rl_observation(
        ...     config=cfg,
        ...     joint_pos=cfg.default_joint_pos,
        ...     joint_vel=np.zeros(12, np.float32),
        ...     base_ang_vel=np.zeros(3, np.float32),
        ...     projected_gravity=np.array([0.0, 0.0, -1.0], np.float32),
        ...     velocity_commands=np.array([0.5, 0.0, 0.0], np.float32),
        ...     last_action=np.zeros(12, np.float32),
        ... )
        >>> obs.shape
        (45,)
    """
    policy_q = _gather(joint_pos, config.joint_ids_map, name="joint_pos")
    policy_dq = _gather(joint_vel, config.joint_ids_map, name="joint_vel")
    policy_default = _gather(config.default_joint_pos, config.joint_ids_map, name="default")
    ang = np.asarray(base_ang_vel, dtype=np.float32).reshape(-1)
    rel = policy_q - policy_default
    pieces: dict[str, NDArray[np.float32]] = {
        "base_ang_vel": ang,
        "base_ang_vel_B": ang,
        "projected_gravity": np.asarray(projected_gravity, dtype=np.float32).reshape(-1),
        "velocity_commands": np.asarray(velocity_commands, dtype=np.float32).reshape(-1),
        "joint_pos_rel": rel,
        "joint_pos": rel,
        "joint_vel_rel": policy_dq,
        "joint_vel": policy_dq,
        "last_action": np.asarray(last_action, dtype=np.float32).reshape(-1),
    }
    if gait_phase is not None:
        pieces["gait_phase_2"] = np.asarray(gait_phase, dtype=np.float32).reshape(-1)
    if euler_rpy is not None:
        pieces["eulerZYX_rpy"] = np.asarray(euler_rpy, dtype=np.float32).reshape(-1)
    for const_name, const_vec in config.constant_terms:
        pieces[const_name] = np.asarray(const_vec, dtype=np.float32).reshape(-1)
    if joystick_buttons is not None:
        pieces["joystick_buttons"] = np.asarray(joystick_buttons, dtype=np.float32).reshape(-1)
    chunks: list[NDArray[np.float32]] = []
    for name, scale in config.observation_terms:
        if name not in pieces:
            raise ROSConfigError(
                f"rsl_rl_onnx: deploy.yaml observation {name!r} is not a supported "
                f"rsl-rl term (supported: {sorted(pieces)}). Keys are taken from "
                "the YAML; this adapter does not invent substitutes."
            )
        term = pieces[name]
        if term.shape[0] != scale.shape[0]:
            raise ROSConfigError(
                f"rsl_rl_onnx: term {name!r} width {term.shape[0]} != scale {scale.shape[0]}"
            )
        chunks.append(term * scale)
    return np.concatenate(chunks).astype(np.float32, copy=False)


def stack_rsl_rl_term_major_history(
    current: NDArray[np.float32],
    previous: Sequence[NDArray[np.float32]],
    config: RslRlOnnxDeployConfig,
) -> NDArray[np.float32]:
    """Pack one policy input in default **term-major** history order.

    For each observation term, in YAML order, sample ``history_length``
    lags then concatenate. ``oldest_first`` is lags ``H-1 … 0`` (hop
    mjlab). ``repeat_first`` fills missing lags with the oldest stored
    frame, or ``current`` when history is empty — same as
    ``PolicySlot::assembleDefaultTermMajor``.

    History length 1 (the Hub walk YAML) is a no-op: returns ``current``.

    Example:
        >>> raw = {
        ...     "default_joint_pos": [0.0] * 12,
        ...     "actions": {"JointPositionAction": {"scale": [0.25] * 12}},
        ...     "observations": {
        ...         "gait_phase_2": {
        ...             "scale": [1.0, 1.0],
        ...             "history_length": 2,
        ...             "params": {"cycle_time": 1.5},
        ...         },
        ...     },
        ... }
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "d.yaml"
        ...     p.write_text(yaml.safe_dump(raw))
        ...     cfg = load_rsl_rl_deploy_yaml(p)
        >>> now = np.array([0.0, 1.0], np.float32)
        >>> stacked = stack_rsl_rl_term_major_history(now, [], cfg)
        >>> stacked.tolist()
        [0.0, 1.0, 0.0, 1.0]
    """
    frame = np.asarray(current, dtype=np.float32).reshape(-1)
    if frame.shape[0] != config.frame_dim:
        raise ROSConfigError(
            f"rsl_rl_onnx: current frame width {frame.shape[0]} != {config.frame_dim}"
        )
    if all(int(h) <= 1 for h in config.term_history_lengths):
        return frame
    slices = _term_frame_slices(config)
    chunks: list[NDArray[np.float32]] = []
    for start, stop, hist_len in slices:
        lags = _history_lags(hist_len, config.history_order)
        for lag in lags:
            sample = _sample_frame_lag(
                current=frame,
                previous=previous,
                lag=lag,
                warmup=config.history_warmup,
            )
            chunks.append(sample[start:stop])
    stacked = np.concatenate(chunks).astype(np.float32, copy=False)
    if stacked.shape[0] != config.observation_dim:
        raise ROSConfigError(
            f"rsl_rl_onnx: stacked obs width {stacked.shape[0]} != {config.observation_dim}"
        )
    return stacked


def stack_rsl_rl_frame_major_history(
    current: NDArray[np.float32],
    previous: Sequence[NDArray[np.float32]],
    config: RslRlOnnxDeployConfig,
) -> NDArray[np.float32]:
    """Pack one policy input as concatenated full frames (Isaac Gym ``frame_stack``).

    ``oldest_first`` + ``zero`` warmup matches
    ``My_unitree_go2_gym`` ``obs_history`` (deque of zeros, then
    ``reshape(N, T*K)``). History length 1 is a no-op.

    Example:
        >>> raw = {
        ...     "default_joint_pos": [0.0] * 12,
        ...     "actions": {"JointPositionAction": {"scale": [0.25] * 12}},
        ...     "history_layout": "frame_major",
        ...     "observations": {
        ...         "last_action": {
        ...             "scale": [1.0] * 12,
        ...             "history_length": 2,
        ...             "history_warmup": "zero",
        ...         },
        ...     },
        ... }
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "d.yaml"
        ...     p.write_text(yaml.safe_dump(raw))
        ...     cfg = load_rsl_rl_deploy_yaml(p)
        >>> now = np.arange(12, dtype=np.float32)
        >>> stacked = stack_rsl_rl_frame_major_history(now, [], cfg)
        >>> stacked[:12].tolist()
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        >>> stacked[12:].tolist() == now.tolist()
        True
    """
    frame = np.asarray(current, dtype=np.float32).reshape(-1)
    if frame.shape[0] != config.frame_dim:
        raise ROSConfigError(
            f"rsl_rl_onnx: current frame width {frame.shape[0]} != {config.frame_dim}"
        )
    hist_len = int(config.term_history_lengths[0]) if config.term_history_lengths else 1
    if hist_len <= 1:
        return frame
    chunks: list[NDArray[np.float32]] = []
    for lag in _history_lags(hist_len, config.history_order):
        chunks.append(
            _sample_frame_lag(
                current=frame,
                previous=previous,
                lag=lag,
                warmup=config.history_warmup,
            )
        )
    stacked = np.concatenate(chunks).astype(np.float32, copy=False)
    if stacked.shape[0] != config.observation_dim:
        raise ROSConfigError(
            f"rsl_rl_onnx: stacked obs width {stacked.shape[0]} != {config.observation_dim}"
        )
    return stacked


def decode_rsl_rl_joint_position(
    raw_action: NDArray[np.float32],
    config: RslRlOnnxDeployConfig,
) -> NDArray[np.float32]:
    """``default_joint_pos + raw * scale``, scattered to HAL / robot order.

    Example:
        >>> raw = {
        ...     "joint_ids_map": list(range(12)),
        ...     "default_joint_pos": [0.0, 0.9, -1.8] * 4,
        ...     "actions": {"JointPositionAction": {"scale": [0.5] * 12}},
        ...     "observations": {"last_action": {"scale": [1.0] * 12}},
        ... }
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as td:
        ...     p = Path(td) / "d.yaml"
        ...     p.write_text(yaml.safe_dump(raw))
        ...     cfg = load_rsl_rl_deploy_yaml(p)
        >>> q = decode_rsl_rl_joint_position(np.zeros(12, np.float32), cfg)
        >>> np.allclose(q, cfg.default_joint_pos)
        True
    """
    raw = np.asarray(raw_action, dtype=np.float32).reshape(-1)
    if raw.shape[0] != config.action_dim:
        raise ROSRuntimeError(
            f"rsl_rl_onnx: ONNX emitted {raw.shape[0]}-D action; "
            f"deploy.yaml JointPositionAction is {config.action_dim}-D"
        )
    if not np.isfinite(raw).all():
        raise ROSRuntimeError("rsl_rl_onnx: ONNX emitted non-finite actions")
    policy_default = _gather(config.default_joint_pos, config.joint_ids_map, name="default")
    policy_target = policy_default + raw * config.action_scale
    return _scatter(policy_target, config.joint_ids_map, n=config.default_joint_pos.shape[0])


@dataclass
class _RslRlOnnxAdapter:
    """ONNX Runtime policy that emits 12-D joint-position targets."""

    spec: VLASpec
    device: str
    _session: Any
    _input_name: str
    _config: RslRlOnnxDeployConfig
    _velocity_commands: NDArray[np.float32]
    _default_velocity_commands: NDArray[np.float32]
    _joystick_buttons: NDArray[np.float32]
    _coast_to_stand_s: float | None = None
    _coast_budget_s: float | None = None
    _last_action: NDArray[np.float32] = field(init=False)
    _history: deque[NDArray[np.float32]] = field(init=False)
    _step_index: int = field(init=False)

    def __post_init__(self) -> None:
        self._last_action = np.zeros(self._config.action_dim, dtype=np.float32)
        self._default_velocity_commands = np.asarray(
            self._default_velocity_commands, dtype=np.float32
        ).reshape(3)
        self._velocity_commands = np.asarray(self._velocity_commands, dtype=np.float32).reshape(3)
        self._joystick_buttons = np.asarray(self._joystick_buttons, dtype=np.float32).reshape(-1)
        self.reset()

    def reset(self) -> None:
        self._last_action = np.zeros(self._config.action_dim, dtype=np.float32)
        max_lag = max((int(h) - 1 for h in self._config.term_history_lengths), default=0)
        self._history = deque(maxlen=max(max_lag, 1))
        self._history.clear()
        self._step_index = 0

    def set_velocity_commands(self, commands: object | None) -> None:
        """Replace the joystick for subsequent ``step()`` calls.

        ``None`` restores the YAML / extras default captured at load. Used by
        ``execute_rskill`` so a resident skill can take a per-goal override
        without rebuilding the ONNX session.
        """
        if commands is None:
            self._velocity_commands = self._default_velocity_commands.copy()
            return
        self._velocity_commands = _as_velocity_command_vec(commands)

    def step(self, observation: Observation, instruction: str) -> NDArray[np.float32]:
        del instruction  # reasoner prompt ≠ Isaac velocity command (documented gap)
        obs_cmd = _velocity_commands_from_obs(observation)
        commanded = obs_cmd if obs_cmd is not None else self._velocity_commands
        elapsed_s = float(self._step_index) * float(self._config.step_dt)
        velocity = coast_velocity_commands(
            commanded,
            elapsed_s=elapsed_s,
            budget_s=self._coast_budget_s,
            coast_to_stand_s=self._coast_to_stand_s,
        )
        needs_gait = any(name == "gait_phase_2" for name, _scale in self._config.observation_terms)
        needs_euler = any(name == "eulerZYX_rpy" for name, _scale in self._config.observation_terms)
        gait = None
        if needs_gait:
            if self._config.gait_cycle_s is None:
                raise ROSConfigError("rsl_rl_onnx: gait_phase_2 present but gait_cycle_s is unset")
            gait = gait_phase_2(
                step_index=self._step_index,
                step_dt=self._config.step_dt,
                cycle_s=self._config.gait_cycle_s,
            )
        euler = _euler_rpy_from_obs(observation) if needs_euler else None
        needs_joy = any(
            name == "joystick_buttons" for name, _scale in self._config.observation_terms
        )
        joy = _joystick_from_obs(observation) if needs_joy else None
        if needs_joy and joy is None:
            joy = self._joystick_buttons
        frame = build_rsl_rl_observation(
            config=self._config,
            joint_pos=_joint_pos_from_obs(observation, self._config),
            joint_vel=_joint_vel_from_obs(observation, self._config),
            base_ang_vel=_base_ang_vel_from_obs(observation),
            projected_gravity=_projected_gravity_from_obs(observation),
            velocity_commands=velocity,
            last_action=self._last_action,
            gait_phase=gait,
            euler_rpy=euler,
            joystick_buttons=joy,
        )
        stacker = (
            stack_rsl_rl_frame_major_history
            if self._config.history_layout == "frame_major"
            else stack_rsl_rl_term_major_history
        )
        obs_vec = stacker(frame, list(self._history), self._config)
        batch = {self._input_name: obs_vec.reshape(1, -1)}
        with inference_span(kind="single", engine="onnx"):
            outputs = self._session.run(None, batch)
        raw = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        if self._config.action_clip is not None:
            raw = np.clip(raw, -self._config.action_clip, self._config.action_clip)
        self._last_action = raw.copy()
        if self._history.maxlen:
            self._history.append(frame.copy())
        self._step_index += 1
        return decode_rsl_rl_joint_position(raw, self._config)

    def close(self) -> None:
        self._session = None


@POLICIES.register(RSL_RL_ONNX_FAMILY)
def _build_rsl_rl_onnx(env_cfg: Any) -> _RslRlOnnxAdapter:
    """Load ``policy.onnx`` + ``params/deploy.yaml`` for ``model_family: rsl_rl_onnx``."""
    spec = env_cfg.vla
    extra = dict(getattr(spec, "extra", {}) or {})
    manifest = _optional_manifest(spec)
    if manifest is not None:
        extra = {**dict(manifest.policy_extras), **extra}
    onnx_path, deploy_path = resolve_rsl_rl_onnx_assets(spec, extra=extra, manifest=manifest)
    config = load_rsl_rl_deploy_yaml(deploy_path)
    config = _apply_joint_order(config, extra)
    session, input_name, device = _open_onnx_session(onnx_path, spec)
    velocity = resolve_velocity_commands(extra)
    joystick = _resolve_joystick_buttons(extra, config=config)
    latency = getattr(manifest, "latency_budget", None) if manifest is not None else None
    coast_s = resolve_coast_to_stand_s(extra, family=RSL_RL_ONNX_FAMILY)
    coast_budget = resolve_coast_budget_s(
        extra,
        max_execution_s=getattr(latency, "max_execution_s", None),
    )
    log.info(
        "rsl_rl_onnx.loaded",
        onnx=str(onnx_path),
        deploy=str(deploy_path),
        observation_dim=config.observation_dim,
        frame_dim=config.frame_dim,
        action_dim=config.action_dim,
        history_lengths=list(config.term_history_lengths),
        history_layout=config.history_layout,
        gait_cycle_s=config.gait_cycle_s,
        velocity_commands=velocity.tolist(),
        velocity_command_source="policy_extras",
        jump_trigger=joystick.tolist(),
        joint_order=str(extra.get("joint_order", _JOINT_ORDER_DEFAULT)),
        joint_ids_map=config.joint_ids_map.tolist(),
        coast_to_stand_s=coast_s,
        coast_budget_s=coast_budget,
        note="reasoner prompt is not mapped to Isaac velocity_commands",
    )
    return _RslRlOnnxAdapter(
        spec=spec,
        device=device,
        _session=session,
        _input_name=input_name,
        _config=config,
        _velocity_commands=velocity,
        _default_velocity_commands=velocity.copy(),
        _joystick_buttons=joystick,
        _coast_to_stand_s=coast_s,
        _coast_budget_s=coast_budget,
    )


def _apply_joint_order(
    config: RslRlOnnxDeployConfig, extra: dict[str, object]
) -> RslRlOnnxDeployConfig:
    """Resolve whose joint order the caller feeds, and drop the map when it is the policy's.

    ``deploy.yaml``'s ``joint_ids_map`` is the **real-robot** permutation: it
    reorders between the policy's own joint order and the Unitree SDK's
    (``FR, FL, RR, RL`` against menagerie's ``FL, FR, RL, RR``). OpenRAL's HAL
    speaks menagerie order, which for this checkpoint IS the policy's training
    order — so applying the map hands every command to the mirrored leg.

    The permutation is self-inverse, so reading it as gather-then-scatter or
    the reverse produces the same wrong result; the only correct action is not
    to apply it. Measured offline at a true 50 Hz on the composed `go2_walk`
    floor, 20 s at ``[0.5, 0, 0]``:

    ==================  ================================================
    ``joint_order``     result
    ==================  ================================================
    ``policy`` (ident)  7.07 m forward, 0.39 m lateral, never below stand
    ``unitree_sdk``     0.30 m, collapsed to z=0.155 (self-collision stop)
    ==================  ================================================

    Default is ``"policy"`` because every in-tree consumer drives a MuJoCo
    twin in menagerie order. A caller wiring this policy to a real Go2 over
    ``unitree_sdk2`` sets ``policy_extras.joint_order: unitree_sdk`` to get
    the YAML permutation back. The map is still parsed and validated either
    way, so a malformed one is still rejected at load.
    """
    order = str(extra.get("joint_order", _JOINT_ORDER_DEFAULT))
    if order not in _JOINT_ORDERS:
        raise ROSConfigError(
            f"rsl_rl_onnx: joint_order {order!r} is not one of {sorted(_JOINT_ORDERS)}"
        )
    if order == "unitree_sdk":
        return config
    identity = np.arange(config.default_joint_pos.shape[0], dtype=np.intp)
    return replace(config, joint_ids_map=identity)


def resolve_rsl_rl_onnx_assets(
    spec: Any,
    *,
    extra: dict[str, object],
    manifest: RSkillManifest | None,
) -> tuple[Path, Path]:
    """Locate ``policy.onnx`` and ``params/deploy.yaml`` (local dir or Hub).

    Resolution order:

    1. Explicit ``policy_extras.onnx_path`` + ``deploy_yaml_path``.
    2. Files next to a local ``weights_uri`` directory
       (``policy.onnx``, ``params/deploy.yaml``, overridable via extras).
       Missing ONNX with a present deploy YAML is filled from
       ``policy_extras.onnx_url`` (hop customer; weights not vendored).
    3. Hub download from ``manifest.weights_uri`` or an ``hf://`` spec URI
       (``policy.onnx`` + optional ``policy.onnx.data`` sidecar).

    Args:
        spec: ``VLASpec`` (or a namespace with ``weights_uri``).
        extra: Merged ``policy_extras`` / ``VLASpec.extra``.
        manifest: Optional rSkill manifest loaded from a local directory.

    Returns:
        ``(onnx_path, deploy_yaml_path)``.

    Raises:
        ROSConfigError: Neither local files nor a Hub URI can be resolved.
    """
    onnx_override = extra.get("onnx_path")
    deploy_override = extra.get("deploy_yaml_path")
    if onnx_override is not None and deploy_override is not None:
        return Path(str(onnx_override)), Path(str(deploy_override))

    onnx_name = str(extra.get("onnx_filename") or _DEFAULT_ONNX_FILENAME)
    deploy_rel = str(extra.get("deploy_yaml") or _DEFAULT_DEPLOY_REL)
    weights_uri = str(getattr(spec, "weights_uri", "") or "")

    local_root = _local_weights_root(weights_uri)
    if local_root is not None:
        local_onnx = local_root / onnx_name
        local_deploy = local_root / deploy_rel
        if local_onnx.is_file() and local_deploy.is_file():
            return local_onnx, local_deploy
        if local_deploy.is_file():
            fetched = _onnx_from_url(extra, filename=onnx_name)
            if fetched is not None:
                return fetched, local_deploy

    hub_uri = _hub_uri(weights_uri, extra, manifest)
    if hub_uri is not None:
        return _download_hub_assets(hub_uri, onnx_name=onnx_name, deploy_rel=deploy_rel)

    fetched = _onnx_from_url(extra, filename=onnx_name)
    deploy_override_only = extra.get("deploy_yaml_path")
    if fetched is not None and deploy_override_only is not None:
        return fetched, Path(str(deploy_override_only))

    raise ROSConfigError(
        "rsl_rl_onnx: could not find policy.onnx + params/deploy.yaml. "
        f"Looked under {weights_uri!r}. Point weights_uri at an rSkill directory "
        "or hf://owner/repo, or set policy_extras.onnx_path / deploy_yaml_path "
        "(hop: onnx_url + in-tree params/deploy.yaml)."
    )


def write_zero_action_onnx(path: Path | str, *, observation_dim: int, action_dim: int) -> Path:
    """Write a deterministic ONNX that ignores obs and emits a zero action.

    Used by unit tests so ``make_policy`` runs a real ONNX Runtime session
    without downloading Hub weights. Requires the optional ``onnx`` package.

    Args:
        path: Destination ``*.onnx`` path.
        observation_dim: Input width (45 for Go2 velocity-flat, 470 for mjlab hop).
        action_dim: Output width (12 for Go2).

    Returns:
        The written path.

    Raises:
        ROSConfigError: The ``onnx`` package is not installed.
    """
    try:
        import onnx
        from onnx import helper, numpy_helper
    except ImportError as exc:
        raise ROSConfigError(
            "rsl_rl_onnx: writing a fixture ONNX requires the 'onnx' package"
        ) from exc
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    zeros = numpy_helper.from_array(
        np.zeros((1, action_dim), dtype=np.float32), name="actions_const"
    )
    obs_in = helper.make_tensor_value_info("obs", onnx.TensorProto.FLOAT, [1, observation_dim])
    act_out = helper.make_tensor_value_info("actions", onnx.TensorProto.FLOAT, [1, action_dim])
    passthrough_out = helper.make_tensor_value_info(
        "obs_passthrough", onnx.TensorProto.FLOAT, [1, observation_dim]
    )
    graph = helper.make_graph(
        nodes=[
            helper.make_node("Constant", inputs=[], outputs=["actions"], value=zeros),
            helper.make_node("Identity", inputs=["obs"], outputs=["obs_passthrough"]),
        ],
        name="rsl_rl_zero_action",
        inputs=[obs_in],
        outputs=[act_out, passthrough_out],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(dest))
    return dest


# ── internals ────────────────────────────────────────────────────────────────


def _optional_manifest(spec: Any) -> RSkillManifest | None:
    """Load a local rSkill manifest when one is actually on disk.

    ``load_manifest_for_spec`` treats a bare path without ``rskill.yaml`` as
    a Hub repo id and tries ``hf_hub_download``. A fixture directory that
    only holds ``policy.onnx`` + ``params/deploy.yaml`` must not hit the
    network. ``hf://`` URIs already return ``None``.
    """
    weights_uri = str(getattr(spec, "weights_uri", "") or "")
    local = _local_weights_root(weights_uri)
    if local is not None and not (local / "rskill.yaml").is_file():
        return None
    try:
        return load_manifest_for_spec(spec)
    except ROSConfigError:
        return None


def _local_weights_root(weights_uri: str) -> Path | None:
    if not weights_uri:
        return None
    if weights_uri.startswith("local://"):
        path = Path(weights_uri[len("local://") :])
        return path if path.is_dir() else path.parent
    if weights_uri.startswith(("hf://", "file://", "http://", "https://")):
        return None
    path = Path(weights_uri)
    if path.is_dir():
        return path
    if path.is_file():
        return path.parent
    return None


def _hub_uri(
    weights_uri: str,
    extra: dict[str, object],
    manifest: RSkillManifest | None,
) -> str | None:
    raw = extra.get("weights_hub")
    if isinstance(raw, str) and raw.startswith("hf://"):
        return raw
    if weights_uri.startswith("hf://"):
        return weights_uri
    if manifest is not None and manifest.weights_uri and manifest.weights_uri.startswith("hf://"):
        return manifest.weights_uri
    return None


def _download_hub_assets(
    hub_uri: str,
    *,
    onnx_name: str,
    deploy_rel: str,
) -> tuple[Path, Path]:
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError
    except ImportError as exc:
        raise ROSConfigError(
            "rsl_rl_onnx: huggingface_hub is required to fetch policy.onnx"
        ) from exc
    repo_id, revision = _split_hf_repo(hub_uri)
    try:
        onnx_path = Path(hf_hub_download(repo_id=repo_id, filename=onnx_name, revision=revision))
    except Exception as exc:
        raise ROSConfigError(
            f"rsl_rl_onnx: failed to download hf://{repo_id}/{onnx_name}: {exc}"
        ) from exc
    # External-data ONNX (policy.onnx.data) must sit next to the proto.
    data_name = f"{onnx_name}.data"
    try:
        hf_hub_download(repo_id=repo_id, filename=data_name, revision=revision)
    except EntryNotFoundError:
        log.debug("rsl_rl_onnx.no_external_data", repo=repo_id, filename=data_name)
    try:
        deploy_path = Path(hf_hub_download(repo_id=repo_id, filename=deploy_rel, revision=revision))
    except Exception as exc:
        raise ROSConfigError(
            f"rsl_rl_onnx: failed to download hf://{repo_id}/{deploy_rel}: {exc}"
        ) from exc
    return onnx_path, deploy_path


def _split_hf_repo(uri: str) -> tuple[str, str | None]:
    if not uri.startswith("hf://"):
        raise ROSConfigError(f"rsl_rl_onnx: expected hf:// URI, got {uri!r}")
    body = uri[len("hf://") :]
    owner, sep, rest = body.partition("/")
    if not sep or not owner or not rest:
        raise ROSConfigError(f"rsl_rl_onnx: malformed Hub URI {uri!r}")
    repo_and_rev = rest.split("/", 1)[0]
    if "@" in repo_and_rev:
        repo, revision = repo_and_rev.split("@", 1)
        return f"{owner}/{repo}", revision or None
    return f"{owner}/{repo_and_rev}", None


def _open_onnx_session(onnx_path: Path, spec: Any) -> tuple[Any, str, str]:
    try:
        import onnxruntime as ort  # type: ignore[import-untyped]  # reason: onnxruntime ships no py.typed
    except ImportError as exc:
        raise ROSRuntimeError(
            "rsl_rl_onnx: 'onnxruntime' is not installed. "
            "Install with: just sync --all-packages --group sim"
        ) from exc
    device = str(getattr(spec, "device", "cpu") or "cpu")
    if device == "auto":
        available = list(ort.get_available_providers())
        device = "cuda" if "CUDAExecutionProvider" in available else "cpu"
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device.startswith("cuda")
        else ["CPUExecutionProvider"]
    )
    try:
        session = ort.InferenceSession(str(onnx_path), providers=providers)
    except Exception as exc:
        raise ROSConfigError(f"rsl_rl_onnx: could not load {onnx_path}: {exc}") from exc
    inputs = session.get_inputs()
    if not inputs:
        raise ROSConfigError(f"rsl_rl_onnx: {onnx_path} has no inputs")
    return session, str(inputs[0].name), device


def _float_vec(raw: object, *, name: str) -> NDArray[np.float32]:
    if raw is None:
        raise ROSConfigError(f"rsl_rl_onnx: {name} is missing")
    if isinstance(raw, (int, float)):
        return np.asarray([float(raw)], dtype=np.float32)
    # An already-coerced vector must survive a second pass. `set_velocity_commands`
    # re-validates whatever it is handed, and `apply_velocity_command_override`
    # hands it the float32 array `velocity_override_from_goal_params` just
    # produced — so rejecting ndarray here made every goal_params_json joystick
    # override abort the goal.
    if isinstance(raw, np.ndarray):
        raw = raw.reshape(-1).tolist()
    if not isinstance(raw, (list, tuple)):
        raise ROSConfigError(f"rsl_rl_onnx: {name} must be a list of floats, got {type(raw)}")
    try:
        return np.asarray([float(v) for v in raw], dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ROSConfigError(f"rsl_rl_onnx: {name} is not a numeric list: {raw!r}") from exc


def _broadcast_scale(raw: object, *, width: int, name: str) -> NDArray[np.float32]:
    if raw is None:
        return np.ones(width, dtype=np.float32)
    if isinstance(raw, (int, float)):
        return np.full(width, float(raw), dtype=np.float32)
    vec = _float_vec(raw, name=name)
    if vec.shape == (1,) and width > 1:
        return np.full(width, float(vec[0]), dtype=np.float32)
    if vec.shape != (width,):
        raise ROSConfigError(f"rsl_rl_onnx: {name} scale dim {vec.shape[0]} != {width}")
    return vec


def _term_width(name: str, scale: object) -> int:
    if isinstance(scale, (list, tuple)):
        return len(scale)
    if name in _ISAAC_TERM_WIDTHS:
        return _ISAAC_TERM_WIDTHS[name]
    raise ROSConfigError(f"rsl_rl_onnx: observation {name!r} has no scale list and no known width")


def _parse_observation_terms(
    observations: dict[object, object],
) -> tuple[
    tuple[tuple[str, NDArray[np.float32]], ...],
    tuple[int, ...],
    str,
    str,
    float | None,
]:
    """Read YAML ``observations:`` into term scales, history, and gait cycle."""
    terms: list[tuple[str, NDArray[np.float32]]] = []
    hist_lengths: list[int] = []
    orders: set[str] = set()
    warmups: set[str] = set()
    gait_cycle_s: float | None = None
    for name, block in observations.items():
        if not isinstance(name, str):
            raise ROSConfigError(f"rsl_rl_onnx: observation key {name!r} is not a string")
        params: dict[str, object] = (
            {str(k): v for k, v in block.items()} if isinstance(block, dict) else {}
        )
        width = _term_width(name, params.get("scale"))
        terms.append((name, _broadcast_scale(params.get("scale"), width=width, name=name)))
        hist_lengths.append(_history_length(params, name=name))
        order = str(params.get("history_order") or params.get("order") or _HISTORY_ORDER_DEFAULT)
        warmup = str(params.get("history_warmup") or _HISTORY_WARMUP_DEFAULT)
        if order not in _HISTORY_ORDERS:
            raise ROSConfigError(
                f"rsl_rl_onnx: observation {name!r} order {order!r} is not one of "
                f"{sorted(_HISTORY_ORDERS)}"
            )
        if warmup not in _HISTORY_WARMUPS:
            raise ROSConfigError(
                f"rsl_rl_onnx: observation {name!r} history_warmup {warmup!r} is not one of "
                f"{sorted(_HISTORY_WARMUPS)}"
            )
        orders.add(order)
        warmups.add(warmup)
        if name == "gait_phase_2":
            gait_cycle_s = _gait_cycle_s(params)
    if len(orders) > 1:
        raise ROSConfigError(
            f"rsl_rl_onnx: mixed history_order values {sorted(orders)}; "
            "all observation terms must share one order"
        )
    if len(warmups) > 1:
        raise ROSConfigError(
            f"rsl_rl_onnx: mixed history_warmup values {sorted(warmups)}; "
            "all observation terms must share one warmup"
        )
    history_order = orders.pop() if orders else _HISTORY_ORDER_DEFAULT
    history_warmup = warmups.pop() if warmups else _HISTORY_WARMUP_DEFAULT
    return tuple(terms), tuple(hist_lengths), history_order, history_warmup, gait_cycle_s


def _history_layout(loaded: dict[object, object]) -> str:
    raw = loaded.get("history_layout", _HISTORY_LAYOUT_DEFAULT)
    layout = str(raw or _HISTORY_LAYOUT_DEFAULT)
    if layout not in _HISTORY_LAYOUTS:
        raise ROSConfigError(
            f"rsl_rl_onnx: history_layout {layout!r} is not one of {sorted(_HISTORY_LAYOUTS)}"
        )
    return layout


def _action_clip(loaded: dict[object, object], joint_action: dict[str, object]) -> float | None:
    raw = loaded.get("action_clip", joint_action.get("clip"))
    if raw is None:
        return None
    try:
        clip = float(raw)
    except (TypeError, ValueError) as exc:
        raise ROSConfigError(f"rsl_rl_onnx: action_clip {raw!r} is not a float") from exc
    if clip <= 0.0:
        raise ROSConfigError(f"rsl_rl_onnx: action_clip must be > 0, got {clip}")
    return clip


def _constant_terms(
    observations: dict[object, object],
) -> tuple[tuple[str, NDArray[np.float32]], ...]:
    out: list[tuple[str, NDArray[np.float32]]] = []
    for name, block in observations.items():
        if name != "constants" or not isinstance(block, dict):
            continue
        nested = block.get("params")
        params = nested if isinstance(nested, dict) else {}
        vec_raw = params.get("vec", block.get("vec"))
        if not isinstance(vec_raw, (list, tuple)) or not vec_raw:
            raise ROSConfigError("rsl_rl_onnx: constants requires params.vec")
        out.append((str(name), _float_vec(vec_raw, name="constants.vec")))
    return tuple(out)


def _joystick_term_width(config: RslRlOnnxDeployConfig) -> int:
    for name, scale in config.observation_terms:
        if name == "joystick_buttons":
            return int(scale.shape[0])
    return 0


def _resolve_joystick_buttons(
    extra: dict[str, object], *, config: RslRlOnnxDeployConfig
) -> NDArray[np.float32]:
    width = _joystick_term_width(config)
    if width == 0:
        return np.zeros(0, dtype=np.float32)
    raw = extra.get("jump_trigger", extra.get("joystick_buttons"))
    if raw is None:
        return np.ones(width, dtype=np.float32)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return np.full(width, float(raw), dtype=np.float32)
    vec = _float_vec(raw, name="jump_trigger")
    if vec.shape[0] != width:
        raise ROSConfigError(
            f"rsl_rl_onnx: jump_trigger width {vec.shape[0]} != joystick_buttons {width}"
        )
    return vec


def _joystick_from_obs(observation: Observation) -> NDArray[np.float32] | None:
    raw = observation.get("joystick_buttons", observation.get("jump_trigger"))
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return np.asarray([float(raw)], dtype=np.float32)
    return _float_vec(raw, name="joystick_buttons")


def _gait_cycle_s(params: dict[str, object]) -> float:
    nested = params.get("params")
    cycle_raw: object = nested.get("cycle_time") if isinstance(nested, dict) else None
    if cycle_raw is None:
        cycle_raw = params.get("cycle_time")
    if isinstance(cycle_raw, bool) or not isinstance(cycle_raw, (int, float, str)):
        raise ROSConfigError(
            f"rsl_rl_onnx: gait_phase_2 requires params.cycle_time, got {cycle_raw!r}"
        )
    cycle = float(cycle_raw)
    if cycle <= 0.0:
        raise ROSConfigError(f"rsl_rl_onnx: gait_phase_2 cycle_time must be > 0, got {cycle}")
    return cycle


def _history_length(params: dict[str, object], *, name: str) -> int:
    raw = params.get("history_length", params.get("length", 1))
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ROSConfigError(
            f"rsl_rl_onnx: observation {name!r} history_length {raw!r} is not an int"
        )
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ROSConfigError(
            f"rsl_rl_onnx: observation {name!r} history_length {raw!r} is not an int"
        ) from exc
    if value < 1:
        raise ROSConfigError(
            f"rsl_rl_onnx: observation {name!r} history_length must be >= 1, got {value}"
        )
    return value


def _term_frame_slices(config: RslRlOnnxDeployConfig) -> tuple[tuple[int, int, int], ...]:
    offset = 0
    slices: list[tuple[int, int, int]] = []
    for (_name, scale), hist in zip(
        config.observation_terms, config.term_history_lengths, strict=True
    ):
        width = int(scale.shape[0])
        slices.append((offset, offset + width, int(hist)))
        offset += width
    return tuple(slices)


def _history_lags(length: int, order: str) -> tuple[int, ...]:
    if length < 1:
        raise ROSConfigError(f"rsl_rl_onnx: history length must be >= 1, got {length}")
    if order == "newest_first":
        return tuple(range(length))
    return tuple(range(length - 1, -1, -1))


def _sample_frame_lag(
    *,
    current: NDArray[np.float32],
    previous: Sequence[NDArray[np.float32]],
    lag: int,
    warmup: str,
) -> NDArray[np.float32]:
    if lag == 0:
        return current
    if len(previous) >= lag:
        return np.asarray(previous[-lag], dtype=np.float32).reshape(-1)
    if warmup == "zero":
        return np.zeros_like(current)
    if previous:
        return np.asarray(previous[0], dtype=np.float32).reshape(-1)
    return current


def _onnx_from_url(extra: dict[str, object], *, filename: str) -> Path | None:
    url = extra.get("onnx_url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    return _download_onnx_url(url, filename=filename)


def _download_onnx_url(url: str, *, filename: str) -> Path:
    """Fetch ``policy.onnx`` once into ``~/.cache/openral/rsl_rl_onnx/<digest>/``.

    Used for the hop customer: the ONNX is not vendored (upstream deploy
    repo has no license). One GET, no hidden retries.
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    cache_dir = Path.home() / ".cache" / "openral" / "rsl_rl_onnx" / digest
    dest = cache_dir / filename
    if dest.is_file() and dest.stat().st_size > 0:
        log.info("rsl_rl_onnx.onnx_cache_hit", url=url, path=str(dest))
        return dest
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "openral-rsl-rl-onnx/1.0"})
    log.info("rsl_rl_onnx.fetch_onnx", url=url, dest=str(dest))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            tmp.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ROSConfigError(f"rsl_rl_onnx: failed to download {url}: {exc}") from exc
    if tmp.stat().st_size <= 0:
        tmp.unlink(missing_ok=True)
        raise ROSConfigError(f"rsl_rl_onnx: downloaded empty ONNX from {url}")
    tmp.replace(dest)
    return dest


def _joint_ids_map(raw: object, *, n: int) -> NDArray[np.intp]:
    if not isinstance(raw, (list, tuple)) or len(raw) != n:
        raise ROSConfigError(f"rsl_rl_onnx: joint_ids_map must be length {n}, got {raw!r}")
    try:
        mapped = np.asarray([int(v) for v in raw], dtype=np.intp)
    except (TypeError, ValueError) as exc:
        raise ROSConfigError(f"rsl_rl_onnx: joint_ids_map is not integer: {raw!r}") from exc
    if set(mapped.tolist()) != set(range(n)):
        raise ROSConfigError(
            f"rsl_rl_onnx: joint_ids_map {mapped.tolist()} is not a permutation of 0..{n - 1}"
        )
    return mapped


def _gather(
    values: NDArray[np.float32], joint_ids_map: NDArray[np.intp], *, name: str
) -> NDArray[np.float32]:
    vec = np.asarray(values, dtype=np.float32).reshape(-1)
    if vec.shape[0] <= int(joint_ids_map.max()):
        raise ROSConfigError(
            f"rsl_rl_onnx: {name} length {vec.shape[0]} is shorter than joint_ids_map"
        )
    return vec[joint_ids_map]


def _scatter(
    policy_values: NDArray[np.float32],
    joint_ids_map: NDArray[np.intp],
    *,
    n: int,
) -> NDArray[np.float32]:
    robot = np.zeros(n, dtype=np.float32)
    robot[joint_ids_map] = np.asarray(policy_values, dtype=np.float32).reshape(-1)
    return robot


def _quat_xyzw_to_rotation(q: NDArray[np.float32]) -> NDArray[np.float32]:
    x, y, z, w = (float(v) for v in q)
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float32,
    )


def _as_velocity_command_vec(raw: object) -> NDArray[np.float32]:
    vec = _float_vec(raw, name="velocity_commands")
    if vec.shape != (3,):
        raise ROSConfigError(
            f"rsl_rl_onnx: velocity_commands must be a 3-vector [vx, vy, yaw]; got {vec.shape}"
        )
    return vec


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
        import json

        loaded = json.loads(text)
    except ValueError as exc:
        raise ROSConfigError(f"rsl_rl_onnx: goal_params_json is not valid JSON: {text!r}") from exc
    if not isinstance(loaded, dict):
        raise ROSConfigError(
            f"rsl_rl_onnx: goal_params_json must be a JSON object, got {type(loaded)}"
        )
    return loaded


def _velocity_commands_from_obs(observation: Observation) -> NDArray[np.float32] | None:
    raw = observation.get("velocity_commands", observation.get("velocity_command"))
    if raw is None:
        return None
    return _as_velocity_command_vec(raw)


def _warn_obs_fallback(term: str, detail: str) -> None:
    if term in _OBS_FALLBACK_WARNED:
        return
    _OBS_FALLBACK_WARNED.add(term)
    log.warning("rsl_rl_onnx.obs_fallback", term=term, detail=detail)


def _as_float_vec(raw: object, *, n: int, name: str) -> NDArray[np.float32] | None:
    if raw is None:
        return None
    if hasattr(raw, "tolist") and not isinstance(raw, (list, tuple)):
        raw = raw.tolist()
    if isinstance(raw, dict):
        return None
    try:
        vec = np.asarray(raw, dtype=np.float32).reshape(-1)
    except (TypeError, ValueError):
        return None
    if vec.shape[0] < n:
        raise ROSConfigError(f"rsl_rl_onnx: {name} length {vec.shape[0]} < {n}")
    return vec[:n]


def _joint_pos_from_obs(
    observation: Observation, config: RslRlOnnxDeployConfig
) -> NDArray[np.float32]:
    n = config.default_joint_pos.shape[0]
    for key in ("joint_pos", "state"):
        vec = _as_float_vec(observation.get(key), n=n, name=key)
        if vec is not None:
            return vec
    raise ROSConfigError(
        "rsl_rl_onnx: observation is missing joint positions (expected 'joint_pos' or 'state')"
    )


def _joint_vel_from_obs(
    observation: Observation, config: RslRlOnnxDeployConfig
) -> NDArray[np.float32]:
    n = config.default_joint_pos.shape[0]
    vec = _as_float_vec(observation.get("joint_vel"), n=n, name="joint_vel")
    if vec is not None:
        return vec
    return np.zeros(n, dtype=np.float32)


def _base_ang_vel_from_obs(observation: Observation) -> NDArray[np.float32]:
    vec = _as_float_vec(observation.get("base_ang_vel"), n=3, name="base_ang_vel")
    if vec is not None:
        return vec
    twist = _as_float_vec(observation.get("base_twist"), n=6, name="base_twist")
    if twist is not None:
        return twist[3:6]
    _warn_obs_fallback(
        "base_ang_vel",
        "observation has no base_ang_vel / base_twist; using zeros. "
        "Go2MujocoHAL must publish base_pose_6dof + base_twist so WorldState "
        "can fill the 45-D rsl-rl obs.",
    )
    return np.zeros(3, dtype=np.float32)


def _projected_gravity_from_obs(observation: Observation) -> NDArray[np.float32]:
    vec = _as_float_vec(observation.get("projected_gravity"), n=3, name="projected_gravity")
    if vec is not None:
        return vec
    pose = observation.get("base_pose")
    quat: object = (
        pose.get("quat_xyzw") if isinstance(pose, dict) else getattr(pose, "quat_xyzw", None)
    )
    q = _as_float_vec(quat, n=4, name="base_pose.quat_xyzw")
    if q is not None:
        return projected_gravity_from_quat_xyzw(q)
    _warn_obs_fallback(
        "projected_gravity",
        "observation has no projected_gravity / base_pose.quat_xyzw; using "
        "identity gravity [0, 0, -1]. Go2MujocoHAL must publish base_pose_6dof "
        "so WorldState can fill the 45-D rsl-rl obs.",
    )
    return _GRAVITY_WORLD.copy()


def _euler_rpy_from_obs(observation: Observation) -> NDArray[np.float32]:
    vec = _as_float_vec(observation.get("eulerZYX_rpy"), n=3, name="eulerZYX_rpy")
    if vec is not None:
        return vec
    pose = observation.get("base_pose")
    quat: object = (
        pose.get("quat_xyzw") if isinstance(pose, dict) else getattr(pose, "quat_xyzw", None)
    )
    q = _as_float_vec(quat, n=4, name="base_pose.quat_xyzw")
    if q is not None:
        return euler_rpy_from_quat_xyzw(q)
    _warn_obs_fallback(
        "eulerZYX_rpy",
        "observation has no eulerZYX_rpy / base_pose.quat_xyzw; using zeros. "
        "Go2MujocoHAL must publish base_pose_6dof so WorldState can fill the "
        "hop rsl-rl obs.",
    )
    return np.zeros(3, dtype=np.float32)
