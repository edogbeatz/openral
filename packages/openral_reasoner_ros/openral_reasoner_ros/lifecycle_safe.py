"""Detect Jazzy rclpy's fatal redundant-lifecycle ``RCLError``.

Jazzy ``rclpy.lifecycle`` (``__change_state``) calls
``trigger_transition_by_id`` without checking whether the transition is
registered. A second ``TRANSITION_ACTIVATE`` (id 3) while already
``active`` raises::

    RCLError: Failed to trigger lifecycle transition
    (Transition is not registered)
    No transition matching 3 for state active

That exception leaves ``rclpy.spin`` and ``reasoner_node.main`` destroys
the node (exit 1). Rolling later catches this (ros2/rclpy#1209 / #1319);
Jazzy does not. Helpers here are import-safe without rclpy.
"""

from __future__ import annotations

import os
from typing import Any

COMPLETION_CAMERA_TOPIC_ENV = "OPENRAL_COMPLETION_CAMERA_TOPIC"


def is_redundant_lifecycle_error(exc: BaseException) -> bool:
    """True when ``exc`` is Jazzy's invalid-transition crash.

    Args:
        exc: Exception raised from ``LifecycleNodeMixin.__change_state``
            or bubbling out of ``rclpy.spin``.

    Returns:
        Whether the node can stay up (already in the requested primary
        state) instead of exiting.
    """
    text = str(exc)
    return (
        "Transition is not registered" in text
        or "No transition matching" in text
        or "Failed to trigger lifecycle transition" in text
    )


def completion_camera_topic_from_env(env: dict[str, str] | None = None) -> str | None:
    """Optional topic override so Go2 can use ``front`` without launch edits.

    ``deploy_e2e`` defaults the reasoner to ``/openral/cameras/top/image``.
    Acquire / cricket set ``OPENRAL_COMPLETION_CAMERA_TOPIC`` to the HAL
    RGB topic (Go2: ``/openral/cameras/front/image``). Empty / unset
    keeps the launch default.
    """
    src = os.environ if env is None else env
    raw = (src.get(COMPLETION_CAMERA_TOPIC_ENV) or "").strip()
    return raw or None


def install_redundant_transition_guard(node: Any, *, success: Any) -> None:
    """Wrap name-mangled ``__change_state`` so a redundant ACTIVATE is a no-op."""
    original = node._LifecycleNodeMixin__change_state  # type: ignore[attr-defined]  # reason: rclpy name-mangled service path

    def _guard(transition_id: int) -> Any:
        try:
            return original(transition_id)
        except Exception as exc:  # reason: Jazzy raises RCLError on invalid transition
            if is_redundant_lifecycle_error(exc):
                node.get_logger().warning(
                    f"ignoring redundant lifecycle transition id={transition_id}: {exc}"
                )
                return success
            raise

    node._LifecycleNodeMixin__change_state = _guard  # type: ignore[attr-defined]  # reason: wrap name-mangled mixin method
