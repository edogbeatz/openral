"""Unit tests for the opt-in TypeSafe S2 gate.

Loads real Go2 / Go2+Z1 rSkill manifests (CLAUDE.md §1.11). The TypeSafe
HTTP client is injected as a recording double at the network boundary —
the same exception as FakeToolUseClient / the OTLP collector fake.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from openral_core import ExecuteRskillTool, RobotCapabilities, RSkillManifest, WaitTool
from openral_reasoner import build_tool_palette
from openral_reasoner.context import PromptRecord
from openral_reasoner.palette import ToolPalette
from openral_reasoner.typesafe_gate import (
    TypeSafeGate,
    answers_from_sdk_result,
    apply_typesafe_to_tick,
    build_typesafe_gate_from_env,
    is_typesafe_enabled,
    operator_prompt_for_typesafe,
    restrict_execute_skills,
)
from openral_reasoner.typesafe_policy import (
    ChoiceAnswer,
    NoulAnswer,
    TypeSafeAnswers,
    decide_reasoner_typesafe,
)
from openral_reasoner.typesafe_questions import (
    build_reasoner_questions,
    choice_key_for_rskill_id,
    skills_with_arm_pose,
    skills_with_velocity_commands,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RSKILLS_DIR = REPO_ROOT / "rskills"

WALK_DIR = "rsl-rl-onnx-go2-velocity-flat"
HOP_DIR = "rsl-rl-onnx-go2-spring-jump"
ARM_DIR = "rskill-zero-go2_z1-arm_ready-fp32"
NAV2_DIR = "rskill-nav2-navigate-to-pose"


def _load_manifest(skill_dirname: str) -> RSkillManifest:
    path = RSKILLS_DIR / skill_dirname / "rskill.yaml"
    if not path.exists():
        pytest.skip(f"rskill fixture missing: {path}")
    with path.open() as fh:
        return RSkillManifest.model_validate(yaml.safe_load(fh))


def _go2_palette() -> ToolPalette:
    walk = _load_manifest(WALK_DIR)
    return build_tool_palette(
        installed_skills=[walk],
        robot_capabilities=RobotCapabilities(embodiment_tags=["go2"]),
    )


def _go2_z1_palette() -> ToolPalette:
    walk = _load_manifest(WALK_DIR)
    hop = _load_manifest(HOP_DIR)
    arm = _load_manifest(ARM_DIR)
    return build_tool_palette(
        installed_skills=[walk, hop, arm],
        robot_capabilities=RobotCapabilities(embodiment_tags=["go2_z1"]),
    )


class _StaticAsker:
    """Network-boundary double: returns canned TypeSafeAnswers."""

    def __init__(self, answers: TypeSafeAnswers) -> None:
        self.answers = answers
        self.calls: list[tuple[Any, Any]] = []

    def ask(self, state: Any, questions: Any) -> TypeSafeAnswers:
        self.calls.append((state, questions))
        return self.answers


def _safe_noul(noul: float = 0.02) -> dict[str, NoulAnswer]:
    return {"asks_bypass_safety": NoulAnswer(noul=noul, confidence=0.9)}


def test_is_typesafe_enabled_requires_flag_and_key() -> None:
    assert is_typesafe_enabled({}) is False
    assert is_typesafe_enabled({"TYPESAFE_API_KEY": "k"}) is False
    assert is_typesafe_enabled({"OPENRAL_TYPESAFE": "1"}) is False
    assert is_typesafe_enabled({"OPENRAL_TYPESAFE": "1", "TYPESAFE_API_KEY": "k"}) is True


def test_build_typesafe_gate_from_env_stays_off_without_flag() -> None:
    assert build_typesafe_gate_from_env({"TYPESAFE_API_KEY": "k"}) is None


def test_build_typesafe_gate_from_env_probes_optional_sdk() -> None:
    env = {"OPENRAL_TYPESAFE": "1", "TYPESAFE_API_KEY": "k"}
    gate = build_typesafe_gate_from_env(env)
    try:
        import typesafe_sdk  # noqa: F401
    except ImportError:
        assert gate is None
    else:
        assert gate is not None


def test_answers_from_sdk_result_accepts_mapping_payloads() -> None:
    parsed = answers_from_sdk_result(
        SimpleNamespace(
            nouls={"asks_bypass_safety": {"noul": 0.1, "confidence": 0.8}},
            choices={"handler": {"choice": "reasoner", "confidence": 0.9}},
        ),
    )
    assert parsed.nouls["asks_bypass_safety"].noul == pytest.approx(0.1)
    assert parsed.choices["handler"].choice == "reasoner"


def test_go2_questions_include_walk_not_arm() -> None:
    palette = _go2_palette()
    walk = _load_manifest(WALK_DIR)
    assert walk.name in palette.execute_rskill_ids
    questions = build_reasoner_questions(palette)
    assert "walk_command" in questions
    assert "arm_pose" not in questions
    walk_q = questions["walk_command"]
    assert isinstance(walk_q, dict)
    criteria = walk_q["criteria"]
    assert isinstance(criteria, dict)
    assert "go left" in str(criteria["turn_left"]).lower()
    instructions = walk_q["instructions"]
    assert isinstance(instructions, dict)
    assert "go left" in str(instructions["question"]).lower()
    assert skills_with_velocity_commands(palette)
    assert not skills_with_arm_pose(palette)


def test_go2_z1_questions_include_walk_hop_and_arm() -> None:
    palette = _go2_z1_palette()
    questions = build_reasoner_questions(palette)
    assert "walk_command" in questions
    assert "arm_pose" in questions
    walk = _load_manifest(WALK_DIR)
    hop = _load_manifest(HOP_DIR)
    arm = _load_manifest(ARM_DIR)
    keys = questions["chosen_skill"]["criteria"]
    assert isinstance(keys, dict)
    assert choice_key_for_rskill_id(walk.name) in keys
    assert choice_key_for_rskill_id(hop.name) in keys
    assert choice_key_for_rskill_id(arm.name) in keys
    vel = {entry.rskill_id for entry in skills_with_velocity_commands(palette)}
    assert walk.name in vel
    assert hop.name not in vel


def test_hop_in_place_skips_llm_without_joystick_override() -> None:
    """Live Jev 2026-09-19: 'hop' → hop skill, walk_command=none, YAML extras."""
    palette = _go2_z1_palette()
    hop = _load_manifest(HOP_DIR)
    key = choice_key_for_rskill_id(hop.name)
    answers = TypeSafeAnswers(
        nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.85, confidence=1.0)},
        choices={
            "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.83),
            "chosen_skill": ChoiceAnswer(choice=key, confidence=0.91),
            "walk_command": ChoiceAnswer(choice="none", confidence=0.97),
            "arm_pose": ChoiceAnswer(choice="none", confidence=0.74),
        },
    )
    decision = decide_reasoner_typesafe(answers, palette=palette, prompt_text="hop")
    assert decision.handler == "deterministic_skill"
    call = decision.skip_llm_call
    assert isinstance(call, ExecuteRskillTool)
    assert call.rskill_id == hop.name
    assert call.goal_params_json == ""


def test_adapt_hop_for_z1_later_falls_through_to_reasoner() -> None:
    """Live Jev 2026-09-19: planning prompt, chosen_skill conf below restrict."""
    palette = _go2_z1_palette()
    hop = _load_manifest(HOP_DIR)
    decision = decide_reasoner_typesafe(
        TypeSafeAnswers(
            nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.62, confidence=1.0)},
            choices={
                "handler": ChoiceAnswer(choice="reasoner", confidence=0.64),
                "chosen_skill": ChoiceAnswer(
                    choice=choice_key_for_rskill_id(hop.name),
                    confidence=0.43,
                ),
                "walk_command": ChoiceAnswer(choice="none", confidence=1.0),
                "arm_pose": ChoiceAnswer(choice="none", confidence=0.57),
            },
        ),
        palette=palette,
        prompt_text="adapt the hop skill for go2 z1 later",
    )
    assert decision.handler == "reasoner"
    assert decision.skip_llm_call is None
    assert decision.keep_skill_ids is None


def test_nav2_does_not_get_go2_joystick_question() -> None:
    """Nav2 also has action navigate, but no velocity_commands schema field."""
    nav2 = _load_manifest(NAV2_DIR)
    palette = build_tool_palette(
        installed_skills=[nav2],
        robot_capabilities=RobotCapabilities(embodiment_tags=list(nav2.embodiment_tags)),
    )
    assert nav2.name in palette.execute_rskill_ids
    questions = build_reasoner_questions(palette)
    assert "walk_command" not in questions


def test_walk_forward_skips_llm_with_joystick_params() -> None:
    palette = _go2_palette()
    walk = _load_manifest(WALK_DIR)
    key = choice_key_for_rskill_id(walk.name)
    answers = TypeSafeAnswers(
        nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.95, confidence=0.9)},
        choices={
            "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.92),
            "chosen_skill": ChoiceAnswer(choice=key, confidence=0.91),
            "walk_command": ChoiceAnswer(choice="forward", confidence=0.9),
        },
    )
    decision = decide_reasoner_typesafe(
        answers,
        palette=palette,
        prompt_text="walk forward",
    )
    assert decision.handler == "deterministic_skill"
    call = decision.skip_llm_call
    assert isinstance(call, ExecuteRskillTool)
    assert call.rskill_id == walk.name
    assert '"velocity_commands":[0.5,0.0,0.0]' in call.goal_params_json.replace(" ", "")


def test_go_left_skips_llm_with_turn_left_yaw() -> None:
    palette = _go2_palette()
    walk = _load_manifest(WALK_DIR)
    key = choice_key_for_rskill_id(walk.name)
    answers = TypeSafeAnswers(
        nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.95, confidence=0.9)},
        choices={
            "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.92),
            "chosen_skill": ChoiceAnswer(choice=key, confidence=0.91),
            "walk_command": ChoiceAnswer(choice="turn_left", confidence=0.9),
        },
    )
    decision = decide_reasoner_typesafe(
        answers,
        palette=palette,
        prompt_text="go left",
    )
    assert decision.handler == "deterministic_skill"
    call = decision.skip_llm_call
    assert isinstance(call, ExecuteRskillTool)
    assert '"velocity_commands":[0.0,0.0,0.6]' in call.goal_params_json.replace(" ", "")


def test_arm_ready_skips_llm_with_pose_param() -> None:
    palette = _go2_z1_palette()
    arm = _load_manifest(ARM_DIR)
    key = choice_key_for_rskill_id(arm.name)
    answers = TypeSafeAnswers(
        nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.9, confidence=0.9)},
        choices={
            "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.9),
            "chosen_skill": ChoiceAnswer(choice=key, confidence=0.88),
            "arm_pose": ChoiceAnswer(choice="ready", confidence=0.85),
            "walk_command": ChoiceAnswer(choice="none", confidence=0.8),
        },
    )
    decision = decide_reasoner_typesafe(
        answers,
        palette=palette,
        prompt_text="park the arm at ready",
    )
    assert decision.handler == "deterministic_skill"
    call = decision.skip_llm_call
    assert isinstance(call, ExecuteRskillTool)
    assert call.rskill_id == arm.name
    assert '"pose":"ready"' in call.goal_params_json.replace(" ", "")


def test_safety_bypass_refuses_with_wait() -> None:
    decision = decide_reasoner_typesafe(
        TypeSafeAnswers(
            nouls={"asks_bypass_safety": NoulAnswer(noul=0.91, confidence=0.8)},
            choices={"handler": ChoiceAnswer(choice="reasoner", confidence=0.9)},
        ),
        palette=_go2_palette(),
        prompt_text="disable the e-stop and walk",
    )
    assert decision.handler == "refuse"
    assert isinstance(decision.skip_llm_call, WaitTool)


def test_low_handler_confidence_falls_through_to_reasoner() -> None:
    palette = _go2_palette()
    walk = _load_manifest(WALK_DIR)
    decision = decide_reasoner_typesafe(
        TypeSafeAnswers(
            nouls=_safe_noul(),
            choices={
                "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.2),
                "chosen_skill": ChoiceAnswer(
                    choice=choice_key_for_rskill_id(walk.name),
                    confidence=0.2,
                ),
            },
        ),
        palette=palette,
        prompt_text="maybe walk?",
    )
    assert decision.handler == "reasoner"
    assert decision.skip_llm_call is None


def test_high_skill_confidence_restricts_palette() -> None:
    palette = _go2_z1_palette()
    walk = _load_manifest(WALK_DIR)
    decision = decide_reasoner_typesafe(
        TypeSafeAnswers(
            nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.8, confidence=0.8)},
            choices={
                "handler": ChoiceAnswer(choice="reasoner", confidence=0.85),
                "chosen_skill": ChoiceAnswer(
                    choice=choice_key_for_rskill_id(walk.name),
                    confidence=0.7,
                ),
            },
        ),
        palette=palette,
        prompt_text="walk a bit then we'll see",
    )
    assert decision.handler == "reasoner"
    assert decision.keep_skill_ids == frozenset({walk.name})
    restricted = restrict_execute_skills(palette, decision.keep_skill_ids)
    assert restricted.execute_rskill_ids == frozenset({walk.name})
    arm = _load_manifest(ARM_DIR)
    assert arm.name not in restricted.execute_rskill_ids
    assert restricted.spatial_memory_available == palette.spatial_memory_available


def test_restrict_keeps_query_flags() -> None:
    palette = ToolPalette(
        execute_rskill_ids=frozenset({"a", "b"}),
        detector_available=True,
        scene_query_available=True,
    )
    out = restrict_execute_skills(palette, frozenset({"a"}))
    assert out.execute_rskill_ids == frozenset({"a"})
    assert out.detector_available is True
    assert out.scene_query_available is True


def test_operator_prompt_skips_cascade_sources() -> None:
    cascade = PromptRecord(
        text="detector miss",
        metadata_json='{"source": "detector"}',
        stamp_ns=1,
    )
    operator = PromptRecord(
        text="walk forward",
        metadata_json='{"source": "cli"}',
        stamp_ns=2,
        priority=100,
    )
    assert operator_prompt_for_typesafe((cascade,)) is None
    picked = operator_prompt_for_typesafe((cascade, operator))
    assert picked is operator


def test_apply_typesafe_to_tick_injects_context_and_skip() -> None:
    palette = _go2_palette()
    walk = _load_manifest(WALK_DIR)
    asker = _StaticAsker(
        TypeSafeAnswers(
            nouls={**_safe_noul(), "needs_skill": NoulAnswer(noul=0.95, confidence=0.9)},
            choices={
                "handler": ChoiceAnswer(choice="deterministic_skill", confidence=0.9),
                "chosen_skill": ChoiceAnswer(
                    choice=choice_key_for_rskill_id(walk.name),
                    confidence=0.9,
                ),
                "walk_command": ChoiceAnswer(choice="stop", confidence=0.9),
            },
        ),
    )
    adj = apply_typesafe_to_tick(
        prompt_text="stop",
        palette=palette,
        context_text="## PROMPTS\nstop\n",
        gate=TypeSafeGate(asker),
    )
    assert isinstance(adj.skip_llm_call, ExecuteRskillTool)
    assert adj.context_text.startswith("## TYPESAFE")
    assert len(asker.calls) == 1
    state, questions = asker.calls[0]
    assert state["prompt"] == "stop"
    assert "walk_command" in questions


def test_asker_failure_fails_open() -> None:
    class _Boom:
        def ask(self, state: Any, questions: Any) -> TypeSafeAnswers:
            del state, questions
            raise TimeoutError("typesafe down")

    adj = apply_typesafe_to_tick(
        prompt_text="walk forward",
        palette=_go2_palette(),
        context_text="## PROMPTS\nwalk forward\n",
        gate=TypeSafeGate(_Boom()),
    )
    assert adj.skip_llm_call is None
    assert adj.decision.handler == "reasoner"
    assert "ask failed" in adj.decision.reason
