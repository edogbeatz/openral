"""Opt-in finite horizon for scripted (non-learned) VLA shims.

OpenRAL VLAs never self-terminate. ``latency_budget.max_execution_s`` is an
**abort** (``deadline_exceeded``), not ``ExecuteRskill`` success. A scripted
hold+trot (``model_family: zero``) may declare ``policy_extras.horizon_s``
and/or ``horizon_ticks`` so ``_PolicyAdapterSkill._step_impl`` can raise
``ROSRskillGoalSatisfied`` after a finite chunk run — then the reasoner logs
``execute_rskill succeeded``.

Learned VLAs leave both unset and keep the open-loop deadline path.
"""

from __future__ import annotations


def scripted_horizon_done(
    *,
    ticks: int,
    elapsed_s: float,
    horizon_ticks: int | None,
    horizon_s: float | None,
) -> bool:
    """True when an opt-in scripted horizon has finished (and ≥1 chunk ran).

    Always emit at least one chunk (``ticks > 1`` before done) so a
    zero/empty horizon cannot succeed without actuating.
    """
    if ticks <= 1:
        return False
    if horizon_ticks is not None and ticks > int(horizon_ticks):
        return True
    return horizon_s is not None and elapsed_s >= float(horizon_s)


def optional_positive_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0.0 else None


def optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
