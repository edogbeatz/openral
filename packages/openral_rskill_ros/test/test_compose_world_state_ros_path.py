"""compose_runtime must find openral_world_state_ros from the source tree.

A go2 HAL-only overlay can launch reasoner + HAL without ament-installing
``openral_world_state``. ``runtime_node`` then exits 3
(``No module named 'openral_world_state_ros'``) and the reasoner logs
``execute_rskill server /openral/execute_rskill not on graph``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORLD_STATE = _REPO_ROOT / "packages" / "world_state"


def test_ensure_world_state_ros_importable_from_source_tree() -> None:
    from openral_rskill_ros.compose import _ensure_world_state_ros_importable

    saved = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != _WORLD_STATE.resolve()]
        sys.modules.pop("openral_world_state_ros", None)
        sys.modules.pop("openral_world_state_ros.lifecycle_node", None)
        _ensure_world_state_ros_importable()
        import openral_world_state_ros  # noqa: F401
    finally:
        sys.path[:] = saved
