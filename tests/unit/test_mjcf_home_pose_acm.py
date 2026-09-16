"""ACM rest-pose excludes must use the spawn / Hub stand, not q=0.

Go2's menagerie ``home`` (thigh 0.9, calf −1.8) is not enough after
OpenRAL #6: HAL snaps hips to Hub ±0.1. ACM seeded at keyframe 0
(hip 0) misses FL_thigh↔FR_thigh, base↔RR_thigh (~1.4 mm), and
FR_calf↔RR_thigh (~6 mm). The kernel then estops at step 0
(``sim.estop_initial_configuration`` / ``safety.collision``).
Home-stand extras are conservative-capsule admits, not a mesh/cert
claim.

Hermetic inline MJCF (no asset download). Gates on mujoco.
"""

from __future__ import annotations

import math

import pytest

mujoco = pytest.importorskip("mujoco")

from openral_safety.mjcf_lowering import (  # noqa: E402
    _actuated_q_from_keyframe,
    _as_scalar,
    _keyframe_qpos,
    lower_collision_params,
)

# Three collinear links along +X. Parent↔child pairs are always excluded.
# link1↔link3 overlap only when the middle hinge is ~π (folded), not at q=0.
_FOLDED_HOME_MJCF = """
<mujoco>
  <worldbody>
    <body name="link1" pos="0 0 0">
      <joint name="j1" type="hinge" axis="0 0 1"/>
      <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
      <body name="link2" pos="0.4 0 0">
        <joint name="j2" type="hinge" axis="0 0 1"/>
        <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
        <body name="link3" pos="0.4 0 0">
          <joint name="j3" type="hinge" axis="0 0 1"/>
          <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
        </body>
      </body>
    </body>
  </worldbody>
  <keyframe>
    <key name="home" qpos="0 3.141592653589793 0"/>
  </keyframe>
</mujoco>
"""

_NO_KEYFRAME_MJCF = """
<mujoco>
  <worldbody>
    <body name="link1" pos="0 0 0">
      <joint name="j1" type="hinge" axis="0 0 1"/>
      <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
      <body name="link2" pos="0.4 0 0">
        <joint name="j2" type="hinge" axis="0 0 1"/>
        <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
        <body name="link3" pos="0.4 0 0">
          <joint name="j3" type="hinge" axis="0 0 1"/>
          <geom type="capsule" fromto="0 0 0 0.36 0 0" size="0.05"/>
        </body>
      </body>
    </body>
  </worldbody>
</mujoco>
"""

_JOINTS = ["j1", "j2", "j3"]


def _acm_pairs(params: dict[str, object]) -> set[tuple[str, str]]:
    names = list(params["collision_link_names"])
    raw = list(params["collision_allowed_pairs"])
    out: set[tuple[str, str]] = set()
    for i in range(0, len(raw), 2):
        a, b = names[int(raw[i])], names[int(raw[i + 1])]
        out.add((a, b) if a < b else (b, a))
    return out


def test_keyframe_home_excludes_folded_skip_one_but_not_at_zero() -> None:
    """Self-collision stays on at q=0; home keyframe only excludes rest overlaps."""
    folded = mujoco.MjModel.from_xml_string(_FOLDED_HOME_MJCF)
    straight = mujoco.MjModel.from_xml_string(_NO_KEYFRAME_MJCF)

    home_params = lower_collision_params(folded, _JOINTS)
    zero_params = lower_collision_params(straight, _JOINTS)
    seeded_params = lower_collision_params(
        straight, _JOINTS, seed_q=[0.0, math.pi, 0.0]
    )

    home_acm = _acm_pairs(home_params)
    zero_acm = _acm_pairs(zero_params)
    seeded_acm = _acm_pairs(seeded_params)

    skip = ("link1", "link3")
    assert skip in home_acm
    assert skip in seeded_acm
    assert skip not in zero_acm
    # Parent-child still excluded either way — not a disable-all-safety flag.
    assert ("link1", "link2") in home_acm
    assert ("link1", "link2") in zero_acm
    assert home_params["self_collision_enabled"] is True
    assert zero_params["self_collision_enabled"] is True


def test_keyframe_q_matches_home_stand() -> None:
    model = mujoco.MjModel.from_xml_string(_FOLDED_HOME_MJCF)
    q = _actuated_q_from_keyframe(model, 3)
    assert q[0] == pytest.approx(0.0)
    assert q[1] == pytest.approx(math.pi)
    assert q[2] == pytest.approx(0.0)
    empty = mujoco.MjModel.from_xml_string(_NO_KEYFRAME_MJCF)
    assert _actuated_q_from_keyframe(empty, 3) == [0.0, 0.0, 0.0]


