"""Opt-in TypeSafe System One gate for the S2 reasoner.

Lazy-imports ``typesafe_sdk``. Off unless ``OPENRAL_TYPESAFE=1`` and
``TYPESAFE_API_KEY`` are set. Routing/shortlist failures fall through to
the LLM; a high ``asks_bypass_safety`` noul still fail-closes to wait.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Protocol

import structlog
from openral_core import ReasonerToolCall
from pydantic import BaseModel, ConfigDict

from openral_reasoner.context import PromptRecord
from openral_reasoner.node_policy import CASCADE_PROMPT_SOURCES
from openral_reasoner.palette import ToolPalette
from openral_reasoner.typesafe_policy import (
    ChoiceAnswer,
    NoulAnswer,
    TypeSafeAnswers,
    TypeSafeDecision,
    decide_reasoner_typesafe,
    fail_open_decision,
)
from openral_reasoner.typesafe_questions import (
    QuestionMap,
    build_reasoner_questions,
    build_reasoner_state,
)

__all__ = [
    "ENABLE_ENV",
    "TYPESAFE_API_KEY_ENV",
    "TypeSafeAsker",
    "TypeSafeGate",
    "TypesafeTickAdjustment",
    "answers_from_sdk_result",
    "apply_typesafe_to_tick",
    "build_typesafe_gate_from_env",
    "is_typesafe_enabled",
    "operator_prompt_for_typesafe",
    "restrict_execute_skills",
]

ENABLE_ENV = "OPENRAL_TYPESAFE"
TYPESAFE_API_KEY_ENV = "TYPESAFE_API_KEY"

log = structlog.get_logger(__name__)


class TypeSafeAsker(Protocol):
    """Network boundary: one System One call in, typed answers out."""

    def ask(
        self,
        state: Mapping[str, object],
        questions: QuestionMap,
    ) -> TypeSafeAnswers:
        """Evaluate ``questions`` against ``state``."""
        ...


class TypesafeTickAdjustment(BaseModel):
    """What the LLM worker should do after one TypeSafe assess."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skip_llm_call: ReasonerToolCall | None = None
    palette: ToolPalette
    context_text: str
    decision: TypeSafeDecision


def is_typesafe_enabled(env: Mapping[str, str] | None = None) -> bool:
    """True only when the explicit flag and API key are both set.

    Example:
        >>> is_typesafe_enabled({"OPENRAL_TYPESAFE": "1", "TYPESAFE_API_KEY": "k"})
        True
        >>> is_typesafe_enabled({"TYPESAFE_API_KEY": "k"})
        False
    """
    src = os.environ if env is None else env
    flag = src.get(ENABLE_ENV, "").strip() == "1"
    key = bool(src.get(TYPESAFE_API_KEY_ENV, "").strip())
    return flag and key


def operator_prompt_for_typesafe(
    prompts: tuple[PromptRecord, ...],
) -> PromptRecord | None:
    """First non-cascade prompt (buffer is already priority-ordered)."""
    for rec in prompts:
        source = _prompt_source(rec)
        if source not in CASCADE_PROMPT_SOURCES:
            return rec
    return None


def restrict_execute_skills(palette: ToolPalette, keep_ids: frozenset[str]) -> ToolPalette:
    """Copy ``palette`` keeping only the named ExecuteRskill skills.

    Query-tool flags are unchanged. Unknown ids are dropped.

    Example:
        >>> p = ToolPalette(execute_rskill_ids=frozenset({"a", "b"}))
        >>> restrict_execute_skills(p, frozenset({"a"})).execute_rskill_ids
        frozenset({'a'})
    """
    if palette.skills:
        skills = tuple(entry for entry in palette.skills if entry.rskill_id in keep_ids)
        return palette.model_copy(
            update={
                "skills": skills,
                "execute_rskill_ids": frozenset(entry.rskill_id for entry in skills),
            },
        )
    kept = palette.execute_rskill_ids & keep_ids
    return palette.model_copy(update={"execute_rskill_ids": kept})


def render_typesafe_block(decision: TypeSafeDecision) -> str:
    """Compact ``## TYPESAFE`` section injected above the LLM context."""
    lines = [
        "## TYPESAFE",
        f"handler: {decision.handler}",
        f"reason: {decision.reason}",
    ]
    if decision.keep_skill_ids:
        lines.append("keep_skills: " + ", ".join(sorted(decision.keep_skill_ids)))
    safety = decision.answers.nouls.get("asks_bypass_safety")
    if safety is not None:
        lines.append(
            f"asks_bypass_safety: noul={safety.noul:.2f} conf={safety.confidence:.2f}",
        )
    skill = decision.answers.choices.get("chosen_skill")
    if skill is not None:
        lines.append(f"chosen_skill: {skill.choice} conf={skill.confidence:.2f}")
    return "\n".join(lines)


class TypeSafeGate:
    """Assess an operator prompt against the live palette."""

    def __init__(self, asker: TypeSafeAsker) -> None:
        """Inject the System One client (SDK adapter or test double)."""
        self._asker = asker

    def assess(self, *, prompt_text: str, palette: ToolPalette) -> TypeSafeDecision:
        """One parallel System One call, then :func:`decide_reasoner_typesafe`."""
        state = build_reasoner_state(prompt_text=prompt_text, palette=palette)
        questions = build_reasoner_questions(palette)
        try:
            answers = self._asker.ask(state, questions)
        except Exception as exc:  # reason: SDK/network boundary; fail open to LLM
            log.warning("reasoner.typesafe.ask_failed", error=str(exc))
            return fail_open_decision(reason=f"typesafe ask failed: {exc}")
        decision = decide_reasoner_typesafe(
            answers,
            palette=palette,
            prompt_text=prompt_text,
        )
        log.info(
            "reasoner.typesafe.assessed",
            handler=decision.handler,
            skip_llm=decision.skip_llm_call is not None,
            reason=decision.reason,
        )
        return decision


