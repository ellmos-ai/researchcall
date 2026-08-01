from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from typing import Any

from .database import load_questionnaire


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


def build_report(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    questionnaire = load_questionnaire(study)
    rows = connection.execute(
        """
        SELECT s.id AS sample_id, s.time_window, s.excluded_at,
               a.call_status, a.detail_json,
               r.structured_json, r.consent,
               r.asked_verbatim_reported, r.wording_matches
        FROM sample s
        LEFT JOIN attempt a ON a.sample_id = s.id
        LEFT JOIN response r ON r.sample_id = s.id
        WHERE s.study_id = ?
        ORDER BY s.time_window, s.id
        """,
        (study["id"],),
    ).fetchall()
    included = [row for row in rows if row["excluded_at"] is None]
    excluded_count = len(rows) - len(included)
    windows = sorted({str(row["time_window"]) for row in included})
    status_counts = Counter(
        str(row["call_status"]) for row in included if row["call_status"] is not None
    )
    completed = status_counts["COMPLETED"]
    attempted = sum(status_counts.values())

    lines = [
        f"# ResearchCall report: {study['title']}",
        "",
        "## Fieldwork summary",
        "",
        f"- Drawn records: {len(rows)}",
        f"- Included records: {len(included)}",
        f"- Privacy withdrawals excluded from analysis: {excluded_count}",
        f"- Attempts recorded: {attempted}",
        f"- Completed interviews: {completed}",
        f"- Completion yield (completed / included drawn): {_percent(completed, len(included))}",
        "",
        "A recorded attempt is never retried. Open records have no attempt yet; the host may invoke a later bounded quota for their assigned window.",
        "",
        "## Terminal outcomes",
        "",
    ]
    outcome_rows = [
        [status, str(count), _percent(count, attempted)]
        for status, count in sorted(status_counts.items())
    ]
    if not outcome_rows:
        outcome_rows = [["No attempts", "0", "n/a"]]
    lines.extend(_table(["Status", "Count", "Share of attempts"], outcome_rows))

    lines.extend(["", "## Outcome structure by assigned time window", ""])
    window_rows: list[list[str]] = []
    for window in windows:
        window_data = [row for row in included if row["time_window"] == window]
        window_status = Counter(
            str(row["call_status"])
            for row in window_data
            if row["call_status"] is not None
        )
        row = [
            window,
            str(len(window_data)),
            str(sum(window_status.values())),
            str(window_status["COMPLETED"]),
            _percent(window_status["COMPLETED"], len(window_data)),
            *[str(window_status[status]) for status in LOSS_STATUSES],
        ]
        window_rows.append(row)
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
            "## Answer distributions by assigned time window",
            "",
        ]
    )

    response_rows: list[tuple[str, dict[str, Any]]] = []
    for row in included:
        if row["consent"] != "granted" or row["structured_json"] is None:
            continue
        value = json.loads(row["structured_json"])
        if isinstance(value, dict):
            response_rows.append((str(row["time_window"]), value))

    categorized_answers = 0
    categorized_with_raw = 0
    for _, response in response_rows:
        answers = response.get("answers", {})
        raw_answers = response.get("raw_answers", {})
        if not isinstance(answers, dict) or not isinstance(raw_answers, dict):
            continue
        for question in questionnaire["questions"]:
            question_id = question["id"]
            if isinstance(answers.get(question_id), str):
                categorized_answers += 1
                raw_answer = raw_answers.get(question_id)
                if isinstance(raw_answer, str) and raw_answer.strip():
                    categorized_with_raw += 1

    lines.extend(
        [
            "## Raw-answer audit",
            "",
            f"- Categorized answers: {categorized_answers}",
            f"- Categorized answers with retained raw source text: {categorized_with_raw}",
            "",
            "Raw response text is retained in the local structured response for auditability but is not printed in this aggregate report. Categories remain interpretations and can be checked against their raw source.",
            "",
        ]
    )

    for question in questionnaire["questions"]:
        question_id = question["id"]
        lines.extend([f"### {question_id}: {question['wording']}", ""])
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        denominators: Counter[str] = Counter()
        for window, response in response_rows:
            answer = response.get("answers", {}).get(question_id)
            if isinstance(answer, str):
                counts[window][answer] += 1
                denominators[window] += 1
        distribution_rows: list[list[str]] = []
        for category in question["categories"]:
            values = []
            total = 0
            for window in windows:
                count = counts[window][category]
                total += count
                values.append(f"{count} ({_percent(count, denominators[window])})")
            distribution_rows.append([category, *values, str(total)])
        lines.extend(_table(["Answer", *windows, "Total"], distribution_rows))
        lines.extend(
            [
                "",
                "Percentages use non-missing answers within each window. Differences are descriptive; this report does not claim statistical significance.",
                "",
            ]
        )

    wording_rows = [
        row
        for row in included
        if row["consent"] == "granted" and row["structured_json"] is not None
    ]
    reported_true = sum(int(row["asked_verbatim_reported"] or 0) for row in wording_rows)
    exact_matches = sum(int(row["wording_matches"] or 0) for row in wording_rows)
    response_count = len(wording_rows)
    live_observed = False
    transcript_audits = 0
    transcript_exact = 0
    for row in included:
        try:
            detail = json.loads(row["detail_json"] or "{}")
        except json.JSONDecodeError:
            detail = {}
        if detail.get("transport") == "live-api":
            live_observed = True
        if detail.get("transcript_format") == "timestamped-speaker-lines":
            transcript_audits += 1
            if detail.get("transcript_wording_matches") is True:
                transcript_exact += 1
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
