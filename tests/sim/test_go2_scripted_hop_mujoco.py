"""Scripted Go2 hop leaves the go2_walk floor.

The mjlab hop ONNX does not (headless air_ticks=0). This is the test
that would have caught Apply hop never taking the feet off the ground.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openral_core import Action, VLASpec
from openral_hal.go2 import GO2_HOP_JOINT_TARGETS, Go2MujocoHAL
from openral_sim.factory import make_policy
from openral_sim.scene_composers import compose_ground_plane_mjcf

try:
    import mujoco as mj
except Exception as exc:  # mujoco's eager renderer probe can raise non-ImportError types
    pytest.skip(f"mujoco unavailable: {exc}", allow_module_level=True)

_FOOTS = ("FL", "FR", "RL", "RR")
_DT = 0.02
_SECONDS = 2.4  # three crouch-extend-land cycles


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


@pytest.mark.sim
def test_scripted_hop_leaves_the_floor() -> None:
    xml, meshdir = compose_ground_plane_mjcf(mjcf_ref="rd:go2_mj_description")
    path = meshdir.parent / "go2_scripted_hop.xml"
    path.write_text(xml)
    hal = Go2MujocoHAL(
        mjcf_path=str(path),
        gravity_enabled=True,
        settle_steps=10,
        staleness_limit_s=1e9,
    )
    hal.connect()
    policy = make_policy(
        SimpleNamespace(
            vla=VLASpec(
                id="zero",
                weights_uri="local://rskills/rskill-zero-go2-hop-fp32",
                device="cpu",
                extra={
                    "action_dim": 12,
                    "gait": "jump",
                    "dt": 0.02,
                    "hold_targets": list(GO2_HOP_JOINT_TARGETS),
                },
            ),
            scene=SimpleNamespace(cameras=()),
        )
    )
    policy.reset()
    try:
        hal.reset_to_pose(list(GO2_HOP_JOINT_TARGETS))
        walk_kp = next(iter(hal._pd_gains.values()))[0]
        assert walk_kp != pytest.approx(20.0)
        air = 0
        max_foot = -1e9
        max_z = -1e9
        for _ in range(int(_SECONDS / _DT)):
            targets = policy.step({}, "")
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
        assert air >= 20, f"scripted hop stayed planted (air_ticks={air})"
        assert max_foot > 0.18, f"feet only rose to {max_foot:.3f} m"
        assert max_z > 0.42, f"base only rose to {max_z:.3f} m"
    finally:
        hal.disconnect()
