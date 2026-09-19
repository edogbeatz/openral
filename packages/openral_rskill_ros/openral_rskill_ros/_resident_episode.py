"""Per-goal episode reset for a reused GPU-resident skill.

``rskill_runner_node._acquire_skill`` keeps weights loaded and skips
``activate()``. Without this reset the previous goal's ``last_action``,
frozen hold-pad, scripted horizon, and action queue leak into the next
``execute_rskill`` — a second Go2 walk stands still, and a ``horizon_s``
skill completes on tick 1.
"""

from __future__ import annotations

__all__ = ["reset_resident_episode"]


def _clear(skill: object, name: str, value: object) -> None:
    if hasattr(skill, name):
        object.__setattr__(skill, name, value)


def reset_resident_episode(skill: object) -> None:
    """Clear per-goal episode state without unloading weights.

    Example:
        >>> class _Skill:
        ...     def __init__(self) -> None:
        ...         self._horizon_started = 1.0
        ...         self._horizon_ticks_ran = 9
        ...         self._hold_pad_pose = [0.0]
        ...         self._step_count = 4
        ...     def _activate_impl(self) -> None:
        ...         self._horizon_started = None
        ...         self._horizon_ticks_ran = 0
        ...         self._hold_pad_pose = None
        ...         self._step_count = 0
        >>> s = _Skill()
        >>> reset_resident_episode(s)
        >>> s._horizon_started is None and s._horizon_ticks_ran == 0
        True
    """
    activate_impl = getattr(skill, "_activate_impl", None)
    if callable(activate_impl):
        activate_impl()
        _clear(skill, "_step_count", 0)
        return
    adapter = getattr(skill, "_adapter", None)
    reset = getattr(adapter, "reset", None) if adapter is not None else None
    if reset is None:
        reset = getattr(skill, "reset", None)
    if callable(reset):
        reset()
    _clear(skill, "_horizon_started", None)
    _clear(skill, "_horizon_ticks_ran", 0)
    _clear(skill, "_hold_pad_pose", None)
    _clear(skill, "_step_count", 0)
