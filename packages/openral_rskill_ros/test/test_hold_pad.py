"""Unit tests for ``hold_pad_joint_targets`` (short JOINT_POSITION → full DoF)."""

from __future__ import annotations

import pytest
from openral_core.exceptions import ROSConfigError
from openral_rskill_ros._hold_pad import hold_pad_joint_targets


def test_hold_pad_copies_leading_and_holds_trailing() -> None:
    hold = [9.0, 9.0, 0.7, 0.8, 0.9]
    assert hold_pad_joint_targets([0.1, 0.2], n_dof=5, hold=hold) == [
        0.1,
        0.2,
        0.7,
        0.8,
        0.9,
    ]


def test_hold_pad_passthrough_when_widths_match() -> None:
    row = [1.0, 2.0, 3.0, 4.0]
    assert hold_pad_joint_targets(row, n_dof=4, hold=[0.0] * 4) == row


def test_hold_pad_go2_to_go2_z1_shape() -> None:
    """12-D policy on 19-D robot: arm joints come from hold, not zeros."""
    legs = [-0.1, 0.9, -1.8] * 4
    arm_home = [0.0, 0.785, -0.261, -0.523, 0.0, 0.0, 0.0]
    hold = [*([0.0] * 12), *arm_home]
    out = hold_pad_joint_targets(legs, n_dof=19, hold=hold)
    assert len(out) == 19
    assert out[:12] == pytest.approx(legs)
    assert out[12:] == pytest.approx(arm_home)
    assert out[12] == 0.0  # not a zero-pad accident: joint1 home is 0
    assert out[13] == pytest.approx(0.785)


def test_hold_pad_rejects_row_longer_than_n_dof() -> None:
    with pytest.raises(ROSConfigError, match="exceeds n_dof"):
        hold_pad_joint_targets([1.0, 2.0, 3.0], n_dof=2, hold=[0.0, 0.0])


def test_hold_pad_rejects_hold_width_mismatch() -> None:
    with pytest.raises(ROSConfigError, match="hold length"):
        hold_pad_joint_targets([1.0], n_dof=2, hold=[0.0])


def test_hold_pad_clamps_held_joints_to_limits() -> None:
    """Normalised gripper proprio must not enter a radian envelope as-is."""
    out = hold_pad_joint_targets(
        [1.0, 2.0],
        n_dof=3,
        hold=[0.0, 0.0, 0.9],
        limits=[(-1.0, 1.0), (-1.0, 1.0), (-1.5, 0.0)],
    )
    assert out[:2] == [1.0, 2.0]
    assert out[2] == pytest.approx(-0.001)
    with pytest.raises(ROSConfigError, match="positive"):
        hold_pad_joint_targets([], n_dof=0, hold=[])
