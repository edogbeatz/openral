#!/usr/bin/env python3
"""Installed ``reasoner_node.py`` entry — Jazzy activate guard + camera env.

``ament`` installs this file to ``lib/openral_reasoner_ros/reasoner_node.py``
(the launch executable). The library module
``openral_reasoner_ros.reasoner_node`` is unchanged.

Jazzy: a second ``TRANSITION_ACTIVATE`` (id 3) while already ``active``
raises ``RCLError`` and ``main()`` destroyed the node (cricket go2_bench:
``on_activate: ticking`` then exit 1, so ``startup_prompt`` had no
subscriber). This entry wraps ``__change_state`` and re-spins once if
the same error still leaves ``rclpy.spin``.

Camera: optional ``OPENRAL_COMPLETION_CAMERA_TOPIC`` (Go2 HAL is
``/openral/cameras/front/image``; the library default is tabletop ``top``).
"""

from __future__ import annotations

import sys

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.parameter import Parameter

from openral_observability import configure_observability
from openral_reasoner_ros.lifecycle_safe import (
    completion_camera_topic_from_env,
    install_redundant_transition_guard,
    is_redundant_lifecycle_error,
)
from openral_reasoner_ros.reasoner_node import ReasonerNode


def main(args: list[str] | None = None) -> int:
    configure_observability(service_name="openral.reasoner")
    rclpy.init(args=args)
    try:
        node = ReasonerNode()
        install_redundant_transition_guard(
            node, success=TransitionCallbackReturn.SUCCESS
        )
        override = completion_camera_topic_from_env()
        if override:
            node.set_parameters(
                [Parameter("completion_camera_topic", Parameter.Type.STRING, override)]
            )
            node.get_logger().info(
                f"completion_camera_topic from {override!r} env override"
            )
        try:
            rclpy.spin(node)
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        except Exception as exc:
            if not is_redundant_lifecycle_error(exc):
                raise
            node.get_logger().warning(
                f"spin: ignoring redundant lifecycle transition: {exc}"
            )
            try:
                rclpy.spin(node)
            except (KeyboardInterrupt, ExternalShutdownException):
                pass
        finally:
            node.destroy_node()
    finally:
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
