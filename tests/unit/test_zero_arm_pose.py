"""Scripted ``model_family: zero`` named-pose override (Go2+Z1 arm command)."""

from __future__ import annotations

import numpy as np
import pytest
from openral_core.exceptions import ROSConfigError
from openral_sim.policies.mock import _ZeroPolicy, apply_zero_pose_override


def _policy() -> _ZeroPolicy:
    from openral_core import VLASpec

    hold = np.array(
        [
            -0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8,
            0.0, 1.2, -1.0, -0.4, 0.0, 0.0, 0.0,
        ],
        dtype=np.float32,
    )
    return _ZeroPolicy(
        spec=VLASpec(id="zero", weights_uri="local://rskills/rskill-zero-go2_z1-arm_ready-fp32"),
        device="cpu",
        action_dim=19,
        hold_targets=hold,
        poses={
            "ready": [0.0, 1.2, -1.0, -0.4, 0.0, 0.0, 0.0],
            "home": [0.0, 0.785, -0.261, -0.523, 0.0, 0.0, 0.0],
            "fold": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    )


def test_named_home_overlays_trailing_arm() -> None:
    policy = _policy()
    out = policy.set_named_pose("home")
    assert out is not None
    assert policy._default_hold is not None
    np.testing.assert_allclose(out[:12], policy._default_hold[:12])
    np.testing.assert_allclose(out[12:], [0.0, 0.785, -0.261, -0.523, 0.0, 0.0, 0.0])
    step = policy.step({}, "")
    np.testing.assert_allclose(step[12:], out[12:])


def test_explicit_arm_wins_over_pose_name() -> None:
    policy = _policy()
    apply_zero_pose_override(policy, {"pose": "fold", "arm": [0.1, 0.2, -0.3, 0.0, 0.0, 0.0, 0.0]})
    assert policy.hold_targets is not None
    np.testing.assert_allclose(
        policy.hold_targets[12:], [0.1, 0.2, -0.3, 0.0, 0.0, 0.0, 0.0], atol=1e-6
    )


def test_empty_goal_params_restores_default_ready() -> None:
    policy = _policy()
    policy.set_named_pose("fold")
    apply_zero_pose_override(policy, "")
    assert policy.hold_targets is not None
    np.testing.assert_allclose(policy.hold_targets[13], 1.2, atol=1e-6)


def test_unknown_pose_raises() -> None:
    policy = _policy()
    with pytest.raises(ROSConfigError, match="unknown pose"):
        policy.set_named_pose("wave")


def test_override_noops_on_adapter_without_hooks() -> None:
    assert apply_zero_pose_override(object(), {"pose": "ready"}) is None
