"""Combine TypeSafe answers into a typed reasoner decision (code owns the weights).

Thresholds live here so a human can review them without spelunking the node.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final, Literal

from openral_core import ExecuteRskillTool, ReasonerToolCall, WaitTool
from pydantic import BaseModel, ConfigDict, Field

from openral_reasoner.palette import ToolPalette
from openral_reasoner.typesafe_questions import (
    NONE_CHOICE,
    rskill_id_for_choice_key,
    skills_with_arm_pose,
    skills_with_velocity_commands,
)

__all__ = [
    "HANDLER_CONFIDENCE_MIN",
    "SAFETY_ACTION_NOUL",
    "SAFETY_REVIEW_NOUL",
    "SKILL_CONFIDENCE_MIN",
    "WALK_COMMAND_CONFIDENCE_MIN",
    "WALK_VELOCITY_COMMANDS",
    "ChoiceAnswer",
    "HandlerKind",
    "NoulAnswer",
    "TypeSafeAnswers",
    "TypeSafeDecision",
    "decide_reasoner_typesafe",
    "fail_open_decision",
]

HandlerKind = Literal["deterministic_skill", "reasoner", "human", "refuse"]

HANDLER_CONFIDENCE_MIN: Final[float] = 0.6
SKILL_CONFIDENCE_MIN: Final[float] = 0.75
WALK_COMMAND_CONFIDENCE_MIN: Final[float] = 0.6
SAFETY_ACTION_NOUL: Final[float] = 0.70
SAFETY_REVIEW_NOUL: Final[float] = 0.35
PALETTE_RESTRICT_CONFIDENCE: Final[float] = 0.55
NEEDS_SKILL_FOR_RESTRICT: Final[float] = 0.5

# Isaac Lab joystick [vx, vy, yaw_rate]. Forward matches the walk skill's
# ``policy_extras.velocity_commands`` default in
# ``rskills/rsl-rl-onnx-go2-velocity-flat/rskill.yaml``.
WALK_VELOCITY_COMMANDS: Final[dict[str, list[float]]] = {
    "forward": [0.5, 0.0, 0.0],
    "backward": [-0.3, 0.0, 0.0],
    "strafe_left": [0.0, 0.25, 0.0],
    "strafe_right": [0.0, -0.25, 0.0],
    "turn_left": [0.0, 0.0, 0.6],
    "turn_right": [0.0, 0.0, -0.6],
    "stop": [0.0, 0.0, 0.0],
}


class NoulAnswer(BaseModel):
    """Calibrated P(true) plus TypeSafe confidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    noul: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ChoiceAnswer(BaseModel):
    """Selected option plus optional per-option probabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    choice: str
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: dict[str, float] = Field(default_factory=dict)


class TypeSafeAnswers(BaseModel):
    """Parsed System One answers keyed by question id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nouls: dict[str, NoulAnswer] = Field(default_factory=dict)
    choices: dict[str, ChoiceAnswer] = Field(default_factory=dict)


