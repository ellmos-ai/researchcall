from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safety import reject_high_stakes_content


CONSENT_VALUES = {"granted", "declined", "not_obtained"}


def _task_label(value: str) -> str:
    return "`" + value.replace("`", "\\`") + "`"


def load_questionnaire_file(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Questionnaire must be a JSON object")
    validate_questionnaire(value)
    return value


def validate_questionnaire(questionnaire: dict[str, Any]) -> None:
    for field in ("title", "language", "consent_text", "questions"):
        if field not in questionnaire:
            raise ValueError(f"Questionnaire is missing required field: {field}")
    if not isinstance(questionnaire["questions"], list) or not questionnaire["questions"]:
        raise ValueError("Questionnaire questions must be a non-empty list")

    seen: set[str] = set()
    for question in questionnaire["questions"]:
        if not isinstance(question, dict):
            raise ValueError("Every question must be an object")
        question_id = question.get("id")
        wording = question.get("wording")
        categories = question.get("categories")
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("Every question needs a non-empty id")
        if question_id in seen:
            raise ValueError(f"Duplicate question id: {question_id}")
        seen.add(question_id)
        if not isinstance(wording, str) or not wording.strip():
            raise ValueError(f"Question {question_id} needs fixed wording")
        if not isinstance(categories, list) or not categories:
            raise ValueError(f"Question {question_id} needs fixed answer categories")
        if len(set(categories)) != len(categories) or not all(
            isinstance(item, str) and item for item in categories
        ):
            raise ValueError(f"Question {question_id} has invalid answer categories")
        condition = question.get("ask_if")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"question", "equals"}:
                raise ValueError(f"Question {question_id} has an invalid ask_if condition")
            if condition["question"] not in seen:
                raise ValueError(f"Question {question_id} filters on a later or unknown question")
        for follow_up in question.get("follow_ups", []):
            if not isinstance(follow_up, dict) or set(follow_up) != {"when", "wording"}:
                raise ValueError(f"Question {question_id} has an invalid follow-up")
            if follow_up["when"] not in categories:
                raise ValueError(f"Question {question_id} follow-up uses an unknown category")
            if not isinstance(follow_up["wording"], str) or not follow_up["wording"].strip():
                raise ValueError(f"Question {question_id} follow-up wording is empty")
    reject_high_stakes_content(questionnaire)


def result_schema(questionnaire: dict[str, Any]) -> dict[str, Any]:
    answer_properties: dict[str, Any] = {}
    raw_answer_properties: dict[str, Any] = {}
    wording_properties: dict[str, Any] = {}
    question_ids: list[str] = []
    for question in questionnaire["questions"]:
        question_id = question["id"]
        question_ids.append(question_id)
        answer_properties[question_id] = {
            "type": ["string", "null"],
            "enum": [*question["categories"], None],
        }
        raw_answer_properties[question_id] = {"type": ["string", "null"]}
        wording_properties[question_id] = {"type": ["string", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "consent",
            "withdrawal_requested",
            "asked_verbatim",
            "spoken_consent_wording",
            "spoken_wording",
            "answers",
            "raw_answers",
        ],
        "properties": {
            "consent": {"type": "string", "enum": sorted(CONSENT_VALUES)},
            "withdrawal_requested": {"type": "boolean"},
            "asked_verbatim": {"type": "boolean"},
            "spoken_consent_wording": {"type": ["string", "null"]},
            "spoken_wording": {
                "type": "object",
                "additionalProperties": False,
                "required": question_ids,
                "properties": wording_properties,
            },
            "answers": {
                "type": "object",
                "additionalProperties": False,
                "required": question_ids,
                "properties": answer_properties,
            },
            "raw_answers": {
                "type": "object",
                "additionalProperties": False,
                "required": question_ids,
                "properties": raw_answer_properties,
            },
        },
    }


