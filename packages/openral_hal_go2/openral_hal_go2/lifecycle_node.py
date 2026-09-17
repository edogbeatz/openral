#!/usr/bin/env python3
r"""Unitree Go2 / Go2+Z1 HAL lifecycle node entry point.

Manifest-driven node: builds its HAL via
``openral_hal.lifecycle.make_lifecycle_main_from_manifest``, which reads
the ``robot_yaml`` + ``hal_mode`` ROS parameters and routes through
``openral_hal.build_hal``. ``openral deploy sim`` injects ``hal_mode:=sim``
(→ ``Go2MujocoHAL`` for ``robots/go2``, ``Go2Z1MujocoHAL`` for
``robots/go2_z1``). Both are sim-only today (``hal.real`` is null), so
``hal_mode:=real`` raises ``ROSCapabilityMismatch`` until a real adapter
lands.

Usage::

    ros2 run openral_hal_go2 lifecycle_node.py \
        --ros-args -p robot_yaml:=robots/go2/robot.yaml -p hal_mode:=sim
"""

from __future__ import annotations

from openral_hal.lifecycle import make_lifecycle_main_from_manifest

main = make_lifecycle_main_from_manifest(node_name="openral_hal_go2")


if __name__ == "__main__":
    main()