# Sibling thighs hanging down. At hip=0 they clear; Hub ±0.1 rotates them
# inward around +X so conservative capsules overlap (Go2 FL_thigh↔FR_thigh).
_HUB_HIP_THIGHS_MJCF = """
<mujoco>
  <worldbody>
    <body name="FL_thigh" pos="0 0.06 0">
      <joint name="FL_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
    <body name="FR_thigh" pos="0 -0.06 0">
      <joint name="FR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
  </worldbody>
</mujoco>
"""


def test_hub_hip_seed_excludes_thigh_pair_menagerie_hips_do_not() -> None:
    """Hub ±0.1 must ACM-exclude thighs; menagerie hip 0 leaves the pair on."""
    model = mujoco.MjModel.from_xml_string(_HUB_HIP_THIGHS_MJCF)
    joints = ["FL_hip_joint", "FR_hip_joint"]
    menagerie = lower_collision_params(model, joints, seed_q=[0.0, 0.0])
    hub = lower_collision_params(model, joints, seed_q=[-0.1, 0.1])
    pair = ("FL_thigh", "FR_thigh")
    assert pair not in _acm_pairs(menagerie)
    assert pair in _acm_pairs(hub)
    assert hub["self_collision_enabled"] is True


# Vertical torso + hanging thighs. At hip=0 the shafts clear the base;
# Hub ±0.1 rotates them inward so conservative capsules clip base↔thigh
# (Go2 safety.collision a=base b=RR_thigh, min_distance_m≈−0.00138).
_HUB_HIP_BASE_THIGHS_MJCF = """
<mujoco>
  <worldbody>
    <body name="base" pos="0 0 0">
      <geom type="capsule" fromto="0 0 0.05 0 0 -0.35" size="0.04"/>
    </body>
    <body name="FL_thigh" pos="0 0.10 0">
      <joint name="FL_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.04"/>
    </body>
    <body name="FR_thigh" pos="0 -0.10 0">
      <joint name="FR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.04"/>
    </body>
    <body name="RL_thigh" pos="0 0.10 0">
      <joint name="RL_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.04"/>
    </body>
    <body name="RR_thigh" pos="0 -0.10 0">
      <joint name="RR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.04"/>
    </body>
  </worldbody>
</mujoco>
"""

_HUB_BASE_THIGH_PAIRS = (
    ("FL_thigh", "base"),
    ("FR_thigh", "base"),
    ("RL_thigh", "base"),
    ("RR_thigh", "base"),
)


def test_hub_hip_seed_excludes_base_thigh_pairs_menagerie_hips_do_not() -> None:
    """Hub ±0.1 must ACM-exclude base↔thigh; menagerie hip 0 leaves them on."""
    model = mujoco.MjModel.from_xml_string(_HUB_HIP_BASE_THIGHS_MJCF)
    joints = ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint"]
    menagerie = lower_collision_params(model, joints, seed_q=[0.0, 0.0, 0.0, 0.0])
    hub = lower_collision_params(model, joints, seed_q=[-0.1, 0.1, -0.1, 0.1])
    men_acm = _acm_pairs(menagerie)
    hub_acm = _acm_pairs(hub)
    for pair in _HUB_BASE_THIGH_PAIRS:
        assert pair not in men_acm
        assert pair in hub_acm
    assert hub["self_collision_enabled"] is True


# Front calf vs rear thigh hanging shafts. At hip=0 they clear; Hub-magnitude
# opposite hip signs rotate them inward so conservative capsules clip
# FR_calf↔RR_thigh (Go2 safety.collision a=FR_calf b=RR_thigh,
# min_distance_m≈−0.006). Same mechanism as the thigh↔thigh fixture.
_HUB_HIP_CALF_THIGH_MJCF = """
<mujoco>
  <worldbody>
    <body name="FR_calf" pos="0 -0.06 0">
      <joint name="FR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
    <body name="RR_thigh" pos="0 0.06 0">
      <joint name="RR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
  </worldbody>
</mujoco>
"""

_GO2_LEGS = ("FL", "FR", "RL", "RR")
_HUB_CALF_THIGH_SKIP_PAIRS = tuple(
    (f"{calf}_calf", f"{thigh}_thigh")
    for calf in _GO2_LEGS
    for thigh in _GO2_LEGS
    if calf != thigh
)