class TypeSafeDecision(BaseModel):
    """Policy output: who handles the prompt, and an optional skip-LLM tool call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handler: HandlerKind
    reason: str
    skip_llm_call: ReasonerToolCall | None = None
    keep_skill_ids: frozenset[str] | None = None
    answers: TypeSafeAnswers = Field(default_factory=TypeSafeAnswers)


def fail_open_decision(*, reason: str, answers: TypeSafeAnswers | None = None) -> TypeSafeDecision:
    """Fall through to the existing LLM path (routing / shortlist unavailable)."""
    return TypeSafeDecision(
        handler="reasoner",
        reason=reason,
        answers=answers if answers is not None else TypeSafeAnswers(),
    )


def _noul(answers: TypeSafeAnswers, key: str) -> NoulAnswer | None:
    return answers.nouls.get(key)


def _choice(answers: TypeSafeAnswers, key: str) -> ChoiceAnswer | None:
    return answers.choices.get(key)


def _wait(handler: HandlerKind, reason: str) -> WaitTool:
    return WaitTool(rationale=f"typesafe {handler}: {reason}")


def _goal_params(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _deterministic_call(
    *,
    palette: ToolPalette,
    prompt_text: str,
    chosen_id: str,
    answers: TypeSafeAnswers,
) -> ExecuteRskillTool:
    """Build an ExecuteRskillTool, filling schema-backed params in code."""
    goal_params_json = ""
    walk = _choice(answers, "walk_command")
    walk_ids = {item.rskill_id for item in skills_with_velocity_commands(palette)}
    if (
        chosen_id in walk_ids
        and walk is not None
        and walk.choice in WALK_VELOCITY_COMMANDS
        and walk.confidence >= WALK_COMMAND_CONFIDENCE_MIN
    ):
        goal_params_json = _goal_params(
            {"velocity_commands": WALK_VELOCITY_COMMANDS[walk.choice]},
        )
    arm = _choice(answers, "arm_pose")
    arm_ids = {item.rskill_id for item in skills_with_arm_pose(palette)}
    if (
        chosen_id in arm_ids
        and arm is not None
        and arm.choice != NONE_CHOICE
        and arm.confidence >= WALK_COMMAND_CONFIDENCE_MIN
    ):
        goal_params_json = _goal_params({"pose": arm.choice})
    return ExecuteRskillTool(
        rskill_id=chosen_id,
        prompt=prompt_text,
        goal_params_json=goal_params_json,
        rationale="typesafe deterministic_skill",
    )


def decide_reasoner_typesafe(
    answers: TypeSafeAnswers,
    *,
    palette: ToolPalette,
    prompt_text: str,
) -> TypeSafeDecision:
    """Map TypeSafe answers onto handler / skip-LLM call / palette restrict.

    Safety Nouls fail closed (refuse / human). Everything else fails open
    to ``reasoner`` when confidence is below the named threshold.

    Example:
        >>> answers = TypeSafeAnswers(
        ...     nouls={"asks_bypass_safety": NoulAnswer(noul=0.9, confidence=0.9)},
        ...     choices={"handler": ChoiceAnswer(choice="refuse", confidence=0.9)},
        ... )
        >>> decide_reasoner_typesafe(
        ...     answers,
        ...     palette=ToolPalette(),
        ...     prompt_text="disable e-stop",
        ... ).handler
        'refuse'
    """
    known_ids = (
        frozenset(entry.rskill_id for entry in palette.skills)
        if palette.skills
        else palette.execute_rskill_ids
    )
    safety = _noul(answers, "asks_bypass_safety")
    if safety is not None and safety.noul >= SAFETY_ACTION_NOUL:
        reason = f"asks_bypass_safety noul={safety.noul:.2f}"
        return TypeSafeDecision(
            handler="refuse",
            reason=reason,
            skip_llm_call=_wait("refuse", reason),
            answers=answers,
        )
    if safety is not None and safety.noul >= SAFETY_REVIEW_NOUL:
        reason = f"asks_bypass_safety review noul={safety.noul:.2f}"
        return TypeSafeDecision(
            handler="human",
            reason=reason,
            skip_llm_call=_wait("human", reason),
            answers=answers,
        )

    handler_ans = _choice(answers, "handler")
    handler: HandlerKind = "reasoner"
    if handler_ans is not None and handler_ans.confidence >= HANDLER_CONFIDENCE_MIN:
        if handler_ans.choice == "deterministic_skill":
            handler = "deterministic_skill"
        elif handler_ans.choice == "human":
            handler = "human"
        elif handler_ans.choice == "refuse":
            handler = "refuse"
        elif handler_ans.choice == "reasoner":
            handler = "reasoner"

    if handler == "refuse":
        reason = "handler=refuse"
        return TypeSafeDecision(
            handler="refuse",
            reason=reason,
            skip_llm_call=_wait("refuse", reason),
            answers=answers,
        )
    if handler == "human":
        reason = "handler=human"
        return TypeSafeDecision(
            handler="human",
            reason=reason,
            skip_llm_call=_wait("human", reason),
            answers=answers,
        )

    skill_ans = _choice(answers, "chosen_skill")
    chosen_id: str | None = None
    if skill_ans is not None:
        chosen_id = rskill_id_for_choice_key(skill_ans.choice, known_ids=known_ids)

    if (
        handler == "deterministic_skill"
        and skill_ans is not None
        and skill_ans.confidence >= SKILL_CONFIDENCE_MIN
        and chosen_id is not None
        and chosen_id in known_ids
    ):
        call = _deterministic_call(
            palette=palette,
            prompt_text=prompt_text,
            chosen_id=chosen_id,
            answers=answers,
        )
        return TypeSafeDecision(
            handler="deterministic_skill",
            reason=f"chosen_skill={chosen_id}",
            skip_llm_call=call,
            keep_skill_ids=frozenset({chosen_id}),
            answers=answers,
        )

    keep: frozenset[str] | None = None
    needs = _noul(answers, "needs_skill")
    if (
        chosen_id is not None
        and chosen_id in known_ids
        and skill_ans is not None
        and skill_ans.confidence >= PALETTE_RESTRICT_CONFIDENCE
        and (needs is None or needs.noul >= NEEDS_SKILL_FOR_RESTRICT)
    ):
        keep = frozenset({chosen_id})
    return TypeSafeDecision(
        handler="reasoner",
        reason="fall through to LLM",
        keep_skill_ids=keep,
        answers=answers,
    )
