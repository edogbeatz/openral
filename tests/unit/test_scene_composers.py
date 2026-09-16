"""Pin the collidable-ground composer a gravity-on legged scene depends on.

The `deploy sim` bare twin loads the robot MJCF alone; the HAL camera rig then
stages a checker plane that is deliberately ``contype="0" conaffinity="0"``,
visual only. With gravity off nothing notices. With gravity on there is no
ground at all, and the floating base free-falls forever (field-observed on
`go2_walk`: odom z reached −242175 m in 37 s).

Real menagerie MJCF, real MuJoCo compile — no mocks (CLAUDE.md §1.11).
"""

from __future__ import annotations

import re

import pytest
from openral_core.exceptions import ROSConfigError
from openral_sim.scene_composers import compose_ground_plane_mjcf

_GO2_MJCF = "rd:go2_mj_description"


def _planes(xml: str) -> list[str]:
    return re.findall(r"<geom\b[^>]*type=\"plane\"[^>]*/?>", xml)


def test_rejects_an_unresolvable_mjcf_ref() -> None:
    """A typo'd ref fails loudly at compose time, not as a mystery empty world."""
    with pytest.raises(ROSConfigError, match="did not resolve to a file"):
        compose_ground_plane_mjcf(mjcf_ref="rd:no_such_robot_description")


def test_splices_a_collidable_plane_into_the_bare_twin() -> None:
    """The staged plane participates in contacts — the whole point of the composer."""
    pytest.importorskip("robot_descriptions")

    xml, meshdir = compose_ground_plane_mjcf(mjcf_ref=_GO2_MJCF)

    planes = _planes(xml)
    assert len(planes) == 1, planes
    floor = planes[0]
    assert 'name="openral_ground"' in floor
    # Contact participation is the contract. The camera rig's visual staging
    # floor is distinguished from this one by exactly these two attributes.
    assert 'contype="0"' not in floor
    assert 'conaffinity="0"' not in floor
    # The node writes the composed scene to `meshdir.parent`, so relative mesh
    # references in the upstream model keep resolving.
    assert meshdir.name == "assets"
    assert (meshdir.parent / "go2.xml").is_file()


def test_is_idempotent_against_a_model_that_already_has_ground() -> None:
    """Re-composing must not stack a second plane at z=0 fighting the first."""
    pytest.importorskip("robot_descriptions")

    once, _ = compose_ground_plane_mjcf(mjcf_ref=_GO2_MJCF)
    twice, _ = compose_ground_plane_mjcf(mjcf_ref=_GO2_MJCF)

    assert len(_planes(once)) == 1
    assert len(_planes(twice)) == 1


def test_composed_model_compiles_and_holds_the_robot_up() -> None:
    """Under real gravity the twin settles on the floor instead of falling through."""
    mujoco = pytest.importorskip("mujoco")
    pytest.importorskip("robot_descriptions")

    xml, meshdir = compose_ground_plane_mjcf(mjcf_ref=_GO2_MJCF)
    scene = meshdir.parent / "go2_test_composed_scene.xml"
    scene.write_text(xml)
    try:
        model = mujoco.MjModel.from_xml_path(str(scene))
        data = mujoco.MjData(model)
        assert float(model.opt.gravity[2]) < 0.0

        mujoco.mj_resetDataKeyframe(model, data, 0)
        # Hub stand (hip +/-0.1, thigh 0.9, calf -1.8) — the pose both the HAL
        # and the rsl-rl policy's `starting_pose` spawn at.
        hub_stand = [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8]
        data.qpos[7:19] = hub_stand
        data.ctrl[:] = hub_stand
        mujoco.mj_forward(model, data)
        spawn_z = float(data.qpos[2])

        for _ in range(3000):  # 6 s at the model's 2 ms timestep
            mujoco.mj_step(model, data)

        settled_z = float(data.qpos[2])
        # Without the floor this is a free fall of many metres; the exact
        # resting height depends on how the torque actuators hold the stand,
        # so assert "supported", not a pose.
        assert settled_z > 0.05, f"fell through the floor: {spawn_z} -> {settled_z}"
    finally:
        scene.unlink(missing_ok=True)
