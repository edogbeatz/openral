"""startup_prompt must wait for /openral/execute_rskill before publishing.

#22 cricket: reasoner subscribed and dispatched execute_rskill ~0.5 s
before runtime_node finished ``trigger_configure()`` on
``openral_skill_runner``. The 100 ms reasoner probe then logged
``execute_rskill server /openral/execute_rskill not on graph`` and
emitted KIND_CONTROLLER. The runner configured *after* FailureTrigger.

Gate is the existing ROS graph (send_goal + runner change_state) — same
names the reasoner / ``ros2 action list`` already use. No new API.
Loads ``startup_gates`` from file so this test does not need rclpy.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_NODE = _PKG / "openral_prompt_router" / "prompt_router_node.py"
_GATES = _PKG / "openral_prompt_router" / "startup_gates.py"


def _load_gates():
    spec = importlib.util.spec_from_file_location("openral_startup_gates_under_test", _GATES)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_gates = _load_gates()
EXECUTE_RSKILL_SEND_GOAL_SERVICE = _gates.EXECUTE_RSKILL_SEND_GOAL_SERVICE
RUNNER_CHANGE_STATE_SERVICE = _gates.RUNNER_CHANGE_STATE_SERVICE
actuation_ready = _gates.actuation_ready


def test_actuation_ready_requires_send_goal_and_runner_change_state() -> None:
    assert actuation_ready([]) is False
    assert actuation_ready({EXECUTE_RSKILL_SEND_GOAL_SERVICE}) is False
    assert actuation_ready({RUNNER_CHANGE_STATE_SERVICE}) is False
    assert (
        actuation_ready(
            {
                EXECUTE_RSKILL_SEND_GOAL_SERVICE,
                RUNNER_CHANGE_STATE_SERVICE,
            }
        )
        is True
    )


def test_actuation_ready_ignores_unrelated_services() -> None:
    assert (
        actuation_ready(
            {
                "/openral_reasoner/change_state",
                "/openral/prompt",
                "/openral_skill_runner/get_state",
            }
        )
        is False
    )


def test_publish_startup_prompt_waits_for_execute_rskill() -> None:
    """Structural pin: the one-shot prompt polls actuation_ready before publish."""
    tree = ast.parse(_NODE.read_text(), filename=str(_NODE))
    publish_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_publish_startup_prompt"
    )
    names: set[str] = set()
    for node in ast.walk(publish_fn):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    assert "actuation_ready" in names, (
        "_publish_startup_prompt must wait for actuation_ready "
        "(/openral/execute_rskill advertised + runner on graph) before "
        "publishing startup_prompt — otherwise the reasoner dispatches "
        "into KIND_CONTROLLER while rskill_runner is still configuring."
    )
