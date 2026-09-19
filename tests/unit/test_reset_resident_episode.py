"""Unit tests for ``reset_resident_episode`` — second-execute Go2 stand-still.

No ROS. The helper lives in ``openral_rskill_ros._resident_episode`` so a
reused GPU-resident skill can drop last_action / hold-pad / horizon without
reloading weights or importing rclpy.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from openral_rskill_ros._resident_episode import reset_resident_episode


def test_reset_resident_episode_calls_activate_impl() -> None:
    """Preferred path: the policy shim's ``_activate_impl`` owns episode reset."""

    class _Skill:
        def __init__(self) -> None:
            self._horizon_started: float | None = 1.0
            self._horizon_ticks_ran = 9
            self._hold_pad_pose: list[float] | None = [0.1, 0.9]
            self._step_count = 4
            self.calls = 0

        def _activate_impl(self) -> None:
            self.calls += 1
            self._horizon_started = None
            self._horizon_ticks_ran = 0
            self._hold_pad_pose = None

    skill = _Skill()
    reset_resident_episode(skill)
    assert skill.calls == 1
    assert skill._horizon_started is None
    assert skill._horizon_ticks_ran == 0
    assert skill._hold_pad_pose is None
    assert skill._step_count == 0


def test_reset_resident_episode_resets_adapter_without_activate_impl() -> None:
    """Hub / test-double handles have no ``_activate_impl`` — reset the adapter."""

    class _Adapter:
        def __init__(self) -> None:
            self._last_action = np.ones(12, dtype=np.float32)

        def reset(self) -> None:
            self._last_action = np.zeros(12, dtype=np.float32)

    skill = SimpleNamespace(
        _adapter=_Adapter(),
        _horizon_started=3.0,
        _horizon_ticks_ran=12,
        _hold_pad_pose=[1.0],
        _step_count=8,
    )
    reset_resident_episode(skill)
    np.testing.assert_allclose(skill._adapter._last_action, 0.0)
    assert skill._horizon_started is None
    assert skill._horizon_ticks_ran == 0
    assert skill._hold_pad_pose is None
    assert skill._step_count == 0
