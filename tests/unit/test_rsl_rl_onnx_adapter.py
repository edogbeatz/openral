"""Unit tests for the ``rsl_rl_onnx`` ModelFamily + ONNX locomotion adapter.

Exercises the real Hub ``params/deploy.yaml`` layout (copied under
``tests/unit/fixtures/rsl_rl_onnx/``), the in-tree rSkill manifest, and a
real ONNX Runtime session against a tiny fixture graph. No SmolVLA path.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import get_args

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
    _base_ang_vel_from_obs,
    _projected_gravity_from_obs,
    apply_velocity_command_override,
    build_rsl_rl_observation,
    decode_rsl_rl_joint_position,
    load_rsl_rl_deploy_yaml,
    projected_gravity_from_quat_xyzw,
    resolve_velocity_commands,
    velocity_override_from_goal_params,
    write_zero_action_onnx,
)
from openral_sim.registry import POLICIES
from structlog.testing import capture_logs

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO / "rskills" / "rsl-rl-onnx-go2-velocity-flat" / "rskill.yaml"
_DEPLOY = Path(__file__).resolve().parent / "fixtures" / "rsl_rl_onnx" / "deploy.yaml"


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


def test_velocity_commands_come_from_extras_not_prompt() -> None:
    np.testing.assert_allclose(resolve_velocity_commands({}), [0.5, 0.0, 0.0])
    np.testing.assert_allclose(
        resolve_velocity_commands({"velocity_commands": [1.0, -0.2, 0.3]}),
        [1.0, -0.2, 0.3],
    )


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


def test_make_policy_emits_12d_joint_positions(tmp_path: Path) -> None:
    """``make_policy`` loads a real ONNX session and emits 12-D targets."""
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")

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

    env = SimpleNamespace(
        vla=VLASpec(
            id=RSL_RL_ONNX_FAMILY,
            weights_uri=str(skill_dir),
            device="cpu",
            extra={"velocity_commands": [0.4, 0.0, 0.0]},
        ),
        scene=SimpleNamespace(cameras=()),
    )
    policy = make_policy(env)  # type: ignore[arg-type]
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
