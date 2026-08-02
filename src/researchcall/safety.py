from __future__ import annotations

import hashlib
import re
from typing import Any


E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

# This deliberately narrow guard is a fail-closed backstop, not legal classification.
HIGH_STAKES_PATTERNS = {
    "medical": re.compile(
        r"\b(diagnos(?:e|is)|medical advice|treatment recommendation|prescri(?:be|ption)|"
        r"Diagnose|medizinische Beratung|Behandlungsempfehlung|verschreiben)\b",
        re.IGNORECASE,
    ),
    "legal": re.compile(
        r"\b(legal advice|act as (?:a )?lawyer|Rechtsberatung|als Anwalt)\b",
        re.IGNORECASE,
    ),
    "financial": re.compile(
        r"\b(investment advice|financial advice|buy or sell stock|Anlageberatung|"
        r"Finanzberatung|Aktien kaufen|Aktien verkaufen)\b",
        re.IGNORECASE,
    ),
    "emergency": re.compile(
        r"\b(emergency dispatch|suicide intervention|Notruf|akuter Notfall|"
        r"Suizidintervention)\b",
        re.IGNORECASE,
    ),
}


def validate_e164(phone: str) -> str:
    if not E164_RE.fullmatch(phone):
        raise ValueError("Phone number must be valid E.164 format")
    return phone


def mask_phone(phone: str) -> str:
    if not phone:
        return "[no phone]"
    visible = phone[-2:] if len(phone) >= 2 else "**"
    return f"+***{visible}"


def idempotency_key(study_key: str, sample_id: int, attempt_no: int = 1) -> str:
    """A stable key per attempt.

    The first attempt keeps the key it always had, so a state file written before
    repeated attempts existed stays consistent. A repeat is a different call and
    must be allowed through — the key therefore carries the attempt number, and
    only from the second one on.
    """
    seed = f"{study_key}:{sample_id}"
    if attempt_no > 1:
        seed = f"{seed}:{attempt_no}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"researchcall-{digest[:32]}"


def _questionnaire_text(questionnaire: dict[str, Any]) -> str:
    pieces: list[str] = [
        str(questionnaire.get("title", "")),
        str(questionnaire.get("consent_text", "")),
    ]
    for question in questionnaire.get("questions", []):
        if not isinstance(question, dict):
            continue
        pieces.append(str(question.get("wording", "")))
        for follow_up in question.get("follow_ups", []):
            if isinstance(follow_up, dict):
                pieces.append(str(follow_up.get("wording", "")))
    return "\n".join(pieces)


def reject_high_stakes_content(questionnaire: dict[str, Any]) -> None:
    text = _questionnaire_text(questionnaire)
    matches = [name for name, pattern in HIGH_STAKES_PATTERNS.items() if pattern.search(text)]
    if matches:
        raise ValueError(
            "Questionnaire enters unsupported high-stakes content: " + ", ".join(matches)
        )

