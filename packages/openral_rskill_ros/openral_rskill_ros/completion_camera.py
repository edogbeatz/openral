"""Map HAL RGB camera names to the reasoner completion-camera topic.

The reasoner ROS param ``completion_camera_topic`` defaults to
``/openral/cameras/top/image`` (tabletop / LIBERO). Quadruped HALs such as
Go2 advertise ``front`` only (``robots/go2/robot.yaml``), so a deploy that
leaves the default subscribed to a topic with zero publishers.

No ROS imports — unit-testable without a sourced overlay.
"""

from __future__ import annotations

_DEFAULT_TOPIC = "/openral/cameras/top/image"


def completion_camera_topic(rgb_names: list[str]) -> str:
    """Return ``/openral/cameras/<name>/image`` for the HAL's completion view.

    Prefers a camera named ``front`` when present (Go2 / Unitree face cam).
    Otherwise the first RGB name. Empty list keeps the tabletop default.

    Args:
        rgb_names: Sensor names with ``modality == \"rgb\"`` from the robot
            manifest (and any scene-mounted RGB sensors).

    Returns:
        Fully-qualified Image topic the reasoner should subscribe.

    Example:
        >>> completion_camera_topic(["front"])
        '/openral/cameras/front/image'
        >>> completion_camera_topic(["top", "wrist_left"])
        '/openral/cameras/top/image'
        >>> completion_camera_topic([])
        '/openral/cameras/top/image'
    """
    if not rgb_names:
        return _DEFAULT_TOPIC
    name = "front" if "front" in rgb_names else rgb_names[0]
    return f"/openral/cameras/{name}/image"
