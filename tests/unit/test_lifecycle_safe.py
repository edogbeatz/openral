"""is_redundant_lifecycle_error matches the cricket Jazzy RCLError text."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "openral_reasoner_ros"
    / "openral_reasoner_ros"
    / "lifecycle_safe.py"
)
_spec = importlib.util.spec_from_file_location("lifecycle_safe_under_test", _PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
is_redundant_lifecycle_error = _mod.is_redundant_lifecycle_error


def test_registered_phrase() -> None:
    assert is_redundant_lifecycle_error(
        RuntimeError(
            "Failed to trigger lifecycle transition (Transition is not registered)"
        )
    )


def test_matching_3_active() -> None:
    assert is_redundant_lifecycle_error(
        RuntimeError("No transition matching 3 for state active")
    )


def test_unrelated_error_is_not_swallowed() -> None:
    assert is_redundant_lifecycle_error(RuntimeError("palette empty")) is False
    assert is_redundant_lifecycle_error(ValueError("boom")) is False


def test_camera_env_override() -> None:
    fn = _mod.completion_camera_topic_from_env
    assert fn({}) is None
    assert fn({"OPENRAL_COMPLETION_CAMERA_TOPIC": ""}) is None
    assert (
        fn({"OPENRAL_COMPLETION_CAMERA_TOPIC": "/openral/cameras/front/image"})
        == "/openral/cameras/front/image"
    )


def test_install_guard_swallows_redundant_and_reraises_other() -> None:
    class _Log:
        def warning(self, _msg: str) -> None:
            return None

    class _Node:
        def __init__(self) -> None:
            self._LifecycleNodeMixin__change_state = self._raw
            self._calls: list[int] = []

        def _raw(self, transition_id: int) -> str:
            self._calls.append(transition_id)
            if transition_id == 3:
                raise RuntimeError("No transition matching 3 for state active")
            if transition_id == 99:
                raise RuntimeError("palette empty")
            return "ok"

        def get_logger(self) -> _Log:
            return _Log()

    node = _Node()
    _mod.install_redundant_transition_guard(node, success="SUCCESS")
    assert node._LifecycleNodeMixin__change_state(3) == "SUCCESS"
    assert node._LifecycleNodeMixin__change_state(1) == "ok"
    try:
        node._LifecycleNodeMixin__change_state(99)
    except RuntimeError as exc:
        assert "palette empty" in str(exc)
    else:
        raise AssertionError("unrelated error must propagate")
