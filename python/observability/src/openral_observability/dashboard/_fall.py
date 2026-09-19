"""Go2 / Go2+Z1 base-tip gate for ``/simple`` chat.

Same 1.0 rad tilt as ``tools/go2_z1_mass_balance.py`` ``TIP_TILT_RAD``.
Input here is MuJoCo free-joint ``qpos`` (wxyz at indices 3:7), not
Isaac ``quat_xyzw``. Dashboard must not import the sim policy helper.
"""

from __future__ import annotations

import math
from typing import Final

__all__ = [
    "TIP_TILT_RAD",
    "fallen_from_snapshot",
    "qpos_is_fallen",
    "tilt_off_vertical_wxyz",
]

#: Angle off world +z that counts as tipped. Matches the mass-balance tool.
TIP_TILT_RAD: Final[float] = 1.0
_ZERO_NORM: Final[float] = 1e-12


def tilt_off_vertical_wxyz(qw: float, qx: float, qy: float, qz: float) -> float:
    """Angle between the body's +z and world +z, radians.

    Example:
        >>> round(tilt_off_vertical_wxyz(1.0, 0.0, 0.0, 0.0), 6)
        0.0
    """
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm < _ZERO_NORM:
        return 0.0
    qx_n = qx / norm
    qy_n = qy / norm
    uz = 1.0 - 2.0 * (qx_n * qx_n + qy_n * qy_n)
    return math.acos(max(-1.0, min(1.0, uz)))


def qpos_is_fallen(qpos: object, *, tip_tilt_rad: float = TIP_TILT_RAD) -> bool:
    """True when a MuJoCo free-joint ``qpos`` is tipped past ``tip_tilt_rad``.

    Example:
        >>> qpos_is_fallen([0.0, 0.0, 0.33, 1.0, 0.0, 0.0, 0.0])
        False
        >>> half = 0.5**0.5
        >>> qpos_is_fallen([0.0, 0.0, 0.08, half, 0.0, half, 0.0])
        True
    """
    if not isinstance(qpos, (list, tuple)) or len(qpos) < 7:
        return False
    try:
        qw = float(qpos[3])
        qx = float(qpos[4])
        qy = float(qpos[5])
        qz = float(qpos[6])
    except (TypeError, ValueError):
        return False
    return tilt_off_vertical_wxyz(qw, qx, qy, qz) > tip_tilt_rad


def fallen_from_snapshot(payload: object) -> bool:
    """Read ``fallen`` from a dashboard ``/api/state`` body, else compute it.

    Prefers the bool the store already latched. An older cricket snapshot
    without that key still works from ``topics.robot_state.qpos``.

    Example:
        >>> fallen_from_snapshot({"fallen": True})
        True
        >>> fallen_from_snapshot({})
        False
    """
    if not isinstance(payload, dict):
        return False
    raw = payload.get("fallen")
    if isinstance(raw, bool):
        return raw
    topics = payload.get("topics")
    robot_state = topics.get("robot_state") if isinstance(topics, dict) else None
    qpos = robot_state.get("qpos") if isinstance(robot_state, dict) else None
    return qpos_is_fallen(qpos)
