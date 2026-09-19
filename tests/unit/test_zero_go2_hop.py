"""Scripted Go2 hop (``model_family: zero``, ``gait: jump``)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from openral_core import RSkillManifest, VLASpec
from openral_core.schemas import repo_name_is_canonical
from openral_hal.go2 import GO2_HOP_JOINT_TARGETS
from openral_rskill.loader import rSkill
from openral_sim.factory import make_policy
from openral_sim.policies.mock import (
    _GO2_JUMP_CROUCH,
    _GO2_JUMP_EXTEND,
    _GO2_JUMP_STAND,
    _GO2_JUMP_TUCK,
    _jump_leg_targets,
    _jump_phase_ticks,
    _ZeroPolicy,
)

_PKG = Path("rskills/rskill-zero-go2-hop-fp32")


def test_jump_stand_matches_hal_hop_stand() -> None:
    np.testing.assert_allclose(_GO2_JUMP_STAND, GO2_HOP_JOINT_TARGETS)


def test_manifest_loads_and_is_canonical() -> None:
    skill = rSkill.from_yaml(str(_PKG / "rskill.yaml"))
    manifest = skill.manifest
    assert isinstance(manifest, RSkillManifest)
    assert manifest.model_family == "zero"
    assert manifest.embodiment_tags == ["go2", "go2_z1"]
    assert manifest.action_contract is not None
    assert manifest.action_contract.dim == 12
    assert repo_name_is_canonical(
        manifest.name, kind=manifest.kind, model_family=manifest.model_family
    )
    extras = manifest.policy_extras
    assert extras["gait"] == "jump"
    np.testing.assert_allclose(extras["hold_targets"], GO2_HOP_JOINT_TARGETS)
    np.testing.assert_allclose(extras["jump_crouch"], _GO2_JUMP_CROUCH)
    np.testing.assert_allclose(extras["jump_extend"], _GO2_JUMP_EXTEND)
    np.testing.assert_allclose(extras["jump_tuck"], _GO2_JUMP_TUCK)
    assert extras["jump_crouch_s"] == 0.30
    assert extras["jump_extend_s"] == 0.24
    assert extras["jump_tuck_s"] == 0.22
    assert extras["jump_recover_s"] == 0.40
    assert manifest.starting_pose is not None
    np.testing.assert_allclose(manifest.starting_pose, GO2_HOP_JOINT_TARGETS)


def test_jump_gait_cycles_crouch_extend_tuck_land() -> None:
    policy = _ZeroPolicy(
        spec=VLASpec(id="zero", weights_uri="local://rskills/rskill-zero-go2-hop-fp32"),
        device="cpu",
        action_dim=12,
        hold_targets=np.asarray(GO2_HOP_JOINT_TARGETS, dtype=np.float32),
        gait="jump",
        dt=0.02,
    )
    first = policy.step({}, "")
    np.testing.assert_allclose(first, _jump_leg_targets(1, dt=0.02))
    crouch_ticks, extend_ticks, tuck_ticks, _recover = _jump_phase_ticks(dt=0.02)
    policy.reset()
    for _ in range(crouch_ticks):
        row = policy.step({}, "")
    np.testing.assert_allclose(row[2], -2.65, atol=1e-6)
    for _ in range(extend_ticks):
        row = policy.step({}, "")
    np.testing.assert_allclose(row[2], -0.84, atol=1e-6)
    for _ in range(tuck_ticks):
        row = policy.step({}, "")
    np.testing.assert_allclose(row[2], -2.30, atol=1e-6)
    row = policy.step({}, "")
    np.testing.assert_allclose(row, GO2_HOP_JOINT_TARGETS, atol=1e-6)


def test_jump_gait_keeps_trailing_arm_on_19d() -> None:
    hold = np.array(
        [*GO2_HOP_JOINT_TARGETS, 0.0, 1.2, -1.0, -0.4, 0.0, 0.0, 0.0],
        dtype=np.float32,
    )
    policy = _ZeroPolicy(
        spec=VLASpec(id="zero", weights_uri="local://rskills/rskill-zero-go2-hop-fp32"),
        device="cpu",
        action_dim=19,
        hold_targets=hold,
        gait="jump",
        dt=0.02,
    )
    row = policy.step({}, "")
    assert row.shape == (19,)
    np.testing.assert_allclose(row[12:], hold[12:])
    assert not np.allclose(row[:12], hold[:12])


def test_make_policy_reads_jump_cycle_from_manifest() -> None:
    skill = rSkill.from_yaml(str(_PKG / "rskill.yaml"))
    policy = make_policy(
        SimpleNamespace(
            vla=VLASpec(
                id="zero",
                weights_uri="local://rskills/rskill-zero-go2-hop-fp32",
                device="cpu",
                extra=dict(skill.manifest.policy_extras),
            ),
            scene=SimpleNamespace(cameras=()),
        )
    )
    assert isinstance(policy, _ZeroPolicy)
    assert policy.gait == "jump"
    assert policy.jump_extend_s == 0.24
    assert policy.jump_tuck_s == 0.22
    assert policy.jump_extend is not None
    np.testing.assert_allclose(policy.jump_extend[2], -0.84, atol=1e-6)
