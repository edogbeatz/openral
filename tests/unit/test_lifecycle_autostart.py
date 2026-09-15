"""Unit tests for ``tools/lifecycle_autostart.py:_drive_transition``.

The lifecycle ``change_state``/``get_state`` services are a ROS
process/network boundary, so faking the service clients is allowed under
CLAUDE.md §1.11. The whole module skips when ROS 2 isn't installed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("rclpy", reason="lifecycle_autostart needs a ROS 2 (rclpy) install")
pytest.importorskip("lifecycle_msgs", reason="lifecycle_autostart needs lifecycle_msgs")

_TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "lifecycle_autostart.py"


def _load_tool() -> Any:
    spec = importlib.util.spec_from_file_location("lifecycle_autostart_under_test", _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeCurrentState:
    def __init__(self, label: str) -> None:
        self.label = label


class _FakeGetStateResult:
    def __init__(self, label: str) -> None:
        self.current_state = _FakeCurrentState(label)


class _FakeChangeStateResult:
    def __init__(self, success: bool) -> None:
        self.success = success


class _FakeFuture:
    def __init__(self, result: Any) -> None:
        self._result = result

    def result(self) -> Any:
        return self._result


class _FakeChangeStateClient:
    def __init__(self, resp: Any) -> None:
        self._resp = resp

    def call_async(self, _req: Any) -> _FakeFuture:
        return _FakeFuture(self._resp)


class _FakeGetStateClient:
    def __init__(self, labels: list[str]) -> None:
        self._labels = labels

    def call_async(self, _req: Any) -> _FakeFuture:
        label = self._labels.pop(0) if len(self._labels) > 1 else self._labels[0]
        return _FakeFuture(_FakeGetStateResult(label))


class _FakeRclpy:
    def __init__(self) -> None:
        self.spin_timeouts: list[float | None] = []

    def spin_until_future_complete(
        self, _node: Any, _future: Any, timeout_sec: float | None = None
    ) -> None:
        self.spin_timeouts.append(timeout_sec)

    def spin_once(self, _node: Any, timeout_sec: float | None = None) -> None:
        return None


class _FakeTime:
    def __init__(self) -> None:
        self._t = 0.0

    def monotonic(self) -> float:
        now = self._t
        self._t += 1.0
        return now


def _patch_runtime(mod: Any) -> _FakeRclpy:
    fake_rclpy = _FakeRclpy()
    mod.rclpy = fake_rclpy
    mod.time = _FakeTime()
    return fake_rclpy


def test_drive_transition_uses_caller_timeout() -> None:
    mod = _load_tool()
    fake_rclpy = _patch_runtime(mod)
    mod._drive_transition(
        node=object(),
        target_node="/openral_hal_panda_mobile",
        change_state_client=_FakeChangeStateClient(_FakeChangeStateResult(success=True)),
        get_state_client=_FakeGetStateClient(["inactive"]),
        transition_id=1,
        transition_label="configure",
        transition_timeout_s=123.0,
    )
    assert fake_rclpy.spin_timeouts[0] == 123.0


def test_drive_transition_succeeds_when_state_advances_despite_no_response() -> None:
    mod = _load_tool()
    _patch_runtime(mod)
    mod._drive_transition(
        node=object(),
        target_node="/openral_hal_panda_mobile",
        change_state_client=_FakeChangeStateClient(None),
        get_state_client=_FakeGetStateClient(["inactive"]),
        transition_id=1,
        transition_label="configure",
        transition_timeout_s=300.0,
    )


def test_drive_transition_polls_grace_window_before_success() -> None:
    mod = _load_tool()
    _patch_runtime(mod)
    mod._drive_transition(
        node=object(),
        target_node="/openral_slam_toolbox",
        change_state_client=_FakeChangeStateClient(_FakeChangeStateResult(success=False)),
        get_state_client=_FakeGetStateClient(["unconfigured", "inactive"]),
        transition_id=1,
        transition_label="configure",
        transition_timeout_s=300.0,
    )


def test_skip_transition_when_already_active() -> None:
    """Second ACTIVATE while active must not be sent (Jazzy RCLError crash)."""
    mod = _load_tool()
    activate = mod.Transition.TRANSITION_ACTIVATE
    configure = mod.Transition.TRANSITION_CONFIGURE
    assert mod._skip_transition("active", activate) is True
    assert mod._skip_transition("active", configure) is True
    assert mod._skip_transition("inactive", configure) is True
    assert mod._skip_transition("inactive", activate) is False
    assert mod._skip_transition("unconfigured", configure) is False


def test_drive_transition_raises_on_genuine_failure() -> None:
    mod = _load_tool()
    _patch_runtime(mod)
    with pytest.raises(RuntimeError, match=r"did not advance the FSM within 300\.0s"):
        mod._drive_transition(
            node=object(),
            target_node="/openral_hal_panda_mobile",
            change_state_client=_FakeChangeStateClient(_FakeChangeStateResult(success=False)),
            get_state_client=_FakeGetStateClient(["unconfigured"]),
            transition_id=1,
            transition_label="configure",
            transition_timeout_s=300.0,
        )
