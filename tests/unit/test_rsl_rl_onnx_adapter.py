"""Unit tests for the ``rsl_rl_onnx`` ModelFamily + ONNX locomotion adapter.

Exercises the real Hub ``params/deploy.yaml`` layout (copied under
``tests/unit/fixtures/rsl_rl_onnx/``), the in-tree mjlab hop and gym
spring-jump rSkills, and a real ONNX Runtime session against a tiny
fixture graph. No SmolVLA path.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import numpy as np
import pytest
from openral_core.exceptions import ROSConfigError
from openral_core.schemas import (
    ModelFamily,
    RSkillManifest,
    VLASpec,
    repo_name_is_canonical,
)
from openral_sim.factory import make_policy
from openral_sim.policies.rsl_rl_onnx import (
    _OBS_FALLBACK_WARNED,
    RSL_RL_ONNX_FAMILY,
    _apply_joint_order,
    _base_ang_vel_from_obs,
    _projected_gravity_from_obs,
    apply_velocity_command_override,
    build_rsl_rl_observation,
    coast_velocity_commands,
    decode_rsl_rl_joint_position,
    euler_rpy_from_quat_xyzw,
    gait_phase_2,
    in_coast_to_stand_window,
    load_rsl_rl_deploy_yaml,
    projected_gravity_from_quat_xyzw,
    resolve_coast_budget_s,
    resolve_coast_to_stand_s,
    resolve_velocity_commands,
    stack_rsl_rl_frame_major_history,
    stack_rsl_rl_term_major_history,
    velocity_override_from_goal_params,
    write_zero_action_onnx,
)
from openral_sim.registry import POLICIES
from structlog.testing import capture_logs

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO / "rskills" / "rsl-rl-onnx-go2-velocity-flat" / "rskill.yaml"
_HOP_MANIFEST = _REPO / "rskills" / "rsl-rl-onnx-go2-hop-flat" / "rskill.yaml"
_SPRING_MANIFEST = _REPO / "rskills" / "rsl-rl-onnx-go2-spring-jump" / "rskill.yaml"
_DEPLOY = Path(__file__).resolve().parent / "fixtures" / "rsl_rl_onnx" / "deploy.yaml"
_HOP_DEPLOY = _REPO / "rskills" / "rsl-rl-onnx-go2-hop-flat" / "params" / "deploy.yaml"
_SPRING_DEPLOY = _REPO / "rskills" / "rsl-rl-onnx-go2-spring-jump" / "params" / "deploy.yaml"


def test_family_token_is_canonical_and_registered() -> None:
    """Acquire must put ``model_family: rsl_rl_onnx`` in ``rskill.yaml``."""
    assert RSL_RL_ONNX_FAMILY == "rsl_rl_onnx"
    assert RSL_RL_ONNX_FAMILY in get_args(ModelFamily)
    assert RSL_RL_ONNX_FAMILY in POLICIES


def test_intree_manifest_from_yaml_accepts_rsl_rl_onnx() -> None:
    manifest = RSkillManifest.from_yaml(str(_MANIFEST))
    assert manifest.kind == "vla"
    assert manifest.model_family == RSL_RL_ONNX_FAMILY
    assert manifest.runtime == "onnx" or getattr(manifest.runtime, "value", None) == "onnx"
    assert manifest.weights_uri == "hf://diasAiMaster/unitree-go2-velocity-flat"
    assert manifest.action_contract is not None
    assert manifest.action_contract.dim == 12
    assert manifest.action_contract.representation is not None
    assert manifest.action_contract.representation.value == "joint_positions"
    assert manifest.action_contract.joint_units is not None
    assert manifest.action_contract.joint_units.value == "radians"
    extras = manifest.policy_extras
    assert extras.get("onnx_filename") == "policy.onnx"
    assert extras.get("deploy_yaml") == "params/deploy.yaml"
    assert extras.get("velocity_commands") == [0.5, 0.0, 0.0]
    assert extras.get("horizon_s") == 57.0
    assert extras.get("coast_to_stand_s") == 3.0
    schema = manifest.goal_params_schema
    assert schema is not None
    assert schema["properties"]["velocity_commands"]["minItems"] == 3
    assert manifest.starting_pose == [
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
        -0.1,
        0.9,
        -1.8,
        0.1,
        0.9,
        -1.8,
    ]
    assert repo_name_is_canonical(
        manifest.name, kind=manifest.kind, model_family=manifest.model_family
    )


def test_deploy_yaml_matches_hub_go2_velocity_flat() -> None:
    """Keys and widths come from the Hub deploy.yaml — not invented."""
    cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    assert [name for name, _scale in cfg.observation_terms] == [
        "base_ang_vel",
        "projected_gravity",
        "velocity_commands",
        "joint_pos_rel",
        "joint_vel_rel",
        "last_action",
    ]
    assert cfg.observation_dim == 45
    assert cfg.action_dim == 12
    assert cfg.joint_ids_map.tolist() == [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]
    np.testing.assert_allclose(
        cfg.default_joint_pos,
        [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8],
    )
    np.testing.assert_allclose(cfg.action_scale, np.full(12, 0.5))
    assert cfg.term_history_lengths == (1, 1, 1, 1, 1, 1)
    assert cfg.frame_dim == 45
    assert cfg.gait_cycle_s is None


def test_velocity_commands_come_from_extras_not_prompt() -> None:
    np.testing.assert_allclose(resolve_velocity_commands({}), [0.5, 0.0, 0.0])
    np.testing.assert_allclose(
        resolve_velocity_commands({"velocity_commands": [1.0, -0.2, 0.3]}),
        [1.0, -0.2, 0.3],
    )


def test_coast_to_stand_zeros_joystick_in_the_trailing_window() -> None:
    """Last coast_to_stand_s of the budget must command stand, not keep walking.

    Deadline idle-hold of a mid-gait waypoint is what dumps the Go2.
    """
    walk = (0.5, 0.0, 0.0)
    assert in_coast_to_stand_window(
        elapsed_s=54.0, budget_s=57.0, coast_to_stand_s=3.0
    )
    np.testing.assert_allclose(
        coast_velocity_commands(
            walk, elapsed_s=54.0, budget_s=57.0, coast_to_stand_s=3.0
        ),
        [0.0, 0.0, 0.0],
    )
    assert not in_coast_to_stand_window(
        elapsed_s=50.0, budget_s=57.0, coast_to_stand_s=3.0
    )
    np.testing.assert_allclose(
        coast_velocity_commands(
            walk, elapsed_s=50.0, budget_s=57.0, coast_to_stand_s=3.0
        ),
        walk,
    )
    np.testing.assert_allclose(
        coast_velocity_commands(
            walk, elapsed_s=99.0, budget_s=57.0, coast_to_stand_s=None
        ),
        walk,
    )


def test_coast_to_stand_defaults_on_rsl_rl_onnx_and_zero_disables() -> None:
    assert resolve_coast_to_stand_s({}, family=RSL_RL_ONNX_FAMILY) == 3.0
    assert resolve_coast_to_stand_s({}, family="zero") is None
    assert resolve_coast_to_stand_s({"coast_to_stand_s": 0}, family=RSL_RL_ONNX_FAMILY) is None
    assert resolve_coast_to_stand_s({"coast_to_stand_s": 2.5}) == 2.5
    assert resolve_coast_budget_s({"horizon_s": 57.0}, max_execution_s=60.0) == 57.0
    assert resolve_coast_budget_s({}, max_execution_s=60.0) == 60.0
    assert resolve_coast_budget_s({}) is None


def test_goal_params_override_beats_yaml_default() -> None:
    """execute_rskill / verify goal_params_json wins over policy_extras."""
    yaml_default = resolve_velocity_commands({"velocity_commands": [0.5, 0.0, 0.0]})
    np.testing.assert_allclose(yaml_default, [0.5, 0.0, 0.0])
    override = velocity_override_from_goal_params('{"velocity_commands": [1.2, -0.1, 0.4]}')
    assert override is not None
    np.testing.assert_allclose(override, [1.2, -0.1, 0.4])
    assert velocity_override_from_goal_params("") is None
    assert velocity_override_from_goal_params("{}") is None
    with pytest.raises(ROSConfigError, match="not valid JSON"):
        velocity_override_from_goal_params("{")
    with pytest.raises(ROSConfigError, match="3-vector"):
        velocity_override_from_goal_params('{"velocity_commands": [1.0, 0.0]}')


def test_apply_velocity_command_override_restores_default() -> None:
    class _Stub:
        def __init__(self) -> None:
            self.commands = np.array([0.5, 0.0, 0.0], dtype=np.float32)

        def set_velocity_commands(self, commands: object | None) -> None:
            if commands is None:
                self.commands = np.array([0.5, 0.0, 0.0], dtype=np.float32)
                return
            self.commands = np.asarray(commands, dtype=np.float32)

    stub = _Stub()
    applied = apply_velocity_command_override(stub, {"velocity_commands": [0.8, 0.0, 0.0]})
    assert applied is not None
    np.testing.assert_allclose(stub.commands, [0.8, 0.0, 0.0])
    restored = apply_velocity_command_override(stub, "")
    assert restored is None
    np.testing.assert_allclose(stub.commands, [0.5, 0.0, 0.0])


def test_projected_gravity_identity_quat() -> None:
    g = projected_gravity_from_quat_xyzw(np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32))
    np.testing.assert_allclose(g, [0.0, 0.0, -1.0], atol=1e-6)


def test_observation_and_action_use_joint_ids_map() -> None:
    cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    robot_q = cfg.default_joint_pos.copy()
    obs = build_rsl_rl_observation(
        config=cfg,
        joint_pos=robot_q,
        joint_vel=np.zeros(12, dtype=np.float32),
        base_ang_vel=np.zeros(3, dtype=np.float32),
        projected_gravity=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        velocity_commands=np.array([0.5, 0.0, 0.0], dtype=np.float32),
        last_action=np.zeros(12, dtype=np.float32),
    )
    assert obs.shape == (45,)
    # At the default stand, joint_pos_rel is zeros in policy order.
    np.testing.assert_allclose(obs[9:21], 0.0, atol=1e-6)
    np.testing.assert_allclose(obs[6:9], [0.5, 0.0, 0.0])

    raw = np.zeros(12, dtype=np.float32)
    raw[0] = 2.0  # policy slot 0 → robot joint 3 (FR hip)
    decoded = decode_rsl_rl_joint_position(raw, cfg)
    assert decoded.shape == (12,)
    np.testing.assert_allclose(decoded[3], 0.1 + 0.5 * 2.0)
    np.testing.assert_allclose(decoded[0], -0.1)


def test_joint_order_defaults_to_the_policys_own_not_the_sdk_permutation() -> None:
    """A MuJoCo twin speaks the policy's joint order, so the SDK map must not apply.

    `deploy.yaml`'s `joint_ids_map` converts between the policy's order and the
    Unitree SDK's real-robot order (`FR, FL, RR, RL` vs menagerie's
    `FL, FR, RL, RR`). Applying it to a sim twin sends every leg's command to
    its mirror. The permutation is self-inverse, so gather-vs-scatter direction
    cannot rescue it — measured offline at a true 50 Hz, 20 s at [0.5, 0, 0]:
    7.07 m upright with identity, 0.30 m and collapsed with the map.
    """
    yaml_cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    # The fixture really is the mirroring permutation, and really is an involution.
    assert yaml_cfg.joint_ids_map.tolist() == [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]
    round_trip = yaml_cfg.joint_ids_map[yaml_cfg.joint_ids_map]
    np.testing.assert_array_equal(round_trip, np.arange(12))

    default = _apply_joint_order(yaml_cfg, {})
    np.testing.assert_array_equal(default.joint_ids_map, np.arange(12))

    sdk = _apply_joint_order(yaml_cfg, {"joint_order": "unitree_sdk"})
    np.testing.assert_array_equal(sdk.joint_ids_map, yaml_cfg.joint_ids_map)

    with pytest.raises(ROSConfigError, match="joint_order"):
        _apply_joint_order(yaml_cfg, {"joint_order": "isaac"})


def test_joint_order_decides_which_leg_an_action_reaches() -> None:
    """The consequence the gait cares about: slot 0 must drive FL, not FR."""
    yaml_cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    raw = np.zeros(12, dtype=np.float32)
    raw[0] = 2.0

    native = decode_rsl_rl_joint_position(raw, _apply_joint_order(yaml_cfg, {}))
    np.testing.assert_allclose(native[0], -0.1 + 0.5 * 2.0)  # FL hip moved
    np.testing.assert_allclose(native[3], 0.1)  # FR hip untouched

    sdk = decode_rsl_rl_joint_position(
        raw, _apply_joint_order(yaml_cfg, {"joint_order": "unitree_sdk"})
    )
    np.testing.assert_allclose(sdk[3], 0.1 + 0.5 * 2.0)  # mirrored onto FR
    np.testing.assert_allclose(sdk[0], -0.1)


def _zero_action_policy(tmp_path: Path, extra: dict[str, object] | None = None) -> Any:
    """Build the real adapter over a zero-action ONNX graph + the Hub deploy.yaml."""
    cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "params").mkdir()
    (skill_dir / "params" / "deploy.yaml").write_text(
        _DEPLOY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (skill_dir / "rskill.yaml").write_text(_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    write_zero_action_onnx(
        skill_dir / "policy.onnx",
        observation_dim=cfg.observation_dim,
        action_dim=cfg.action_dim,
    )
    merged: dict[str, object] = {"velocity_commands": [0.4, 0.0, 0.0]}
    if extra:
        merged.update(extra)

    env = SimpleNamespace(
        vla=VLASpec(
            id=RSL_RL_ONNX_FAMILY,
            weights_uri=str(skill_dir),
            device="cpu",
            extra=merged,
        ),
        scene=SimpleNamespace(cameras=()),
    )
    return make_policy(env)  # type: ignore[arg-type]


def _stand_obs(cfg: Any) -> dict[str, object]:
    return {
        "state": cfg.default_joint_pos,
        "joint_vel": np.zeros(12, dtype=np.float32),
        "base_twist": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        "base_pose": {
            "xyz": (0.0, 0.0, 0.4),
            "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
        },
    }


def _frame_velocity_commands(cfg: Any, frame: np.ndarray) -> np.ndarray:
    offset = 0
    for name, scale in cfg.observation_terms:
        width = int(scale.shape[0])
        if name == "velocity_commands":
            return np.asarray(frame[offset : offset + width], dtype=np.float32)
        offset += width
    raise AssertionError("deploy.yaml has no velocity_commands term")


def test_goal_params_override_reaches_the_real_adapter(tmp_path: Path) -> None:
    """A goal_params joystick must survive the adapter's own re-validation.

    ``apply_velocity_command_override`` hands ``set_velocity_commands`` the
    float32 array it just built, and that setter re-validates what it is given.
    While the validator rejected ``ndarray``, every ``goal_params_json``
    override aborted its goal with ``ROSConfigError`` before a single chunk
    was published. The stub in the sibling test coerces with ``np.asarray``
    and so is blind to this — the regression only shows against a real adapter.
    """
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

    policy = _zero_action_policy(tmp_path)
    try:
        applied = apply_velocity_command_override(policy, '{"velocity_commands": [0.7, -0.2, 0.3]}')
        assert applied is not None
        np.testing.assert_allclose(policy._velocity_commands, [0.7, -0.2, 0.3])
        # Empty payload restores the manifest default rather than sticking.
        assert apply_velocity_command_override(policy, "") is None
        np.testing.assert_allclose(policy._velocity_commands, [0.4, 0.0, 0.0])
        # Second execute_rskill reuses the resident adapter; leftover last_action
        # is the Go2 "stands still on the next skill" observation leak.
        policy._last_action = np.ones(12, dtype=np.float32)
        policy.reset()
        np.testing.assert_allclose(policy._last_action, 0.0)
    finally:
        policy.close()


def test_make_policy_emits_12d_joint_positions(tmp_path: Path) -> None:
    """``make_policy`` loads a real ONNX session and emits 12-D targets."""
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

    cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    policy = _zero_action_policy(tmp_path)
    try:
        policy.reset()
        action = policy.step(
            {
                "state": cfg.default_joint_pos,
                "joint_vel": np.zeros(12, dtype=np.float32),
                "base_twist": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                "base_pose": {
                    "xyz": (0.0, 0.0, 0.4),
                    "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
                },
            },
            "walk forward",  # prompt must not be required to produce an action
        )
        assert action.shape == (12,)
        assert action.dtype == np.float32
        # Zero raw action → default stand in robot / HAL order.
        np.testing.assert_allclose(action, cfg.default_joint_pos, atol=1e-5)

        # Public setter + per-step obs override beat the load-time extra.
        policy.set_velocity_commands([0.4, 0.0, 0.0])
        policy.step(
            {
                "state": cfg.default_joint_pos,
                "joint_vel": np.zeros(12, dtype=np.float32),
                "base_twist": (0.0, 0.0, 0.0, 0.1, 0.0, 0.0),
                "base_pose": {
                    "xyz": (0.0, 0.0, 0.4),
                    "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
                },
                "velocity_commands": [1.0, 0.0, 0.25],
            },
            "walk forward",
        )
        np.testing.assert_allclose(policy._velocity_commands, [0.4, 0.0, 0.0])
        policy.set_velocity_commands([1.0, 0.0, 0.25])
        np.testing.assert_allclose(policy._velocity_commands, [1.0, 0.0, 0.25])
        policy.set_velocity_commands(None)
        np.testing.assert_allclose(policy._velocity_commands, [0.4, 0.0, 0.0])
        assert policy._coast_to_stand_s == 3.0
        assert policy._coast_budget_s == 57.0
    finally:
        policy.close()


def test_adapter_zeros_joystick_on_the_step_clock(tmp_path: Path) -> None:
    """The ONNX obs must see [0,0,0] in the trailing window, not keep walking.

    Helpers already cover the window arithmetic. This is the adapter
    ``step()`` path: deadline idle-hold of a mid-gait waypoint is what
    dumps the Go2, so the joystick in the recorded frame must actually
    change.
    """
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

    cfg = load_rsl_rl_deploy_yaml(_DEPLOY)
    policy = _zero_action_policy(
        tmp_path,
        extra={"horizon_s": 1.0, "coast_to_stand_s": 0.4, "velocity_commands": [0.4, 0.0, 0.0]},
    )
    try:
        policy.reset()
        obs = _stand_obs(cfg)
        walk_ticks = int((1.0 - 0.4) / cfg.step_dt)
        for _ in range(walk_ticks):
            policy.step(obs, "")
        np.testing.assert_allclose(
            _frame_velocity_commands(cfg, policy._history[-1]),
            [0.4, 0.0, 0.0],
        )
        while float(policy._step_index) * cfg.step_dt < 1.0:
            policy.step(obs, "")
        np.testing.assert_allclose(
            _frame_velocity_commands(cfg, policy._history[-1]),
            [0.0, 0.0, 0.0],
        )
        assert policy._coast_to_stand_s == 0.4
        assert policy._coast_budget_s == 1.0
    finally:
        policy.close()


def test_imu_terms_use_pose_when_present() -> None:
    _OBS_FALLBACK_WARNED.clear()
    ang = _base_ang_vel_from_obs({"base_twist": (0.1, 0.0, 0.0, 0.2, -0.3, 0.4)})
    np.testing.assert_allclose(ang, [0.2, -0.3, 0.4])
    g = _projected_gravity_from_obs(
        {"base_pose": {"xyz": (0.0, 0.0, 0.4), "quat_xyzw": (0.0, 0.0, 0.0, 1.0)}}
    )
    np.testing.assert_allclose(g, [0.0, 0.0, -1.0], atol=1e-6)
    assert "base_ang_vel" not in _OBS_FALLBACK_WARNED
    assert "projected_gravity" not in _OBS_FALLBACK_WARNED


def test_imu_terms_warn_and_fallback_without_pose() -> None:
    _OBS_FALLBACK_WARNED.clear()
    with capture_logs() as logs:
        ang = _base_ang_vel_from_obs({})
        g = _projected_gravity_from_obs({})
    np.testing.assert_allclose(ang, [0.0, 0.0, 0.0])
    np.testing.assert_allclose(g, [0.0, 0.0, -1.0])
    events = [row for row in logs if row.get("event") == "rsl_rl_onnx.obs_fallback"]
    terms = {row.get("term") for row in events}
    assert terms == {"base_ang_vel", "projected_gravity"}
    # Second call is silent (one-shot).
    with capture_logs() as logs2:
        _base_ang_vel_from_obs({})
        _projected_gravity_from_obs({})
    assert not [row for row in logs2 if row.get("event") == "rsl_rl_onnx.obs_fallback"]


def test_attach_locomotion_proprio_copies_pose_and_override() -> None:
    """Runner helper fills IMU terms when WorldState has pose; leaves them unset otherwise."""
    from openral_rskill_ros.rskill_runner_node import _attach_locomotion_proprio

    with_pose = SimpleNamespace(
        joint_state=SimpleNamespace(position=[0.1] * 12, velocity=[0.01] * 12),
        base_twist=(0.2, 0.0, 0.0, 0.05, -0.1, 0.3),
        base_pose=SimpleNamespace(
            xyz=(0.0, 0.0, 0.4),
            quat_xyzw=(0.0, 0.0, 0.0, 1.0),
        ),
    )
    obs: dict[str, object] = {}
    _attach_locomotion_proprio(obs, with_pose)
    assert obs["joint_pos"] == [0.1] * 12
    assert obs["joint_vel"] == [0.01] * 12
    assert obs["base_twist"] == (0.2, 0.0, 0.0, 0.05, -0.1, 0.3)
    assert obs["base_ang_vel"] == (0.05, -0.1, 0.3)
    assert obs["base_pose"] == {
        "xyz": (0.0, 0.0, 0.4),
        "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
    }

    empty: dict[str, object] = {}
    _attach_locomotion_proprio(
        empty, SimpleNamespace(joint_state=None, base_twist=None, base_pose=None)
    )
    assert "base_ang_vel" not in empty
    assert "base_pose" not in empty


def test_intree_hop_manifest_from_yaml() -> None:
    manifest = RSkillManifest.from_yaml(str(_HOP_MANIFEST))
    assert manifest.kind == "vla"
    assert manifest.model_family == RSL_RL_ONNX_FAMILY
    assert manifest.license.value == "unknown"
    assert not manifest.is_commercial_use_allowed
    assert manifest.weights_uri == "local://rskills/rsl-rl-onnx-go2-hop-flat"
    extras = manifest.policy_extras
    assert extras.get("onnx_filename") == "policy.onnx"
    assert extras.get("deploy_yaml") == "params/deploy.yaml"
    assert extras.get("velocity_commands") == [0.0, 0.0, 0.0]
    assert str(extras.get("onnx_url", "")).startswith("https://")
    assert "mjlab/hop/policy.onnx" in str(extras.get("onnx_url"))
    assert manifest.starting_pose == [
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
    ]
    assert repo_name_is_canonical(
        manifest.name, kind=manifest.kind, model_family=manifest.model_family
    )
    from openral_hal.go2 import GO2_HOP_JOINT_TARGETS, GO2_HOP_PD_KP, GO2_HOP_PD_KV

    assert list(manifest.starting_pose) == list(GO2_HOP_JOINT_TARGETS)
    assert GO2_HOP_PD_KP == 20.0
    assert GO2_HOP_PD_KV == 0.5


def test_hop_deploy_yaml_is_470d_term_major() -> None:
    cfg = load_rsl_rl_deploy_yaml(_HOP_DEPLOY)
    assert [name for name, _scale in cfg.observation_terms] == [
        "gait_phase_2",
        "velocity_commands",
        "base_ang_vel_B",
        "eulerZYX_rpy",
        "joint_pos_rel",
        "joint_vel_rel",
        "last_action",
    ]
    assert cfg.frame_dim == 47
    assert cfg.observation_dim == 470
    assert cfg.term_history_lengths == (10, 10, 10, 10, 10, 10, 10)
    assert cfg.history_order == "oldest_first"
    assert cfg.history_warmup == "repeat_first"
    assert cfg.history_layout == "term_major"
    assert cfg.action_clip is None
    assert cfg.constant_terms == ()
    assert cfg.gait_cycle_s == 1.5
    assert cfg.action_dim == 12
    np.testing.assert_allclose(cfg.action_scale, np.full(12, 0.25))
    np.testing.assert_allclose(
        cfg.default_joint_pos,
        [0.1, 0.8, -1.5, -0.1, 0.8, -1.5, 0.1, 1.0, -1.5, -0.1, 1.0, -1.5],
    )
    from openral_hal.go2 import GO2_HOP_JOINT_TARGETS

    np.testing.assert_allclose(cfg.default_joint_pos, GO2_HOP_JOINT_TARGETS)
    raw = _HOP_DEPLOY.read_text(encoding="utf-8")
    assert "stiffness:" in raw
    assert "damping:" in raw


def test_gait_phase_and_identity_euler() -> None:
    np.testing.assert_allclose(gait_phase_2(step_index=0, step_dt=0.02, cycle_s=1.5), [0.0, 1.0])
    rpy = euler_rpy_from_quat_xyzw(np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32))
    np.testing.assert_allclose(rpy, [0.0, 0.0, 0.0], atol=1e-6)


def test_hop_history_repeat_first_then_rolls() -> None:
    cfg = load_rsl_rl_deploy_yaml(_HOP_DEPLOY)
    frame0 = np.arange(cfg.frame_dim, dtype=np.float32)
    stacked0 = stack_rsl_rl_term_major_history(frame0, [], cfg)
    assert stacked0.shape == (470,)
    # oldest_first + empty history → ten copies of frame0, per term.
    gait = stacked0[:20]
    np.testing.assert_allclose(gait, np.tile(frame0[:2], 10))

    frame1 = frame0 + 100.0
    stacked1 = stack_rsl_rl_term_major_history(frame1, [frame0], cfg)
    # lag 9..1 still frame0 (repeat_first / only one previous), lag 0 is frame1.
    np.testing.assert_allclose(stacked1[0:18], np.tile(frame0[:2], 9))
    np.testing.assert_allclose(stacked1[18:20], frame1[:2])


def test_hop_frame_uses_gait_and_euler_not_projected_gravity() -> None:
    cfg = load_rsl_rl_deploy_yaml(_HOP_DEPLOY)
    gait = gait_phase_2(step_index=0, step_dt=cfg.step_dt, cycle_s=cfg.gait_cycle_s or 1.5)
    frame = build_rsl_rl_observation(
        config=cfg,
        joint_pos=cfg.default_joint_pos,
        joint_vel=np.zeros(12, dtype=np.float32),
        base_ang_vel=np.array([0.1, -0.2, 0.3], dtype=np.float32),
        projected_gravity=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        velocity_commands=np.array([0.0, 0.0, 0.0], dtype=np.float32),
        last_action=np.zeros(12, dtype=np.float32),
        gait_phase=gait,
        euler_rpy=np.zeros(3, dtype=np.float32),
    )
    assert frame.shape == (47,)
    np.testing.assert_allclose(frame[0:2], [0.0, 1.0])
    np.testing.assert_allclose(frame[2:5], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(frame[5:8], [0.1, -0.2, 0.3])
    np.testing.assert_allclose(frame[8:11], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(frame[11:23], 0.0)  # at default stand


def _hop_zero_action_policy(tmp_path: Path) -> Any:
    cfg = load_rsl_rl_deploy_yaml(_HOP_DEPLOY)
    skill_dir = tmp_path / "hop_skill"
    skill_dir.mkdir()
    (skill_dir / "params").mkdir()
    (skill_dir / "params" / "deploy.yaml").write_text(
        _HOP_DEPLOY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (skill_dir / "rskill.yaml").write_text(
        _HOP_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_zero_action_onnx(
        skill_dir / "policy.onnx",
        observation_dim=cfg.observation_dim,
        action_dim=cfg.action_dim,
    )
    env = SimpleNamespace(
        vla=VLASpec(
            id=RSL_RL_ONNX_FAMILY,
            weights_uri=str(skill_dir),
            device="cpu",
            extra={"velocity_commands": [0.0, 0.0, 0.0]},
        ),
        scene=SimpleNamespace(cameras=()),
    )
    return make_policy(env)  # type: ignore[arg-type]


def test_hop_make_policy_emits_12d_and_resets_history(tmp_path: Path) -> None:
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

    cfg = load_rsl_rl_deploy_yaml(_HOP_DEPLOY)
    policy = _hop_zero_action_policy(tmp_path)
    try:
        policy.reset()
        obs = {
            "state": cfg.default_joint_pos,
            "joint_vel": np.zeros(12, dtype=np.float32),
            "base_twist": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "base_pose": {
                "xyz": (0.0, 0.0, 0.4),
                "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
            },
        }
        action = policy.step(obs, "hop")
        assert action.shape == (12,)
        np.testing.assert_allclose(action, cfg.default_joint_pos, atol=1e-5)
        assert policy._step_index == 1
        assert len(policy._history) == 1
        policy.reset()
        assert policy._step_index == 0
        assert len(policy._history) == 0
    finally:
        policy.close()


def test_intree_spring_jump_manifest_from_yaml() -> None:
    manifest = RSkillManifest.from_yaml(str(_SPRING_MANIFEST))
    assert manifest.kind == "vla"
    assert manifest.model_family == RSL_RL_ONNX_FAMILY
    assert manifest.license.value == "unknown"
    assert not manifest.is_commercial_use_allowed
    assert manifest.weights_uri == "local://rskills/rsl-rl-onnx-go2-spring-jump"
    extras = manifest.policy_extras
    assert extras.get("onnx_filename") == "policy.onnx"
    assert extras.get("deploy_yaml") == "params/deploy.yaml"
    assert extras.get("jump_trigger") == 1.0
    assert "spring_jump/policy.onnx" in str(extras.get("onnx_url"))
    assert manifest.starting_pose == [
        0.0,
        0.8,
        -1.5,
        0.0,
        0.8,
        -1.5,
        0.0,
        1.0,
        -1.5,
        0.0,
        1.0,
        -1.5,
    ]
    assert repo_name_is_canonical(
        manifest.name, kind=manifest.kind, model_family=manifest.model_family
    )


def test_spring_jump_deploy_yaml_is_470d_frame_major() -> None:
    cfg = load_rsl_rl_deploy_yaml(_SPRING_DEPLOY)
    assert [name for name, _scale in cfg.observation_terms] == [
        "constants",
        "joystick_buttons",
        "base_ang_vel_B",
        "eulerZYX_rpy",
        "joint_pos",
        "joint_vel",
        "last_action",
    ]
    assert cfg.frame_dim == 47
    assert cfg.observation_dim == 470
    assert cfg.term_history_lengths == (10, 10, 10, 10, 10, 10, 10)
    assert cfg.history_order == "oldest_first"
    assert cfg.history_warmup == "zero"
    assert cfg.history_layout == "frame_major"
    assert cfg.action_clip == 100.0
    assert cfg.gait_cycle_s is None
    assert len(cfg.constant_terms) == 1
    np.testing.assert_allclose(cfg.constant_terms[0][1], [0.0, 0.0, 0.7, 0.0])
    np.testing.assert_allclose(cfg.action_scale, np.full(12, 0.25))
    manifest = RSkillManifest.from_yaml(str(_SPRING_MANIFEST))
    np.testing.assert_allclose(cfg.default_joint_pos, manifest.starting_pose)


def test_spring_jump_frame_major_zero_warmup_then_rolls() -> None:
    cfg = load_rsl_rl_deploy_yaml(_SPRING_DEPLOY)
    frame0 = np.arange(cfg.frame_dim, dtype=np.float32)
    stacked0 = stack_rsl_rl_frame_major_history(frame0, [], cfg)
    assert stacked0.shape == (470,)
    np.testing.assert_allclose(stacked0[: cfg.frame_dim * 9], 0.0)
    np.testing.assert_allclose(stacked0[cfg.frame_dim * 9 :], frame0)

    frame1 = frame0 + 100.0
    stacked1 = stack_rsl_rl_frame_major_history(frame1, [frame0], cfg)
    np.testing.assert_allclose(stacked1[: cfg.frame_dim * 8], 0.0)
    np.testing.assert_allclose(stacked1[cfg.frame_dim * 8 : cfg.frame_dim * 9], frame0)
    np.testing.assert_allclose(stacked1[cfg.frame_dim * 9 :], frame1)


def test_spring_jump_frame_uses_constants_and_joystick() -> None:
    cfg = load_rsl_rl_deploy_yaml(_SPRING_DEPLOY)
    frame = build_rsl_rl_observation(
        config=cfg,
        joint_pos=cfg.default_joint_pos,
        joint_vel=np.zeros(12, dtype=np.float32),
        base_ang_vel=np.array([0.4, -0.8, 1.2], dtype=np.float32),
        projected_gravity=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        velocity_commands=np.array([0.0, 0.0, 0.0], dtype=np.float32),
        last_action=np.zeros(12, dtype=np.float32),
        euler_rpy=np.zeros(3, dtype=np.float32),
        joystick_buttons=np.array([1.0], dtype=np.float32),
    )
    assert frame.shape == (47,)
    np.testing.assert_allclose(frame[0:4], [0.0, 0.0, 0.7, 0.0])
    np.testing.assert_allclose(frame[4:5], [1.0])
    np.testing.assert_allclose(frame[5:8], [0.1, -0.2, 0.3])
    np.testing.assert_allclose(frame[8:11], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(frame[11:23], 0.0)


def _spring_zero_action_policy(tmp_path: Path) -> Any:
    cfg = load_rsl_rl_deploy_yaml(_SPRING_DEPLOY)
    skill_dir = tmp_path / "spring_skill"
    skill_dir.mkdir()
    (skill_dir / "params").mkdir()
    (skill_dir / "params" / "deploy.yaml").write_text(
        _SPRING_DEPLOY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (skill_dir / "rskill.yaml").write_text(
        _SPRING_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_zero_action_onnx(
        skill_dir / "policy.onnx",
        observation_dim=cfg.observation_dim,
        action_dim=cfg.action_dim,
    )
    env = SimpleNamespace(
        vla=VLASpec(
            id=RSL_RL_ONNX_FAMILY,
            weights_uri=str(skill_dir),
            device="cpu",
            extra={"jump_trigger": 1.0},
        ),
        scene=SimpleNamespace(cameras=()),
    )
    return make_policy(env)  # type: ignore[arg-type]


def test_spring_jump_make_policy_emits_12d(tmp_path: Path) -> None:
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

    cfg = load_rsl_rl_deploy_yaml(_SPRING_DEPLOY)
    policy = _spring_zero_action_policy(tmp_path)
    try:
        policy.reset()
        obs = {
            "state": cfg.default_joint_pos,
            "joint_vel": np.zeros(12, dtype=np.float32),
            "base_twist": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "base_pose": {
                "xyz": (0.0, 0.0, 0.4),
                "quat_xyzw": (0.0, 0.0, 0.0, 1.0),
            },
        }
        action = policy.step(obs, "hop")
        assert action.shape == (12,)
        np.testing.assert_allclose(action, cfg.default_joint_pos, atol=1e-5)
        assert policy._joystick_buttons.tolist() == [1.0]
        assert policy._config.history_layout == "frame_major"
    finally:
        policy.close()
