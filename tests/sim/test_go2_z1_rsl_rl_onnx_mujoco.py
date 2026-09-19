"""Go2 + Z1 under the real rsl-rl velocity policy: the spawn pose must survive a walk.

`rskill-rsl_rl_onnx-go2-velocity_flat` was trained on the BARE Go2 and emits
12-D leg-only rows. A 12-D row leaves `Go2Z1MujocoHAL`'s sticky arm hold alone,
so on a fresh connect the arm walks at whatever the twin spawned with — nobody
has to command the arm for its pose to decide the outcome.

At honest arm mass that pose is decisive and was measured, not guessed: from the
menagerie `home` the composite pitches over in ~0.7 s on every randomised
rollout, and from `ready` it walks. `GO2_Z1_SPAWN_JOINT_TARGETS` therefore
spawns at `ready`, and this suite is the guard on that choice — the `home` leg
is included so a regression cannot pass by making both directions survive.

The second guard here is on a different axis: **observation age**. This policy
balances on proprio it expects to be current, and delaying the observation
bundle by two 20 ms policy ticks drops survival from 8/8 to 1/8. The deploy
scene pays for that freshness with `publish_rate_hz: 200.0`, so these tests
bracket the cliff to keep a future rate change from silently crossing it.

Real menagerie assets, real MuJoCo, the real Hub ONNX checkpoint, and the same
`tools/go2_z1_mass_balance.py` rollout the finding came from (CLAUDE.md §1.11).
Full evidence, including the three rejected explanations, in
`docs/reference/go2-z1-mass-balance.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

pytest.importorskip("mujoco")
pytest.importorskip("robot_descriptions")
pytest.importorskip("onnxruntime")

sys.path.insert(0, str(_REPO / "tools"))

#: Long enough to clear the failure by 4x — `home` tips at ~0.70-1.00 s — while
#: keeping the suite inside its budget. Two rollouts, no batteries.
_ROLLOUT_S = 3.0

#: The manifest ships 0.01 for locomotion demos, which masks this entirely: at
#: that scale every named pose survives. The finding only exists at honest mass.
_HONEST = 1.0


def _walk(arm, pose: str):
    """One rollout via the shipped tool; skips if the Hub checkpoint is unreachable."""
    from go2_z1_mass_balance import walk
    from openral_core.exceptions import ROSConfigError

    try:
        return walk(
            arm=arm,
            pose=pose,
            arm_mass_scale=_HONEST,
            velocity_commands=(0.5, 0.0, 0.0),
            seconds=_ROLLOUT_S,
            trial=0,
            perturbation=0.0,
        )
    except (ROSConfigError, OSError) as exc:  # pragma: no cover - network / asset state
        pytest.skip(f"rsl-rl ONNX checkpoint unavailable: {exc}")


@pytest.mark.sim
def test_spawn_hold_walks_without_a_recalibrate() -> None:
    """A fresh twin must survive a 12-D gait with nobody having posed the arm.

    `arm=None` is the production path: no `reset_to_pose`, so the policy walks
    against the spawn hold exactly as `openral deploy sim` does before any
    Recalibrate.
    """
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY

    rollout = _walk(None, "spawn")

    assert not rollout.tipped, (
        f"the spawn pose tipped after {rollout.survived_s} s — a walk issued "
        "before any Recalibrate must stay upright at honest arm mass"
    )
    assert rollout.survived_s == pytest.approx(_ROLLOUT_S, abs=1e-6)
    assert rollout.distance_m > 0.5, "the dog held still instead of walking"
    # The arm was carried, not dragged or waved: the servos held the pose and
    # nothing on the arm touched the robot or the floor.
    assert rollout.arm_drift_rad < 1e-2
    assert rollout.arm_contacts == 0
    assert GO2_Z1_ARM_READY[1] == pytest.approx(1.2)


@pytest.mark.sim
def test_menagerie_home_is_the_pose_that_tips() -> None:
    """The rejected spawn must still fail, or the test above proves nothing.

    Without this leg a change that makes every arm pose survive (raising the
    PD gains, re-scaling the arm inertias, softening the tip gate) would read
    as a pass while destroying the evidence the spawn choice rests on.
    """
    from openral_hal.go2_z1 import GO2_Z1_ARM_HOME

    rollout = _walk(GO2_Z1_ARM_HOME, "home")

    assert rollout.tipped, (
        "the menagerie `home` arm pose no longer tips the composite. Re-run "
        "`tools/go2_z1_mass_balance.py walk` and revisit "
        "GO2_Z1_SPAWN_JOINT_TARGETS + docs/reference/go2-z1-mass-balance.md — "
        "the spawn pose was chosen because this pose fell"
    )
    assert rollout.survived_s < 1.5
    assert rollout.arm_contacts == 0, "it pitched over; it did not trip on its own arm"


#: The deploy scene's arm mass. The freshness cliff was characterised here
#: rather than at honest mass because this is what the live graph composes.
_LIVE = 0.01

#: Long enough to catch the stale leg — a 3-tick-old observation tips the dog in
#: 2.0-4.3 s on every randomised trial — without paying for a 30 s rollout.
_STALE_ROLLOUT_S = 5.0


def _walk_aged(age_ticks: int):
    """One rollout at the deploy scene's mass with an *age_ticks*-stale observation."""
    from go2_z1_mass_balance import walk
    from openral_core.exceptions import ROSConfigError
    from openral_hal.go2_z1 import GO2_Z1_ARM_READY

    try:
        return walk(
            arm=GO2_Z1_ARM_READY,
            pose="ready",
            arm_mass_scale=_LIVE,
            velocity_commands=(0.5, 0.0, 0.0),
            seconds=_STALE_ROLLOUT_S,
            trial=0,
            perturbation=1.0,
            proprio_age_ticks=age_ticks,
        )
    except (ROSConfigError, OSError) as exc:  # pragma: no cover - network / asset state
        pytest.skip(f"rsl-rl ONNX checkpoint unavailable: {exc}")


@pytest.mark.sim
def test_fresh_proprio_walks_and_stale_proprio_tips() -> None:
    """Bracket the proprio freshness cliff from both sides.

    One tick of observation age is the regime the deploy graph measured into
    (median 5.1 ms, well under one 20 ms tick) and it must walk. Three ticks
    must still tip, or the cliff has moved and the deploy scene's 200 Hz
    publishers are no longer justified by anything.
    """
    from go2_z1_mass_balance import PROPRIO_AGE_CLIFF_TICKS

    fresh = _walk_aged(1)
    stale = _walk_aged(3)

    assert not fresh.tipped, (
        f"a 20 ms-old observation tipped the dog after {fresh.survived_s} s. The "
        "live graph runs fresher than this, so the walk should survive it"
    )
    assert fresh.distance_m > 0.5, "the dog held still instead of walking"
    assert stale.tipped, (
        "a 60 ms-old observation no longer tips the composite. Re-run "
        "`tools/go2_z1_mass_balance.py stale` and revisit PROPRIO_AGE_CLIFF_TICKS "
        "plus the 200 Hz publishers in scenes/deploy/go2_z1_walk.yaml — those "
        "rates exist only because this rollout falls"
    )
    # The guard is only meaningful while the measured cliff sits inside it.
    assert 1 < PROPRIO_AGE_CLIFF_TICKS < 3
