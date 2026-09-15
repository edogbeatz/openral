"""Readiness gates for the one-shot ``startup_prompt``.

The reasoner dispatches ``execute_rskill`` on the first tick after
``/openral/prompt`` arrives, with only a 100 ms ``wait_for_server`` probe.
``runtime_node`` advertises ``/openral/execute_rskill`` only after
``RskillRunnerNode.on_configure``. Publishing the prompt before that
configure finishes is a KIND_CONTROLLER race — not a missing package.

Uses the ROS graph names already queried by ``ros2 action list`` /
``lifecycle_autostart`` / the reasoner. No new topic, flag, or service.
"""

from __future__ import annotations

from collections.abc import Iterable

EXECUTE_RSKILL_SEND_GOAL_SERVICE = "/openral/execute_rskill/_action/send_goal"
RUNNER_CHANGE_STATE_SERVICE = "/openral_skill_runner/change_state"
RUNNER_GET_STATE_SERVICE = "/openral_skill_runner/get_state"

__all__ = [
    "EXECUTE_RSKILL_SEND_GOAL_SERVICE",
    "RUNNER_CHANGE_STATE_SERVICE",
    "RUNNER_GET_STATE_SERVICE",
    "actuation_ready",
]


def actuation_ready(service_names: Iterable[str]) -> bool:
    """True when ``/openral/execute_rskill`` is advertised and the runner is on the graph.

    ``RskillRunnerNode`` (ROS name ``openral_skill_runner``) creates
    ``change_state`` / ``get_state`` at construction and the ExecuteRskill
    ActionServer in ``on_configure``. The reasoner treats a missing
    send_goal service as "not on graph" and fires FailureTrigger — so the
    one-shot startup prompt must not publish until both exist.
    """
    names = set(service_names)
    return EXECUTE_RSKILL_SEND_GOAL_SERVICE in names and RUNNER_CHANGE_STATE_SERVICE in names
