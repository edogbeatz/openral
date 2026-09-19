"""Gym spring_jump ONNX leaves the go2_walk floor higher than the scripted bounce.

The mjlab hop ONNX does not (headless air_ticks=0). Dashboard hop Apply
uses this checkpoint. Skip only when mujoco is missing or the ONNX fetch
fails (ROSConfigError — weights are not vendored).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from openral_core import Action, RSkillManifest, VLASpec
from openral_core.exceptions import ROSConfigError
from openral_hal.go2 import Go2MujocoHAL
from openral_sim.factory import make_policy
from openral_sim.scene_composers import compose_ground_plane_mjcf

try:
    import mujoco as mj
except Exception as exc:  # mujoco's eager renderer probe can raise non-ImportError types
    pytest.skip(f"mujoco unavailable: {exc}", allow_module_level=True)

_FOOTS = ("FL", "FR", "RL", "RR")
_DT = 0.02
_SECONDS = 2.0
_REPO = Path(__file__).resolve().parents[2]
_SKILL_DIR = _REPO / "rskills" / "rsl-rl-onnx-go2-spring-jump"
_MANIFEST = _SKILL_DIR / "rskill.yaml"


def _foot_bottoms(hal: Go2MujocoHAL) -> list[float]:
    model, data = hal._model, hal._data
    assert model is not None and data is not None
    out: list[float] = []
    for name in _FOOTS:
        gid = mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, name)
        if gid < 0:
            raise AssertionError(f"missing foot geom {name!r}")
        out.append(float(data.geom_xpos[gid][2] - model.geom_size[gid][0]))
    return out


def _obs(hal: Go2MujocoHAL) -> dict[str, object]:
    state = hal.read_state()
    xyz, quat = hal.base_pose_6dof()
    return {
        "joint_pos": list(state.position),
        "joint_vel": list(state.velocity),
        "base_twist": hal.base_twist,
        "base_pose": {"xyz": xyz, "quat_xyzw": quat},
    }


@pytest.mark.sim
def test_spring_jump_leaves_the_floor_high() -> None:
    xml, meshdir = compose_ground_plane_mjcf(mjcf_ref="rd:go2_mj_description")
    path = meshdir.parent / "go2_spring_jump.xml"
    path.write_text(xml)
    manifest = RSkillManifest.from_yaml(str(_MANIFEST))
    pose = [float(v) for v in (manifest.starting_pose or [])]
    assert len(pose) == 12
    extras = dict(manifest.policy_extras)
    hal = Go2MujocoHAL(
        mjcf_path=str(path),
        gravity_enabled=True,
        settle_steps=10,
        staleness_limit_s=1e9,
    )
    hal.connect()
    try:
        try:
            policy = make_policy(
                SimpleNamespace(
                    vla=VLASpec(
                        id="rsl_rl_onnx",
                        weights_uri=str(_SKILL_DIR),
                        device="cpu",
                        extra=extras,
                    ),
                    scene=SimpleNamespace(cameras=()),
                )
            )
        except ROSConfigError as exc:
            pytest.skip(f"spring_jump ONNX unavailable: {exc}")
        policy.reset()
        try:
            hal.reset_to_pose(pose)
            walk_kp = next(iter(hal._pd_gains.values()))[0]
            assert walk_kp != pytest.approx(20.0)
            air = 0
            max_foot = -1e9
            max_z = -1e9
            for _ in range(int(_SECONDS / _DT)):
                targets = policy.step(_obs(hal), "")
                hal.send_action(
                    Action(
                        control_mode="joint_position",
                        horizon=1,
                        joint_targets=[[float(v) for v in targets]],
                        stamp_ns=0,
                    )
                )
                feet = _foot_bottoms(hal)
                max_foot = max(max_foot, *feet)
                max_z = max(max_z, float(hal._data.qpos[2]))
                if all(value > 0.01 for value in feet):
                    air += 1
            assert air >= 8, f"spring_jump stayed planted (air_ticks={air})"
            assert max_foot > 0.28, f"feet only rose to {max_foot:.3f} m"
            assert max_z > 0.50, f"base only rose to {max_z:.3f} m"
        finally:
            policy.close()
    finally:
        hal.disconnect()