def test_hub_hip_seed_excludes_calf_thigh_skip_pairs_menagerie_hips_do_not() -> None:
    """Hub ±0.1 must ACM-exclude FR_calf↔RR_thigh; menagerie hip 0 leaves it on."""
    model = mujoco.MjModel.from_xml_string(_HUB_HIP_CALF_THIGH_MJCF)
    joints = ["FR_hip_joint", "RR_hip_joint"]
    menagerie = lower_collision_params(model, joints, seed_q=[0.0, 0.0])
    hub = lower_collision_params(model, joints, seed_q=[0.1, -0.1])
    pair = ("FR_calf", "RR_thigh")
    assert pair not in _acm_pairs(menagerie)
    assert pair in _acm_pairs(hub)
    assert hub["self_collision_enabled"] is True


def test_go2_bench_lists_full_hub_home_calf_thigh_skip_set() -> None:
    """Scene extras list the full 12-pair calf↔thigh skip set, not one pair."""
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    data = yaml.safe_load((root / "scenes" / "deploy" / "go2_bench.yaml").read_text())
    pairs = [list(item) for item in data["extra_allowed_collision_pairs"]]
    assert len(_HUB_CALF_THIGH_SKIP_PAIRS) == 12
    for a, b in _HUB_CALF_THIGH_SKIP_PAIRS:
        assert [a, b] in pairs, f"go2_bench missing {[a, b]}"
    assert ["FR_calf", "RR_thigh"] in pairs
    assert ["FL_calf", "FL_thigh"] not in pairs


# Front calf vs rear hip hanging shafts. At hip=0 they clear; Hub-magnitude
# opposite hip signs rotate them inward so conservative capsules clip
# FR_calf↔RR_hip (Go2 safety.collision a=FR_calf b=RR_hip,
# min_distance_m≈−0.0188). Same mechanism as the calf↔thigh fixture.
_HUB_HIP_CALF_HIP_MJCF = """
<mujoco>
  <worldbody>
    <body name="FR_calf" pos="0 -0.06 0">
      <joint name="FR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
    <body name="RR_hip" pos="0 0.06 0">
      <joint name="RR_hip_joint" type="hinge" axis="1 0 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.05"/>
    </body>
  </worldbody>
</mujoco>
"""

_HUB_CALF_HIP_SKIP_PAIRS = tuple(
    (f"{calf}_calf", f"{hip}_hip")
    for calf in _GO2_LEGS
    for hip in _GO2_LEGS
    if calf != hip
)


def test_hub_hip_seed_excludes_calf_hip_skip_pairs_menagerie_hips_do_not() -> None:
    """Hub ±0.1 must ACM-exclude FR_calf↔RR_hip; menagerie hip 0 leaves it on."""
    model = mujoco.MjModel.from_xml_string(_HUB_HIP_CALF_HIP_MJCF)
    joints = ["FR_hip_joint", "RR_hip_joint"]
    menagerie = lower_collision_params(model, joints, seed_q=[0.0, 0.0])
    hub = lower_collision_params(model, joints, seed_q=[0.1, -0.1])
    pair = ("FR_calf", "RR_hip")
    assert pair not in _acm_pairs(menagerie)
    assert pair in _acm_pairs(hub)
    assert hub["self_collision_enabled"] is True


def test_go2_bench_lists_full_hub_home_calf_hip_skip_set() -> None:
    """Scene extras list the full 12-pair calf↔hip skip set, not one pair."""
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    data = yaml.safe_load((root / "scenes" / "deploy" / "go2_bench.yaml").read_text())
    pairs = [list(item) for item in data["extra_allowed_collision_pairs"]]
    assert len(_HUB_CALF_HIP_SKIP_PAIRS) == 12
    for a, b in _HUB_CALF_HIP_SKIP_PAIRS:
        assert [a, b] in pairs, f"go2_bench missing {[a, b]}"
    assert ["FR_calf", "RR_hip"] in pairs
    assert ["FL_calf", "FL_hip"] not in pairs


def test_2d_key_qpos_does_not_typeerror() -> None:
    """MuJoCo stores key_qpos as (nkey, nq); float(row) must not raise."""
    import numpy as np

    class _Fake:
        nq = 3
        nkey = 1
        key_qpos = np.array([[0.0, math.pi, 0.0]])

    qpos = _keyframe_qpos(_Fake(), keyframe_index=0)
    assert qpos[1] == pytest.approx(math.pi)
    assert _as_scalar(np.array(1.5)) == pytest.approx(1.5)
