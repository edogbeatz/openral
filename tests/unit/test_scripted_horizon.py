"""Scripted VLA horizon — opt-in complete, not a deadline abort."""

from __future__ import annotations

from openral_rskill_ros.scripted_horizon import (
    optional_positive_float,
    optional_positive_int,
    scripted_horizon_done,
)


def test_always_emits_first_chunk() -> None:
    assert scripted_horizon_done(
        ticks=1, elapsed_s=99.0, horizon_ticks=1, horizon_s=0.01
    ) is False


def test_horizon_ticks_completes_after_last_emit() -> None:
    assert scripted_horizon_done(
        ticks=90, elapsed_s=3.0, horizon_ticks=90, horizon_s=None
    ) is False
    assert scripted_horizon_done(
        ticks=91, elapsed_s=3.0, horizon_ticks=90, horizon_s=None
    ) is True


def test_horizon_s_completes_after_budget() -> None:
    assert scripted_horizon_done(
        ticks=10, elapsed_s=7.9, horizon_ticks=None, horizon_s=8.0
    ) is False
    assert scripted_horizon_done(
        ticks=10, elapsed_s=8.0, horizon_ticks=None, horizon_s=8.0
    ) is True


def test_unset_horizon_never_self_terminates() -> None:
    assert scripted_horizon_done(
        ticks=10_000, elapsed_s=120.0, horizon_ticks=None, horizon_s=None
    ) is False


def test_optional_parsers() -> None:
    assert optional_positive_float("8.0") == 8.0
    assert optional_positive_float(0) is None
    assert optional_positive_float("nope") is None
    assert optional_positive_int(90) == 90
    assert optional_positive_int(-1) is None
