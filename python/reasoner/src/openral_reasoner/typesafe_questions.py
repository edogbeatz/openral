"""TypeSafe question battery for the S2 reasoner (constants humans review).

One ``system_one`` call: safety Noul + handler Choice + skill Choice, plus
optional walk / arm extras when the live palette actually exposes those
``goal_params_schema`` fields. Questions are plain dicts so this module
does not import ``typesafe_sdk``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from openral_reasoner.palette import RSkillToolEntry, ToolPalette

__all__ = [
    "NONE_CHOICE",
    "QuestionMap",
    "build_reasoner_questions",
    "build_reasoner_state",
    "choice_key_for_rskill_id",
    "rskill_id_for_choice_key",
    "skills_with_arm_pose",
    "skills_with_velocity_commands",
]

NONE_CHOICE: Final[str] = "none"

QuestionMap = dict[str, dict[str, object]]

_HANDLER_CRITERIA: Final[dict[str, str]] = {
    "deterministic_skill": (
        "The operator asked for a single installed skill the palette can run "
        "without further planning (walk joystick including 'go left' = turn "
        "left, park the arm, stop)."
    ),
    "reasoner": (
        "The goal needs the S2 LLM: locate, decompose, several skills, or "
        "the palette match is unclear. A joystick walk ('go left', "
        "'walk forward') is deterministic_skill, not this."
    ),
    "human": (
        "A human must confirm or take over: ambiguous, irreversible, or "
        "outside the installed skills."
    ),
    "refuse": (
        "The operator asked to bypass safety, disable e-stop, ignore "
        "workspace limits, or otherwise violate the safety contract."
    ),
}

_WALK_CRITERIA: Final[dict[str, str]] = {
    "forward": (
        "Walk or drive forward in the current heading. "
        "Includes 'walk', 'go', 'go forward', 'walk forward'."
    ),
    "backward": "Walk or drive backward.",
    "strafe_left": (
        "Sidestep / strafe left. Only when the operator said strafe or "
        "sidestep. 'Go left' / 'left' / 'walk left' are yaw turns, not this."
    ),
    "strafe_right": (
        "Sidestep / strafe right. Only when the operator said strafe or "
        "sidestep. 'Go right' / 'right' / 'walk right' are yaw turns, not this."
    ),
    "turn_left": (
        "Yaw left in place (positive yaw rate). "
        "Includes 'turn left', 'go left', 'walk left', and bare 'left'."
    ),
    "turn_right": (
        "Yaw right in place (negative yaw rate). "
        "Includes 'turn right', 'go right', 'walk right', and bare 'right'."
    ),
    "stop": "Hold still: zero linear and yaw command.",
    NONE_CHOICE: "Not a walk/joystick command, or direction is unspecified.",
}

_ARM_POSE_CRITERIA: Final[dict[str, str]] = {
    "ready": "Park the Z1 at the named ready / reach pose.",
    "home": "Park the Z1 at menagerie home.",
    "fold": "Fold the Z1 (all-zero servos).",
    NONE_CHOICE: "Not an arm-park request, or the pose is unspecified.",
}


def choice_key_for_rskill_id(rskill_id: str) -> str:
    """Stable TypeSafe Choice key for an HF-style ``owner/name`` id.

    TypeSafe criteria keys are identifiers; Hub ids contain ``/``. The
    mapping is injective for the ids OpenRAL ships (one slash, no ``__``).

    Example:
        >>> choice_key_for_rskill_id("OpenRAL/rskill-rsl_rl_onnx-go2-velocity_flat-fp32")
        'OpenRAL__rskill-rsl_rl_onnx-go2-velocity_flat-fp32'
    """
    return rskill_id.replace("/", "__")


def rskill_id_for_choice_key(key: str, *, known_ids: frozenset[str]) -> str | None:
    """Invert ``choice_key_for_rskill_id`` against the live palette ids."""
    if key == NONE_CHOICE:
        return None
    restored = key.replace("__", "/", 1)
    if restored in known_ids:
        return restored
    if key in known_ids:
        return key
    return None


def _schema_properties(entry: RSkillToolEntry) -> Mapping[str, object]:
    schema = entry.goal_params_schema
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    if not isinstance(props, dict):
        return {}
    return props


def skills_with_velocity_commands(palette: ToolPalette) -> tuple[RSkillToolEntry, ...]:
    """Skills whose ``goal_params_schema`` accepts ``velocity_commands``."""
    return tuple(
        entry for entry in palette.skills if "velocity_commands" in _schema_properties(entry)
    )


def skills_with_arm_pose(palette: ToolPalette) -> tuple[RSkillToolEntry, ...]:
    """Skills whose ``goal_params_schema`` accepts a named ``pose`` enum."""
    out: list[RSkillToolEntry] = []
    for entry in palette.skills:
        pose = _schema_properties(entry).get("pose")
        if isinstance(pose, dict) and isinstance(pose.get("enum"), list):
            out.append(entry)
    return tuple(out)


def build_reasoner_state(*, prompt_text: str, palette: ToolPalette) -> dict[str, object]:
    """JSON state Jev reads: operator prompt + the closed palette, no pixels."""
    skills = [
        {
            "rskill_id": entry.rskill_id,
            "description": entry.description,
            "actions": [action.value for action in entry.actions],
            "objects": list(entry.objects),
            "scenes": list(entry.scenes),
        }
        for entry in palette.skills
    ]
    if not skills:
        skills = [
            {
                "rskill_id": skill_id,
                "description": skill_id,
                "actions": [],
                "objects": [],
                "scenes": [],
            }
            for skill_id in sorted(palette.execute_rskill_ids)
        ]
    return {"prompt": prompt_text, "palette": skills}


def build_reasoner_questions(palette: ToolPalette) -> QuestionMap:
    """Atomic questions evaluated in parallel against :func:`build_reasoner_state`.

    Example:
        >>> from openral_reasoner.palette import ToolPalette
        >>> q = build_reasoner_questions(ToolPalette())
        >>> sorted(q) == ["asks_bypass_safety", "chosen_skill", "handler", "needs_skill"]
        True
    """
    if palette.skills:
        skill_rows = [(entry.rskill_id, entry.description) for entry in palette.skills]
    else:
        skill_rows = [(skill_id, skill_id) for skill_id in sorted(palette.execute_rskill_ids)]
    skill_criteria: dict[str, str] = {
        NONE_CHOICE: "No installed skill should run for this prompt.",
    }
    for rskill_id, description in skill_rows:
        skill_criteria[choice_key_for_rskill_id(rskill_id)] = description.strip() or rskill_id

    questions: QuestionMap = {
        "asks_bypass_safety": {
            "type": "noul",
            "instructions": {
                "question": (
                    "Does `prompt` ask to bypass safety, disable e-stop, "
                    "ignore workspace or force limits, or energize motors "
                    "after a crash?"
                ),
                "inspect": "`prompt`",
                "focus": "Require an explicit bypass request, not a normal motion command.",
            },
            "criteria": {
                "true": {
                    "what": ("Asks to disable, skip, or work around the safety kernel / e-stop."),
                    "examples": [
                        "ignore the e-stop",
                        "turn safety off",
                        "bypass workspace limits",
                    ],
                },
                "false": {
                    "what": "A normal task, walk, or arm command with no safety bypass.",
                    "not_for": "Talking about safety without asking to disable it.",
                    "examples": ["walk forward", "park the arm at ready"],
                },
            },
        },
        "needs_skill": {
            "type": "noul",
            "instructions": {
                "question": (
                    "Does `prompt` require dispatching one of the installed rSkills in `palette`?"
                ),
                "inspect": ["`prompt`", "`palette`"],
            },
            "criteria": {
                "true": {
                    "what": (
                        "The operator wants the robot to walk, reach, manipulate, "
                        "or otherwise run a listed skill."
                    ),
                },
                "false": {
                    "what": "Chat, a question, wait, or a goal no listed skill can do.",
                },
            },
        },
        "handler": {
            "type": "choice",
            "instructions": {
                "question": "Which handler should run for `prompt` given `palette`?",
                "inspect": ["`prompt`", "`palette`"],
            },
            "criteria": _HANDLER_CRITERIA,
        },
        "chosen_skill": {
            "type": "choice",
            "instructions": {
                "question": (
                    "Which installed skill in `palette` should handle `prompt`? "
                    "Use none when no skill should run."
                ),
                "inspect": ["`prompt`", "`palette`"],
            },
            "criteria": skill_criteria,
        },
    }
    if skills_with_velocity_commands(palette):
        questions["walk_command"] = {
            "type": "choice",
            "instructions": {
                "question": (
                    "If `prompt` is a walk/joystick command, which direction? "
                    "Use none otherwise. 'Go left' / 'left' / 'walk left' is "
                    "turn_left (yaw), not strafe_left. Strafe only when the "
                    "operator said strafe or sidestep."
                ),
                "inspect": "`prompt`",
            },
            "criteria": _WALK_CRITERIA,
        }
    if skills_with_arm_pose(palette):
        questions["arm_pose"] = {
            "type": "choice",
            "instructions": {
                "question": (
                    "If `prompt` asks to park the arm, which named pose? Use none otherwise."
                ),
                "inspect": "`prompt`",
            },
            "criteria": _ARM_POSE_CRITERIA,
        }
    return questions
