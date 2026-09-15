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


def is_redundant_lifecycle_error(exc: BaseException) -> bool:
    """True when ``exc`` is Jazzy's invalid-transition crash.

    Args:
        exc: Exception raised from ``LifecycleNodeMixin.__change_state``
            or bubbling out of ``rclpy.spin``.

    Returns:
        Whether the node can stay up (already in the requested primary
        state) instead of exiting.

    Example:
        >>> class _E(Exception):
        ...     pass
        >>> is_redundant_lifecycle_error(
        ...     _E("Failed to trigger lifecycle transition "
        ...        "(Transition is not registered)")
        ... )
        True
        >>> is_redundant_lifecycle_error(
        ...     _E("No transition matching 3 for state active")
        ... )
        True
        >>> is_redundant_lifecycle_error(_E("palette empty"))
        False
    """
    text = str(exc)
    return (
        "Transition is not registered" in text
        or "No transition matching" in text
        or "Failed to trigger lifecycle transition" in text
    )
