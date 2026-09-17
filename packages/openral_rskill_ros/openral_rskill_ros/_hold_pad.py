"""Expand a short JOINT_POSITION row to full robot DoF by holding the rest.

A 12-DoF Go2 locomotion policy on ``go2_z1`` (19 joints: legs + Z1 arm)
must publish ``chunk.n_dof == envelope.n_dof`` or the C++ safety kernel
rejects the chunk. Zero-padding the trailing arm joints is wrong: the Z1's
actuators are position servos, and a target of ``0.0`` folds the arm off its
spawn home. Fill unowned joints from a **hold** vector (latest proprio at
episode start, or the HAL's home) instead — do not re-sample proprio every
tick or base motion walks an idle arm off home.

Policy values occupy the **leading** indices — the go2_z1 joint order puts
the 12 Go2 legs first, byte-identical to ``robots/go2``, so a leg-only
policy row lands on the joints it was trained for.

Held joints are clamped to the robot's ``position_limits`` when provided.
Proprio for a normalised gripper can sit near ``1.0`` while the envelope
expects radians with ``max=0`` (Z1 jaw) — publishing the raw proprio value
trips ``kind_workspace`` on joint 18.
"""

from __future__ import annotations

from collections.abc import Sequence

from openral_core.exceptions import ROSConfigError

__all__ = ["hold_pad_joint_targets"]

# Stay inside the kernel's open interval (value > max / value < min trips).
_CLAMP_EPS = 1e-3


def hold_pad_joint_targets(
    row: Sequence[float],
    *,
    n_dof: int,
    hold: Sequence[float],
    limits: Sequence[tuple[float, float] | None] | None = None,
) -> list[float]:
    """Expand ``row`` to ``n_dof`` by copying leading values and holding the rest.

    Args:
        row: Policy (or starting-pose) joint targets. Length must be ``<= n_dof``.
            When equal to ``n_dof``, returned unchanged (no hold consult).
        n_dof: Robot actuated joint count (safety envelope width).
        hold: Full-width hold vector (usually latest proprio). Length must
            equal ``n_dof``. Trailing joints ``row[len(row):]`` are taken from here.
        limits: Optional per-joint ``(lo, hi)`` from ``RobotDescription.joints``
            ``position_limits``. When set, **held** (trailing) values are clamped
            inside ``(lo+eps, hi-eps)`` so a normalised gripper proprio cannot
            violate a radian envelope.

    Returns:
        A length-``n_dof`` list of floats.

    Raises:
        ROSConfigError: ``n_dof`` is non-positive, ``hold`` width mismatches,
            ``row`` is longer than ``n_dof``, or ``limits`` width mismatches.

    Example:
        >>> hold_pad_joint_targets([0.1, 0.2], n_dof=4, hold=[9.0, 9.0, 0.7, 0.8])
        [0.1, 0.2, 0.7, 0.8]
        >>> hold_pad_joint_targets(
        ...     [1.0, 2.0],
        ...     n_dof=3,
        ...     hold=[0.0, 0.0, 0.9],
        ...     limits=[(-1.0, 1.0), (-1.0, 1.0), (-1.5, 0.0)],
        ... )
        [1.0, 2.0, -0.001]
    """
    if n_dof <= 0:
        raise ROSConfigError(f"hold_pad_joint_targets: n_dof must be positive, got {n_dof}")
    if len(hold) != n_dof:
        raise ROSConfigError(
            f"hold_pad_joint_targets: hold length {len(hold)} != n_dof {n_dof}"
        )
    if len(row) > n_dof:
        raise ROSConfigError(
            f"hold_pad_joint_targets: row length {len(row)} exceeds n_dof {n_dof}"
        )
    if limits is not None and len(limits) != n_dof:
        raise ROSConfigError(
            f"hold_pad_joint_targets: limits length {len(limits)} != n_dof {n_dof}"
        )
    if len(row) == n_dof:
        return [float(v) for v in row]
    out = [float(v) for v in hold]
    for i, value in enumerate(row):
        out[i] = float(value)
    if limits is not None:
        for i in range(len(row), n_dof):
            lim = limits[i]
            if lim is None:
                continue
            lo, hi = float(lim[0]), float(lim[1])
            lo_safe = lo + _CLAMP_EPS
            hi_safe = hi - _CLAMP_EPS
            if hi_safe < lo_safe:
                mid = 0.5 * (lo + hi)
                out[i] = mid
            elif out[i] < lo_safe:
                out[i] = lo_safe
            elif out[i] > hi_safe:
                out[i] = hi_safe
    return out