class SdkTypeSafeAsker:
    """``typesafe_sdk.TypeSafeClient`` adapter (import-gated)."""

    def ask(
        self,
        state: Mapping[str, object],
        questions: QuestionMap,
    ) -> TypeSafeAnswers:
        # Optional extra; default env has no typesafe-sdk.
        from typesafe_sdk import TypeSafeClient  # noqa: PLC0415

        with TypeSafeClient(timeout=30.0) as client:
            result = client.system_one(state=dict(state), questions=questions)
        return answers_from_sdk_result(result)


def answers_from_sdk_result(result: object) -> TypeSafeAnswers:
    """Translate an SDK ``system_one`` result into :class:`TypeSafeAnswers`."""
    nouls_raw = getattr(result, "nouls", {}) or {}
    choices_raw = getattr(result, "choices", {}) or {}
    nouls = {str(key): _as_noul(value) for key, value in dict(nouls_raw).items()}
    choices = {str(key): _as_choice(value) for key, value in dict(choices_raw).items()}
    return TypeSafeAnswers(nouls=nouls, choices=choices)


def build_typesafe_gate_from_env(env: Mapping[str, str] | None = None) -> TypeSafeGate | None:
    """Construct a gate or ``None`` when the opt-in is off / SDK missing."""
    if not is_typesafe_enabled(env):
        return None
    try:
        import typesafe_sdk  # noqa: F401, PLC0415
    except ImportError:
        log.warning(
            "reasoner.typesafe.sdk_missing",
            hint="just sync --group typesafe",
        )
        return None
    return TypeSafeGate(SdkTypeSafeAsker())


def apply_typesafe_to_tick(
    *,
    prompt_text: str,
    palette: ToolPalette,
    context_text: str,
    gate: TypeSafeGate,
) -> TypesafeTickAdjustment:
    """Assess, optionally shrink the palette, inject ``## TYPESAFE`` context.

    Example:
        >>> from openral_reasoner.typesafe_policy import (
        ...     ChoiceAnswer,
        ...     NoulAnswer,
        ...     TypeSafeAnswers,
        ... )
        >>> class _Static:
        ...     def ask(self, state, questions):
        ...         return TypeSafeAnswers(
        ...             nouls={"asks_bypass_safety": NoulAnswer(noul=0.01, confidence=0.9)},
        ...             choices={
        ...                 "handler": ChoiceAnswer(choice="reasoner", confidence=0.9),
        ...                 "chosen_skill": ChoiceAnswer(choice="none", confidence=0.9),
        ...             },
        ...         )
        >>> adj = apply_typesafe_to_tick(
        ...     prompt_text="where is the cup?",
        ...     palette=ToolPalette(),
        ...     context_text="## PROMPTS",
        ...     gate=TypeSafeGate(_Static()),
        ... )
        >>> adj.skip_llm_call is None
        True
        >>> adj.context_text.startswith("## TYPESAFE")
        True
    """
    decision = gate.assess(prompt_text=prompt_text, palette=palette)
    new_palette = palette
    if decision.keep_skill_ids is not None:
        new_palette = restrict_execute_skills(palette, decision.keep_skill_ids)
    block = render_typesafe_block(decision)
    new_context = f"{block}\n\n{context_text}" if block else context_text
    return TypesafeTickAdjustment(
        skip_llm_call=decision.skip_llm_call,
        palette=new_palette,
        context_text=new_context,
        decision=decision,
    )


def _prompt_source(record: PromptRecord) -> str:
    if not record.metadata_json:
        return ""
    try:
        parsed = json.loads(record.metadata_json)
    except json.JSONDecodeError:
        return ""
    if isinstance(parsed, dict):
        return str(parsed.get("source") or "")
    return ""


def _float_attr(payload: object, name: str, default: float | None = None) -> float:
    value: object = getattr(payload, name) if default is None else getattr(payload, name, default)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TypeError(f"TypeSafe payload.{name} is not numeric")
    return float(value)


def _str_attr(payload: object, name: str) -> str:
    value: object = getattr(payload, name)
    if not isinstance(value, str):
        raise TypeError(f"TypeSafe payload.{name} is not a string")
    return value


def _as_noul(payload: object) -> NoulAnswer:
    if isinstance(payload, NoulAnswer):
        return payload
    if isinstance(payload, Mapping):
        return NoulAnswer(
            noul=float(payload["noul"]),
            confidence=float(payload.get("confidence", 1.0)),
        )
    return NoulAnswer(
        noul=_float_attr(payload, "noul"),
        confidence=_float_attr(payload, "confidence", 1.0),
    )


def _mapping_probs(raw: object) -> dict[str, float]:
    if isinstance(raw, Mapping):
        return {str(key): float(value) for key, value in raw.items()}
    return {}


def _as_choice(payload: object) -> ChoiceAnswer:
    if isinstance(payload, ChoiceAnswer):
        return payload
    if isinstance(payload, Mapping):
        return ChoiceAnswer(
            choice=str(payload["choice"]),
            confidence=float(payload.get("confidence", 1.0)),
            probabilities=_mapping_probs(payload.get("probabilities", {})),
        )
    return ChoiceAnswer(
        choice=_str_attr(payload, "choice"),
        confidence=_float_attr(payload, "confidence", 1.0),
        probabilities=_mapping_probs(getattr(payload, "probabilities", {})),
    )