def build_task(questionnaire: dict[str, Any]) -> str:
    lines = [
        "Conduct one standardized scientific telephone interview.",
        "STRICT STANDARDIZATION: Say every quoted sentence exactly as written. Do not paraphrase, summarize, embellish, or add spontaneous probes.",
        "Ask for consent first. If consent is not granted, thank the person and end the interview without asking survey questions.",
        f'CONSENT (say exactly): "{questionnaire["consent_text"]}"',
        "QUESTIONNAIRE:",
    ]
    for question in questionnaire["questions"]:
        prefix = question["id"]
        condition = question.get("ask_if")
        if condition:
            lines.append(
                f'- {prefix} FILTER: Ask only if {condition["question"]} equals category {_task_label(str(condition["equals"]))}.'
            )
        lines.append(f'- {prefix} (say exactly): "{question["wording"]}"')
        lines.append(
            "  Allowed answer categories (interpretation labels; do not read aloud): "
            + ", ".join(_task_label(category) for category in question["categories"])
            + "."
        )
        for follow_up in question.get("follow_ups", []):
            lines.append(
                f'  If the interpreted answer is category {_task_label(str(follow_up["when"]))}, say exactly: "{follow_up["wording"]}"'
            )
    lines.extend(
        [
            "Do not request names, addresses, background history, or any data not required by this questionnaire.",
            "If the person withdraws consent, stop immediately and set withdrawal_requested=true.",
            "For every question, return the actual words spoken in spoken_wording; use null when it was not asked.",
            "For every question, preserve the participant's raw words in raw_answers before interpreting them into answers; do not correct or paraphrase the raw words, and use null only when no answer was given.",
            "Set asked_verbatim=true only if every spoken consent/question sentence exactly matched the required wording.",
        ]
    )
    return "\n".join(lines)


def validate_structured_result(
    questionnaire: dict[str, Any], result: dict[str, Any]
) -> None:
    required = {
        "consent",
        "withdrawal_requested",
        "asked_verbatim",
        "spoken_consent_wording",
        "spoken_wording",
        "answers",
        "raw_answers",
    }
    if set(result) != required:
        raise ValueError("Structured result fields do not match the recipient schema")
    if result["consent"] not in CONSENT_VALUES:
        raise ValueError("Structured result has an invalid consent value")
    if not isinstance(result["withdrawal_requested"], bool):
        raise ValueError("withdrawal_requested must be boolean")
    if not isinstance(result["asked_verbatim"], bool):
        raise ValueError("asked_verbatim must be boolean")
    if result["spoken_consent_wording"] is not None and not isinstance(
        result["spoken_consent_wording"], str
    ):
        raise ValueError("spoken_consent_wording must be a string or null")
    if not all(
        isinstance(result[field], dict)
        for field in ("spoken_wording", "answers", "raw_answers")
    ):
        raise ValueError("spoken_wording, answers, and raw_answers must be objects")

    expected_ids = {question["id"] for question in questionnaire["questions"]}
    if any(
        set(result[field]) != expected_ids
        for field in ("spoken_wording", "answers", "raw_answers")
    ):
        raise ValueError("Structured result question ids do not match the questionnaire")
    for question in questionnaire["questions"]:
        question_id = question["id"]
        wording = result["spoken_wording"][question_id]
        answer = result["answers"][question_id]
        raw_answer = result["raw_answers"][question_id]
        if wording is not None and not isinstance(wording, str):
            raise ValueError(f"Spoken wording for {question_id} must be a string or null")
        if answer is not None and answer not in question["categories"]:
            raise ValueError(f"Answer for {question_id} is outside its fixed categories")
        if raw_answer is not None and not isinstance(raw_answer, str):
            raise ValueError(f"Raw answer for {question_id} must be a string or null")
        if answer is not None and (not isinstance(raw_answer, str) or not raw_answer.strip()):
            raise ValueError(f"Categorized answer for {question_id} needs a raw answer")


def wording_matches(questionnaire: dict[str, Any], result: dict[str, Any]) -> bool:
    observed = result["consent"] != "not_obtained"
    if result["consent"] != "not_obtained":
        if result["spoken_consent_wording"] != questionnaire["consent_text"]:
            return False
    expected = {question["id"]: question["wording"] for question in questionnaire["questions"]}
    spoken = result["spoken_wording"]
    for question_id, actual in spoken.items():
        if actual is None:
            continue
        observed = True
        if actual != expected[question_id]:
            return False
    return observed
