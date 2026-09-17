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
from openral_sim.scene_composers import compose_ground_plane_mjcf, compose_mounted_arm_mjcf

_GO2_MJCF = "rd:go2_mj_description"
_Z1_MJCF = "rd:z1_mj_description"


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


def test_mounted_arm_rejects_a_missing_mount_body() -> None:
    """A typo'd mount body fails at compose time, not as an arm floating in the void."""
    pytest.importorskip("robot_descriptions")

    with pytest.raises(ROSConfigError, match="no body named"):
        compose_mounted_arm_mjcf(
            base_mjcf_ref=_GO2_MJCF,
            arm_mjcf_ref=_Z1_MJCF,
            arm_mjcf_file="z1_gripper.xml",
            mount_body="torso",  # the Go2 calls it `base`
            mount_pos=(0.0, 0.0, 0.0),
        )


def test_mounted_arm_appends_arm_joints_after_the_carrier_s() -> None:
    """Joint ORDER is the contract: a 12-DoF locomotion policy must keep its indices.

    The arm is appended as the last child of the mount body, so its joints land
    after the carrier's in `qpos`. If they interleaved, every existing Go2
    policy and the safety envelope's per-index limits would silently refer to
    different joints.
    """
    mujoco = pytest.importorskip("mujoco")
    pytest.importorskip("robot_descriptions")

    xml, meshdir = compose_mounted_arm_mjcf(
        base_mjcf_ref=_GO2_MJCF,
        arm_mjcf_ref=_Z1_MJCF,
        arm_mjcf_file="z1_gripper.xml",
        mount_body="base",
        mount_pos=(0.18, 0.0, 0.06),
    )
    scene = meshdir.parent / "go2_z1_test_composed.xml"
    scene.write_text(xml)
    try:
        model = mujoco.MjModel.from_xml_path(str(scene))
        names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)]
        legs = [
            f"{leg}_{part}_joint"
            for leg in ("FL", "FR", "RL", "RR")
            for part in ("hip", "thigh", "calf")
        ]
        assert names[1:13] == legs  # names[0] is the unnamed free joint
        assert names[13:] == [f"joint{i}" for i in range(1, 7)] + ["jointGripper"]
        # 7 free-joint qpos + 12 legs + 7 arm.
        assert model.nq == 26
        assert model.nu == 19
    finally:
        scene.unlink(missing_ok=True)


def test_mounted_arm_mass_scale_shrinks_arm_inertial_only() -> None:
    """arm_mass_scale must change Z1 payload mass, not the Go2 carrier."""
    mujoco = pytest.importorskip("mujoco")
    pytest.importorskip("robot_descriptions")
    from openral_core.exceptions import ROSConfigError

    with pytest.raises(ROSConfigError, match="arm_mass_scale"):
        compose_mounted_arm_mjcf(
            base_mjcf_ref=_GO2_MJCF,
            arm_mjcf_ref=_Z1_MJCF,
            arm_mjcf_file="z1_gripper.xml",
            mount_body="base",
            mount_pos=(0.18, 0.0, 0.06),
            arm_mass_scale=0.0,
        )

    def _arm_and_base_mass(scale: float) -> tuple[float, float]:
        xml, meshdir = compose_mounted_arm_mjcf(
            base_mjcf_ref=_GO2_MJCF,
            arm_mjcf_ref=_Z1_MJCF,
            arm_mjcf_file="z1_gripper.xml",
            mount_body="base",
            mount_pos=(0.18, 0.0, 0.06),
            arm_mass_scale=scale,
        )
        scene = meshdir.parent / f"go2_z1_mass_scale_{scale}.xml"
        scene.write_text(xml)
        try:
            model = mujoco.MjModel.from_xml_path(str(scene))
            arm = 0.0
            base = 0.0
            for i in range(model.nbody):
                name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or ""
                mass = float(model.body_mass[i])
                if name.startswith("link") or "gripper" in name.lower():
                    arm += mass
                elif name == "base":
                    base = mass
            return arm, base
        finally:
            scene.unlink(missing_ok=True)

    arm_full, base_full = _arm_and_base_mass(1.0)
    arm_light, base_light = _arm_and_base_mass(0.01)
    assert arm_full > 1.0
    assert arm_light == pytest.approx(arm_full * 0.01, rel=1e-6)
    assert base_light == pytest.approx(base_full, rel=1e-9)


def test_mounted_arm_composite_stands_under_gravity() -> None:
    """The carrier must still hold a stand with the arm's mass on its back."""
    mujoco = pytest.importorskip("mujoco")
    pytest.importorskip("robot_descriptions")
    import numpy as np

    xml, meshdir = compose_mounted_arm_mjcf(
        base_mjcf_ref=_GO2_MJCF,
        arm_mjcf_ref=_Z1_MJCF,
        arm_mjcf_file="z1_gripper.xml",
        mount_body="base",
        mount_pos=(0.18, 0.0, 0.06),
    )
    scene = meshdir.parent / "go2_z1_test_stand.xml"
    scene.write_text(xml)
    try:
        model = mujoco.MjModel.from_xml_path(str(scene))
        data = mujoco.MjData(model)
        assert float(model.opt.gravity[2]) < 0.0
        # The Go2 manifest declares can_lift_kg=8.0; the Z1 must fit under it.
        arm_mass = sum(
            float(model.body_mass[i])
            for i in range(model.nbody)
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or "").startswith("link")
        )
        assert 0.0 < arm_mass <= 8.0

        mujoco.mj_resetDataKeyframe(model, data, 0)
        hub = [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8]
        data.qpos[7:19] = hub
        mujoco.mj_forward(model, data)

        legs = [
            f"{leg}_{part}" for leg in ("FL", "FR", "RL", "RR") for part in ("hip", "thigh", "calf")
        ]
        act = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in legs]
        qadr = [
            model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{n}_joint")]
            for n in legs
        ]
        vadr = [
            model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{n}_joint")]
            for n in legs
        ]
        kp = np.array([23.7, 23.7, 45.43] * 4)
        kv = 0.05 * kp
        target = np.array(hub)
        for _ in range(3000):  # 6 s at the model's 2 ms timestep
            q = np.array([data.qpos[a] for a in qadr])
            dq = np.array([data.qvel[a] for a in vadr])
            tau = kp * (target - q) - kv * dq
            for k, a in enumerate(act):
                lo, hi = model.actuator_ctrlrange[a]
                data.ctrl[a] = float(np.clip(tau[k], lo, hi))
            mujoco.mj_step(model, data)

        assert float(data.qpos[2]) > 0.10, "composite collapsed under the arm's mass"
    finally:
        scene.unlink(missing_ok=True)
