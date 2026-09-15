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
