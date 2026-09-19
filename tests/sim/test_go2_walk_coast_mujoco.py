"""Walk coast-to-stand: after the joystick zeros, idle-hold stays upright.

Deadline idle-hold of a mid-gait waypoint is what dumped the Go2 at the
end of Apply walk. This is the test that would have caught that.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openral_core import Action, VLASpec
from openral_core.exceptions import ROSConfigError
from openral_hal.go2 import GO2_HOME_JOINT_TARGETS, Go2MujocoHAL
from openral_observability.dashboard._fall import qpos_is_fallen
from openral_sim.factory import make_policy
from openral_sim.scene_composers import compose_ground_plane_mjcf

try:
    import mujoco  # noqa: F401  # reason: skip if the sim extra is missing
except Exception as exc:  # mujoco's eager renderer probe can raise non-ImportError types
    pytest.skip(f"mujoco unavailable: {exc}", allow_module_level=True)

_DT = 0.02
_WALK_S = 2.0
_COAST_S = 2.0
_IDLE_S = 1.0


def _observation(hal: Go2MujocoHAL) -> dict[str, object]:
    state = hal.read_state()
    xyz, quat_xyzw = hal.base_pose_6dof()
    return {
        "joint_pos": list(state.position),
        "joint_vel": list(state.velocity),
        "base_twist": tuple(float(value) for value in hal.base_twist),
        "base_pose": {
            "xyz": tuple(float(value) for value in xyz),
            "quat_xyzw": tuple(float(value) for value in quat_xyzw),
        },
    }


@pytest.mark.sim
def test_walk_coast_to_stand_stays_upright_after_idle_hold() -> None:
    pytest.importorskip("onnxruntime")
    xml, meshdir = compose_ground_plane_mjcf(mjcf_ref="rd:go2_mj_description")
    path = meshdir.parent / "go2_walk_coast.xml"
    path.write_text(xml)
    hal = Go2MujocoHAL(
        mjcf_path=str(path),
        gravity_enabled=True,
        settle_steps=10,
        staleness_limit_s=1e9,
    )
    policy = None
    try:
        try:
            policy = make_policy(
                SimpleNamespace(
                    vla=VLASpec(
                        id="rsl_rl_onnx",
                        weights_uri="hf://diasAiMaster/unitree-go2-velocity-flat",
                        device="cpu",
                        extra={
                            "velocity_commands": [0.35, 0.0, 0.0],
                            "horizon_s": _WALK_S + _COAST_S,
                            "coast_to_stand_s": _COAST_S,
                        },
                    ),
                    scene=SimpleNamespace(cameras=()),
                )
            )
        except (ROSConfigError, OSError) as exc:
            pytest.skip(f"rsl-rl ONNX checkpoint unavailable: {exc}")
        policy.reset()
        hal.connect()
        hal.reset_to_pose(list(GO2_HOME_JOINT_TARGETS))
        ticks = int((_WALK_S + _COAST_S) / _DT)
        for _ in range(ticks):
            targets = policy.step(_observation(hal), "")
            hal.send_action(
                Action(
                    control_mode="joint_position",
                    horizon=1,
                    joint_targets=[[float(v) for v in targets]],
                    stamp_ns=0,
                )
            )
        for _ in range(int(_IDLE_S / _DT)):
            assert hal.idle_step(_DT)
        assert hal._data is not None
        qpos = [float(v) for v in hal._data.qpos]
        assert not qpos_is_fallen(qpos), (
            f"walk coast then idle-hold tipped z={qpos[2]:.3f} quat={qpos[3:7]}"
        )
        assert qpos[2] > 0.20, f"base dropped to z={qpos[2]:.3f} m"
    finally:
        if policy is not None:
            policy.close()
        hal.disconnect()
