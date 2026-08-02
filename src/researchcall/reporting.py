from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from typing import Any

from .database import load_questionnaire
from .questionnaire import UNLISTED_CODE, is_open_question


LOSS_STATUSES = (
    "NO_ANSWER",
    "DECLINED",
    "BUSY",
    "VOICEMAIL",
    "FAILED",
    "CANCELED",
    "CANCELLED",
    "EXPIRED",
    "INTERRUPTED",
)


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{100 * numerator / denominator:.1f}%"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]


def _detail(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def collect(connection: sqlite3.Connection, study: sqlite3.Row) -> dict[str, Any]:
    """Everything the report and the interface both need, read once.

    Attempts are rows of their own, so a record with two calls appears twice
    here. The two views are kept apart on purpose: a *yield* is counted per
    person, an *outcome structure* per call. Mixing them is how a survey ends up
    claiming a completion rate above one hundred percent.
    """
    samples = connection.execute(
        """
        SELECT id, time_window, COALESCE(assigned_window, time_window) AS assigned_window,
               excluded_at
        FROM sample WHERE study_id = ? ORDER BY id
        """,
        (study["id"],),
    ).fetchall()
    included_ids = {int(row["id"]) for row in samples if row["excluded_at"] is None}

    attempts = connection.execute(
        """
        SELECT a.sample_id, a.attempt_no,
               COALESCE(a.time_window, s.time_window) AS time_window,
               a.call_status, a.detail_json
        FROM attempt a JOIN sample s ON s.id = a.sample_id
        WHERE s.study_id = ?
        ORDER BY a.sample_id, a.attempt_no
        """,
        (study["id"],),
    ).fetchall()
    responses = connection.execute(
        """
        SELECT r.sample_id, r.structured_json, r.consent,
               r.asked_verbatim_reported, r.wording_matches
        FROM response r JOIN sample s ON s.id = r.sample_id
        WHERE s.study_id = ?
        """,
        (study["id"],),
    ).fetchall()

    by_sample: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in attempts:
        if int(row["sample_id"]) in included_ids:
            by_sample[int(row["sample_id"])].append(row)

    assigned = {int(row["id"]): str(row["assigned_window"]) for row in samples}
    final_status = {
        sample_id: str(rows[-1]["call_status"]) for sample_id, rows in by_sample.items()
    }
    return {
        "samples": samples,
        "included_ids": included_ids,
        "assigned": assigned,
        "attempts": [row for row in attempts if int(row["sample_id"]) in included_ids],
        "by_sample": by_sample,
        "final_status": final_status,
        "responses": [row for row in responses if int(row["sample_id"]) in included_ids],
    }


def build_report(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    questionnaire = load_questionnaire(study)
    data = collect(connection, study)

    samples = data["samples"]
    included_ids = data["included_ids"]
    excluded_count = len(samples) - len(included_ids)
    windows = sorted({data["assigned"][sample_id] for sample_id in included_ids})
    final_status: dict[int, str] = data["final_status"]
    status_counts = Counter(final_status.values())
    completed = status_counts["COMPLETED"]
    reached = len(final_status)
    attempt_rows = data["attempts"]
    repeated = sum(1 for rows in data["by_sample"].values() if len(rows) > 1)
    moved = sum(
        1
        for row in attempt_rows
        if str(row["time_window"]) != data["assigned"][int(row["sample_id"])]
    )

    rules = questionnaire.get("run_rules") or {}
    allowed = 1 + int(rules.get("attempts_per_person", 0) or 0)

    lines = [
        f"# ResearchCall report: {study['title']}",
        "",
        "## Fieldwork summary",
        "",
        f"- Drawn records: {len(samples)}",
        f"- Included records: {len(included_ids)}",
        f"- Privacy withdrawals excluded from analysis: {excluded_count}",
        f"- Records with at least one attempt: {reached}",
        f"- Attempts recorded: {len(attempt_rows)}",
        f"- Completed interviews: {completed}",
        f"- Completion yield (completed / included drawn): {_percent(completed, len(included_ids))}",
        "",
        "## Repeated contact",
        "",
        f"- Attempts allowed per person: {allowed}"
        + (" (configured)" if rules else " (default: one call per person)"),
        f"- Records dialled more than once: {repeated}",
        f"- Attempts made in a time window other than the assigned one: {moved}",
        f"- Callbacks allowed after a refusal: {int(rules.get('callback_after_refusal_max', 0) or 0)}",
        "",
    ]
    if repeated:
        lines.extend(
            [
                "Repeated contact raises the yield and shifts the sample towards people who "
                "are reachable more often. The number above is what that shift cost here; it "
                "is stated rather than folded into the completion rate.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Every included record was dialled at most once. A person who was not reached "
                "is a loss, not a person to call again — which keeps the time of day a "
                "controlled variable instead of a silent preselection.",
                "",
            ]
        )

    lines.extend(["## Terminal outcomes", "", "Counted once per person: the last attempt decides.", ""])
    outcome_rows = [
        [status, str(count), _percent(count, reached)]
        for status, count in sorted(status_counts.items())
    ]
    if not outcome_rows:
        outcome_rows = [["No attempts", "0", "n/a"]]
    lines.extend(_table(["Status", "Count", "Share of records reached"], outcome_rows))

    lines.extend(["", "## Outcome structure by assigned time window", ""])
    window_rows: list[list[str]] = []
    for window in windows:
        window_ids = [
            sample_id
            for sample_id in included_ids
            if data["assigned"][sample_id] == window
        ]
        window_status = Counter(
            final_status[sample_id] for sample_id in window_ids if sample_id in final_status
        )
        window_rows.append(
            [
                window,
                str(len(window_ids)),
                str(sum(window_status.values())),
                str(window_status["COMPLETED"]),
                _percent(window_status["COMPLETED"], len(window_ids)),
                *[str(window_status[status]) for status in LOSS_STATUSES],
            ]
        )
    lines.extend(
        _table(
            [
                "Window",
                "Drawn",
                "Attempted",
                "Completed",
                "Completion yield",
                *LOSS_STATUSES,
            ],
            window_rows or [["No sample", "0", "0", "0", "n/a", *("0" for _ in LOSS_STATUSES)]],
        )
    )
    lines.extend(
        [
            "",
            "Interpretation rule: `NO_ANSWER` is retained as a time-of-day availability signal; `DECLINED` is active refusal; `BUSY` and `VOICEMAIL` are separate availability/routing outcomes. They are not collapsed into one generic loss category.",
            "",
        ]
    )

    if str(questionnaire.get("order", "fixed")).lower() == "randomised":
        lines.extend(
            [
                "Item order was drawn separately for every respondent, filters kept intact. "
                "Position effects are therefore spread across the sample instead of resting "
                "on whichever item happened to be written first.",
                "",
            ]
        )

    lines.extend(["## Answer distributions by assigned time window", ""])

    response_rows: list[tuple[str, dict[str, Any]]] = []
    refusal_reasons = 0
    callbacks_offered = 0
    for row in data["responses"]:
        value = json.loads(row["structured_json"])
        if not isinstance(value, dict):
            continue
        if value.get("refusal_reason"):
            refusal_reasons += 1
        if value.get("callback_wanted"):
            callbacks_offered += 1
        if row["consent"] != "granted":
            continue
        response_rows.append((data["assigned"][int(row["sample_id"])], value))

    categorized_answers = 0
    categorized_with_raw = 0
    open_answers = 0
    for _, response in response_rows:
        answers = response.get("answers", {})
        raw_answers = response.get("raw_answers", {})
        if not isinstance(answers, dict) or not isinstance(raw_answers, dict):
            continue
        for question in questionnaire["questions"]:
            question_id = question["id"]
            raw_answer = raw_answers.get(question_id)
            if is_open_question(question):
                if isinstance(raw_answer, str) and raw_answer.strip():
                    open_answers += 1
                continue
            if isinstance(answers.get(question_id), str):
                categorized_answers += 1
                if isinstance(raw_answer, str) and raw_answer.strip():
                    categorized_with_raw += 1

    by_rule: Counter[str] = Counter()
    for row in attempt_rows:
        for note in _detail(row["detail_json"]).get("coded_by_rule", []) or []:
            if isinstance(note, dict):
                by_rule[str(note.get("rule", "unknown"))] += 1

    lines.extend(
        [
            "## Raw-answer audit",
            "",
            f"- Categorized answers: {categorized_answers}",
            f"- Categorized answers with retained raw source text: {categorized_with_raw}",
            f"- Open answers recorded as spoken: {open_answers}",
            "",
            "Raw response text is retained in the local structured response for auditability but is not printed in this aggregate report. Categories remain interpretations and can be checked against their raw source.",
            "",
        ]
    )
    if by_rule:
        lines.extend(
            [
                "### Answers outside the fixed categories",
                "",
                "The rule below was fixed before the field phase and applied as written.",
                "",
            ]
        )
        lines.extend(
            _table(
                ["Rule applied", "Answers"],
                [[rule, str(count)] for rule, count in sorted(by_rule.items())],
            )
        )
        lines.append("")

    for question in questionnaire["questions"]:
        question_id = question["id"]
        lines.extend([f"### {question_id}: {question['wording']}", ""])
        if is_open_question(question):
            spoken = sum(
                1
                for _, response in response_rows
                if isinstance(response.get("raw_answers", {}).get(question_id), str)
                and response["raw_answers"][question_id].strip()
            )
            lines.extend(
                [
                    f"Open question. {spoken} answers were recorded as spoken and are not "
                    "counted into categories here; coding happens in the analysis station, "
                    "against the raw text.",
                    "",
                ]
            )
            continue
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        denominators: Counter[str] = Counter()
        for window, response in response_rows:
            answer = response.get("answers", {}).get(question_id)
            if isinstance(answer, str):
                counts[window][answer] += 1
                denominators[window] += 1
        categories = list(question["categories"])
        if any(counts[window][UNLISTED_CODE] for window in windows):
            categories.append(UNLISTED_CODE)
        distribution_rows: list[list[str]] = []
        for category in categories:
            values = []
            total = 0
            for window in windows:
                count = counts[window][category]
                total += count
                values.append(f"{count} ({_percent(count, denominators[window])})")
            label = "outside the categories" if category == UNLISTED_CODE else category
            distribution_rows.append([label, *values, str(total)])
        lines.extend(_table(["Answer", *windows, "Total"], distribution_rows))
        scale = question.get("scale") or {}
        if scale.get("reversed"):
            lines.append("")
            lines.append(
                "Reversed item: the values above are as given. The dataset export carries "
                "the recoded value beside them; comparing them without recoding measures "
                "the opposite of the scale."
            )
        lines.extend(
            [
                "",
                "Percentages use non-missing answers within each window. Differences are descriptive; this report does not claim statistical significance.",
                "",
            ]
        )

    if refusal_reasons or callbacks_offered:
        lines.extend(
            [
                "## Refusals",
                "",
                f"- Refusals with a reason given: {refusal_reasons}",
                f"- People who said a call at another time would be welcome: {callbacks_offered}",
                "",
                "The reasons themselves stay in the local state. They are answers of "
                "individual people and belong in the analysis, not in an aggregate report.",
                "",
            ]
        )

    wording_rows = [
        row for row in data["responses"] if row["consent"] == "granted"
    ]
    reported_true = sum(int(row["asked_verbatim_reported"] or 0) for row in wording_rows)
    exact_matches = sum(int(row["wording_matches"] or 0) for row in wording_rows)
    response_count = len(wording_rows)
    live_observed = False
    transcript_audits = 0
    transcript_exact = 0
    for row in attempt_rows:
        detail = _detail(row["detail_json"])
        if detail.get("transport") == "live-api":
            live_observed = True
        if detail.get("transcript_format") == "timestamped-speaker-lines":
            transcript_audits += 1
            if detail.get("transcript_wording_matches") is True:
                transcript_exact += 1
    free_items = [
        question["id"]
        for question in questionnaire["questions"]
        if not question.get("verbatim", True)
    ]
    lines.extend(
        [
            "## Wording fidelity",
            "",
            f"- Consented interview results available: {response_count}",
            f"- `asked_verbatim=true` reported: {reported_true}",
            f"- Actual returned wording exactly matched the questionnaire: {exact_matches}",
            f"- Nested `result.transcript` records audited in memory: {transcript_audits}",
            f"- Transcript audits containing every expected quoted sentence: {transcript_exact}",
            "",
        ]
    )
    if free_items:
        lines.extend(
            [
                "Items the instrument released from fixed wording are excluded from this "
                "count: " + ", ".join(free_items) + ". For them a fresh phrasing is the "
                "intention, and judging them by the same yardstick would turn a "
                "methodological choice into a failure.",
                "",
            ]
        )
    if live_observed:
        lines.append(
            "Live API results are present. Schema wording fields are agent-reported; the separate transcript audit uses the measured `[mm:ss] SPEAKER: Text` string from `result.transcript`. Full transcripts are not persisted."
        )
    else:
        lines.append(
            "Only fixture evidence is present. Offline fixtures verify the enforcement and audit path, but cannot establish that the live CALL-E agent will speak verbatim."
        )
    lines.extend(
        [
            "",
            "## Privacy and scope",
            "",
            "This report contains study IDs and aggregates only. It contains no phone numbers or names. Withdrawn records are anonymized and excluded from every denominator above.",
            "",
        ]
    )
    return "\n".join(lines)
