"""Hermetic copy of the prompt_router actuation-ready gate (no rclpy)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_GATES = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "openral_prompt_router"
    / "openral_prompt_router"
    / "startup_gates.py"
)


def _load_gates():
    spec = importlib.util.spec_from_file_location("openral_startup_gates_unit", _GATES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actuation_ready_requires_send_goal_and_runner_change_state() -> None:
    gates = _load_gates()
    assert gates.actuation_ready([]) is False
    assert gates.actuation_ready({gates.EXECUTE_RSKILL_SEND_GOAL_SERVICE}) is False
    assert gates.actuation_ready({gates.RUNNER_CHANGE_STATE_SERVICE}) is False
    assert (
        gates.actuation_ready(
            {
                gates.EXECUTE_RSKILL_SEND_GOAL_SERVICE,
                gates.RUNNER_CHANGE_STATE_SERVICE,
            }
        )
        is True
    )
