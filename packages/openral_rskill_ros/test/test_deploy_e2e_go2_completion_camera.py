"""Go2 deploy must point the reasoner at ``/openral/cameras/front/image``.

Cricket #17: reasoner defaulted to ``/openral/cameras/top/image`` while
``Go2MujocoHAL`` advertised front only. ``deploy_e2e.launch`` now sets
``completion_camera_topic`` from the manifest RGB names.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

pytest.importorskip("launch")
pytest.importorskip("launch_ros")
pytest.importorskip("openral_core")
pytest.importorskip("openral_safety")
pytest.importorskip("mujoco")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ROS_DISTRO"),
    reason="ROS_DISTRO not set — these tests require a sourced ROS 2 installation.",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LAUNCH_FILE = _REPO_ROOT / "packages" / "openral_rskill_ros" / "launch" / "deploy_e2e.launch.py"


def _import_launch_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "deploy_e2e_launch_go2_completion_camera", _LAUNCH_FILE
    )
    assert spec is not None and spec.loader is not None, f"failed to spec {_LAUNCH_FILE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compose_go2() -> list[object]:
    from launch import LaunchContext
    from launch.actions import DeclareLaunchArgument

    module = _import_launch_module()
    ctx = LaunchContext()
    cfg = ctx.launch_configurations
    cfg["robot_yaml"] = str(_REPO_ROOT / "robots" / "go2" / "robot.yaml")
    cfg["hal_package"] = "openral_hal_go2"
    cfg["hal_executable"] = "lifecycle_node.py"
    cfg["hal_node_name"] = "openral_hal_go2"
    cfg["hal_params_file"] = "/tmp/openral-test-hal-params.yaml"
    for entity in module.generate_launch_description().entities:  # type: ignore[attr-defined]
        if isinstance(entity, DeclareLaunchArgument):
            entity.execute(ctx)
    cfg["hal_mode"] = "sim"
    cfg["enable_slam"] = "false"
    cfg["enable_nav2"] = "false"
    cfg["enable_octomap"] = "false"
    cfg["enable_object_detector"] = "false"
    cfg["enable_dashboard"] = "false"
    cfg["enable_reasoner"] = "true"
    return list(module.compose_runtime_graph(ctx))  # type: ignore[attr-defined]


def _reasoner_param(entities: list[object], name: str) -> object:
    from launch_ros.actions import LifecycleNode

    for entity in entities:
        if not isinstance(entity, LifecycleNode):
            continue
        if getattr(entity, "_Node__node_name", None) != "openral_reasoner":
            continue
        (params_dict,) = entity._Node__parameters
        for key_subs, value in params_dict.items():
            key = "".join(s.text for s in key_subs if hasattr(s, "text"))
            if key == name:
                return value
        pytest.fail(f"openral_reasoner has no {name!r} parameter")
    pytest.fail("no openral_reasoner LifecycleNode found in the composed graph")


def test_go2_reasoner_subscribes_front_not_top() -> None:
    """Manifest RGB is ``front``; do not leave the tabletop ``top`` default."""
    topic = _reasoner_param(_compose_go2(), "completion_camera_topic")
    assert topic == "/openral/cameras/front/image", (
        f"reasoner completion_camera_topic={topic!r} — Go2 HAL publishes "
        "/openral/cameras/front/image only; top is a dead subscription"
    )
