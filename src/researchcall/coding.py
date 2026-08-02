"""The analysis rules, applied where they are needed: at the incoming record.

Station 7 asks two questions before the field phase starts — what happens to an
answer that fits none of the categories, and where free comments live. Fixing
them beforehand is the whole point: a rule invented after the results are in is
not a rule, it is a preference.

The rules act here rather than in the report because an answer that is thrown
away at report time has already been counted somewhere else. Applying them at the
record keeps one truth, and the raw words are kept either way — that is a locked
setting, not a choice.
"""

from __future__ import annotations

from typing import Any

from .questionnaire import UNLISTED_CODE, is_open_question


DISCARD = "discard"
AS_OTHER = "as_other"
LET_MODEL_MAP = "let_model_map"

IN_DATASET = "in_dataset"
SEPARATE = "separate"


def unlisted_policy(questionnaire: dict[str, Any]) -> str:
    coding = questionnaire.get("coding") or {}
    return str(coding.get("unlisted_answers") or AS_OTHER)


def free_comment_policy(questionnaire: dict[str, Any]) -> str:
    coding = questionnaire.get("coding") or {}
    return str(coding.get("free_comments") or IN_DATASET)


def apply_unlisted_policy(
    questionnaire: dict[str, Any], result: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Handle answers outside the fixed categories, by the rule fixed in advance.

    Returns the result and one note per answer the rule touched, so the report can
    state how often it had to intervene instead of quietly presenting a clean
    dataset.
    """
    answers = result.get("answers")
    if not isinstance(answers, dict):
        return result, []

    policy = unlisted_policy(questionnaire)
    raw_answers = result.get("raw_answers") if isinstance(result.get("raw_answers"), dict) else {}
    notes: list[dict[str, str]] = []
    changed = dict(answers)

    for question in questionnaire.get("questions", []):
        question_id = question.get("id")
        if question_id not in changed or is_open_question(question):
            continue
        answer = changed[question_id]
        if answer is None or answer in question.get("categories", []):
            continue
        if policy == DISCARD:
            changed[question_id] = None
            outcome = DISCARD
        elif policy == LET_MODEL_MAP:
            # No model runs in a dry run, so the honest state is "not coded yet"
            # and visible, rather than a coding nobody performed.
            changed[question_id] = None
            outcome = LET_MODEL_MAP
        else:
            changed[question_id] = UNLISTED_CODE
            outcome = AS_OTHER
        notes.append(
            {
                "question": str(question_id),
                "returned": str(answer),
                "rule": outcome,
                "raw_kept": "yes" if isinstance(raw_answers.get(question_id), str) else "no",
            }
        )

    if not notes:
        return result, []
    adjusted = dict(result)
    adjusted["answers"] = changed
    return adjusted, notes


def open_question_ids(questionnaire: dict[str, Any]) -> list[str]:
    return [
        str(question["id"])
        for question in questionnaire.get("questions", [])
        if is_open_question(question)
    ]


def reversed_question_ids(questionnaire: dict[str, Any]) -> list[str]:
    return [
        str(question["id"])
        for question in questionnaire.get("questions", [])
        if (question.get("scale") or {}).get("reversed")
    ]


def reverse_scale_value(question: dict[str, Any], value: str | None) -> str | None:
    """Turn a reversed item's answer back around.

    A reversed item measures the same thing with the sign flipped; forgetting to
    turn it back measures the opposite. The dataset therefore carries both the
    answer as given and the recoded value.
    """
    scale = question.get("scale") or {}
    if not scale.get("reversed") or value is None:
        return value
    try:
        number = int(value)
    except (TypeError, ValueError):
        return value
    steps = int(scale.get("steps", 0) or 0)
    if steps < 2 or not 1 <= number <= steps:
        return value
    return str(steps + 1 - number)
