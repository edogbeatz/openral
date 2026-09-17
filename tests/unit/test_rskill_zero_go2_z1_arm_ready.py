"""The Go2+Z1 arm-ready rSkill is a real in-tree fixture, not a placeholder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from openral_core import RSkillManifest
from openral_hal.go2 import GO2_HOME_JOINT_TARGETS
from openral_hal.go2_z1 import GO2_Z1_ARM_FOLD, GO2_Z1_ARM_HOME, GO2_Z1_ARM_READY
from openral_rskill.loader import rSkill

_PKG = Path("rskills/rskill-zero-go2_z1-arm_ready-fp32")


def test_manifest_loads_and_is_canonical() -> None:
    from openral_core.schemas import repo_name_is_canonical

    skill = rSkill.from_yaml(str(_PKG / "rskill.yaml"))
    manifest = skill.manifest
    assert isinstance(manifest, RSkillManifest)
    assert manifest.model_family == "zero"
    assert manifest.embodiment_tags == ["go2_z1"]
    assert manifest.action_contract is not None
    assert manifest.action_contract.dim == 19
    assert repo_name_is_canonical(
        manifest.name, kind=manifest.kind, model_family=manifest.model_family
    )


def test_controller_json_poses_match_hal_constants() -> None:
    raw = json.loads((_PKG / "controller.json").read_text(encoding="utf-8"))
    np.testing.assert_allclose(raw["poses"]["ready"], GO2_Z1_ARM_READY)
    np.testing.assert_allclose(raw["poses"]["home"], GO2_Z1_ARM_HOME)
    np.testing.assert_allclose(raw["poses"]["fold"], GO2_Z1_ARM_FOLD)
    expected_hold = [*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY]
    np.testing.assert_allclose(raw["hold_targets"], expected_hold)


def test_manifest_hold_and_starting_pose_match_hal() -> None:
    manifest = RSkillManifest.from_yaml(str(_PKG / "rskill.yaml"))
    extras = manifest.policy_extras
    np.testing.assert_allclose(extras["hold_targets"], [*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_READY])
    np.testing.assert_allclose(extras["poses"]["ready"], GO2_Z1_ARM_READY)
    assert manifest.starting_pose is not None
    np.testing.assert_allclose(
        manifest.starting_pose, [*GO2_HOME_JOINT_TARGETS, *GO2_Z1_ARM_HOME]
    )
