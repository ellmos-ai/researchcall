"""The dataset, in the shape the next tool expects.

A survey tool that keeps its data to itself is not finished. What leaves here is
a rectangular file with one row per person and one column per item — the form
every statistics package reads, from a spreadsheet to R.

Two decisions from station 7 act here rather than being decoration:

* **free comments** go into the dataset, into a file of their own, or nowhere.
  Free text is what a person said in their own words, so where it lands is a
  privacy decision as much as a methodological one.
* **reversed items** are carried twice, as given and recoded. Turning them back
  is the step people forget, and forgetting it measures the opposite of the
  scale — so the file does it and says that it did.

What never leaves: phone numbers, and the records of anyone who withdrew.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any

from .coding import free_comment_policy, reverse_scale_value
from .database import load_questionnaire
from .questionnaire import UNLISTED_CODE, is_open_question
from .reporting import collect


UNLISTED_LABEL = "outside_categories"


def _rows(connection: sqlite3.Connection, study: sqlite3.Row) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    questionnaire = load_questionnaire(study)
    data = collect(connection, study)
    responses = {
        int(row["sample_id"]): row for row in data["responses"]
    }
    attempts_by_sample = data["by_sample"]

    records: list[dict[str, Any]] = []
    for sample_id in sorted(data["included_ids"]):
        attempts = attempts_by_sample.get(sample_id, [])
        response = responses.get(sample_id)
        structured: dict[str, Any] = {}
        if response is not None:
            try:
                loaded = json.loads(response["structured_json"])
                structured = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError:
                structured = {}
        records.append(
            {
                "sample_id": sample_id,
                "assigned_window": data["assigned"][sample_id],
                "final_window": str(attempts[-1]["time_window"]) if attempts else "",
                "attempts": len(attempts),
                "status": data["final_status"].get(sample_id, ""),
                "response": response,
                "structured": structured,
            }
        )
    return records, questionnaire


def dataset_csv(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """One row per person, one column per item."""
    records, questionnaire = _rows(connection, study)
    policy = free_comment_policy(questionnaire)
    questions = questionnaire.get("questions", [])

    header = [
        "record",
        "assigned_window",
        "final_window",
        "attempts",
        "status",
        "consent",
        "asked_verbatim_reported",
        "wording_matched",
    ]
    for question in questions:
        if is_open_question(question):
            if policy == "in_dataset":
                header.append(f"{question['id']}_text")
            continue
        header.append(str(question["id"]))
        if (question.get("scale") or {}).get("reversed"):
            header.append(f"{question['id']}_recoded")
    if policy == "in_dataset":
        header.append("refusal_reason")

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for record in records:
        response = record["response"]
        structured = record["structured"]
        answers = structured.get("answers", {}) if structured else {}
        raw_answers = structured.get("raw_answers", {}) if structured else {}
        row: list[Any] = [
            record["sample_id"],
            record["assigned_window"],
            record["final_window"],
            record["attempts"],
            record["status"],
            response["consent"] if response is not None else "",
            int(response["asked_verbatim_reported"]) if response is not None else "",
            int(response["wording_matches"]) if response is not None else "",
        ]
        for question in questions:
            question_id = str(question["id"])
            if is_open_question(question):
                if policy == "in_dataset":
                    row.append(raw_answers.get(question_id) or "")
                continue
            value = answers.get(question_id)
            row.append(UNLISTED_LABEL if value == UNLISTED_CODE else (value or ""))
            if (question.get("scale") or {}).get("reversed"):
                recoded = reverse_scale_value(
                    question, None if value == UNLISTED_CODE else value
                )
                row.append(recoded or "")
        if policy == "in_dataset":
            row.append(structured.get("refusal_reason") or "")
        writer.writerow(row)
    return buffer.getvalue()


def free_text_csv(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """The free answers on their own, when the analysis rule keeps them apart."""
    records, questionnaire = _rows(connection, study)
    open_ids = [
        str(question["id"])
        for question in questionnaire.get("questions", [])
        if is_open_question(question)
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["record", "item", "text"])
    for record in records:
        raw_answers = (record["structured"] or {}).get("raw_answers", {})
        for question_id in open_ids:
            text = raw_answers.get(question_id)
            if isinstance(text, str) and text.strip():
                writer.writerow([record["sample_id"], question_id, text])
        reason = (record["structured"] or {}).get("refusal_reason")
        if isinstance(reason, str) and reason.strip():
            writer.writerow([record["sample_id"], "refusal_reason", reason])
    return buffer.getvalue()


def findings(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """A findings note, started from the numbers rather than from a blank page.

    The pipeline keeps findings as a plain document that grows with the study —
    the same habit as a proof note. What this writes is the part a machine can
    know: the question, the hypotheses, what the field phase produced. The
    reading is left empty on purpose; filling it in is the researcher's work, and
    a generated interpretation would be a guess wearing the study's name.
    """
    questionnaire = load_questionnaire(study)
    data = collect(connection, study)
    statuses = data["final_status"]
    completed = sum(1 for status in statuses.values() if status == "COMPLETED")
    included = len(data["included_ids"])
    lines = [
        f"# Findings: {questionnaire.get('title', study['title'])}",
        "",
        "## Research question",
        "",
        str(questionnaire.get("question") or questionnaire.get("title", "")),
        "",
    ]
    hypotheses = questionnaire.get("hypotheses") or []
    if hypotheses:
        lines.extend(["## Hypotheses", ""])
        lines.extend(f"- [ ] {line}" for line in hypotheses)
        lines.append("")
    lines.extend(
        [
            "## What the field phase produced",
            "",
            f"- Included records: {included}",
            f"- Records with an attempt: {len(statuses)}",
            f"- Attempts placed: {len(data['attempts'])}",
            f"- Completed interviews: {completed}",
            "",
            "## Reading",
            "",
            "<!-- Yours. Say what the numbers support and what they do not. A difference",
            "     between time windows is a difference, not a finding about the population. -->",
            "",
            "## Limitations carried from the method",
            "",
            "- Time of day is controlled by the assigned window, not by when the run happened.",
            "- Nonresponse is reported by kind; NO_ANSWER and DECLINED are never added together.",
            "- Categories are interpretations; the raw answer sits beside every one of them.",
            "",
        ]
    )
    return "\n".join(lines)


def codebook(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """What every column means — the file that makes the dataset re-usable."""
    questionnaire = load_questionnaire(study)
    policy = free_comment_policy(questionnaire)
    coding = questionnaire.get("coding") or {}
    lines = [
        f"# Codebook: {questionnaire.get('title', study['title'])}",
        "",
        f"- Language of the interview: {questionnaire.get('language', 'n/a')}",
        f"- Item order: {questionnaire.get('order', 'fixed')}",
        f"- Answers outside the categories: {coding.get('unlisted_answers', 'as_other')}",
        f"- Free comments: {policy}",
        "",
    ]
    hypotheses = questionnaire.get("hypotheses") or []
    if hypotheses:
        lines.extend(["## Hypotheses", ""])
        lines.extend(f"- {line}" for line in hypotheses)
        lines.append("")
        lines.append(
            "Every item below names the hypothesis it serves. An item that serves none "
            "measures something the study did not set out to measure."
        )
        lines.append("")
    lines.extend(
        [
            "## Columns that describe the call",
            "",
            "| Column | Meaning |",
            "| --- | --- |",
            "| record | Pseudonymous record number. It identifies a row, not a person. |",
            "| assigned_window | The time of day the record was drawn into. |",
            "| final_window | Where the last attempt was made; differs only with repeated contact. |",
            "| attempts | How often this record was dialled. |",
            "| status | Terminal outcome of the last attempt. |",
            "| consent | granted, declined or not_obtained. |",
            "| asked_verbatim_reported | What the agent said about its own fidelity. |",
            "| wording_matched | Whether the returned wording actually matched. |",
            "",
            "## Items",
            "",
        ]
    )
    for number, question in enumerate(questionnaire.get("questions", []), start=1):
        lines.append(f"### {number}. `{question['id']}` — {question.get('format', 'categorical')}")
        lines.append("")
        lines.append(f"- Wording: {question['wording']}")
        if question.get("hypothesis"):
            lines.append(f"- Serves hypothesis: {question['hypothesis']}")
        if is_open_question(question):
            place = {
                "in_dataset": f"column `{question['id']}_text` in the dataset",
                "separate": "the separate free-text file",
                "discard": "nowhere — the rule discards free text",
            }.get(policy, policy)
            lines.append(f"- Open answer, recorded as spoken; stored in {place}.")
        else:
            lines.append("- Values: " + ", ".join(f"`{c}`" for c in question["categories"]))
            lines.append(
                f"- `{UNLISTED_LABEL}` marks an answer that fitted none of them and was "
                "kept by the analysis rule."
            )
            scale = question.get("scale") or {}
            if scale:
                lines.append(
                    f"- Scale with {scale.get('steps')} steps: 1 = {scale.get('low')}, "
                    f"{scale.get('steps')} = {scale.get('high')}."
                )
            if scale.get("reversed"):
                lines.append(
                    f"- Reversed item. Column `{question['id']}` holds the answer as given, "
                    f"`{question['id']}_recoded` the turned-around value. Use the recoded "
                    "one in any scale score."
                )
        condition = question.get("ask_if")
        if condition:
            values = condition["equals"]
            values = [values] if isinstance(values, str) else list(values)
            lines.append(
                f"- Asked only if `{condition['question']}` is "
                + " or ".join(f"`{value}`" for value in values)
                + "; empty otherwise, which is a filter, not a missing value."
            )
        if question.get("max_follow_ups"):
            depth = question["max_follow_ups"]
            lines.append(
                "- Follow-up questions allowed: "
                + ("until the answer was exhausted" if depth < 0 else str(depth))
            )
        if question.get("analysis_rule"):
            lines.append(f"- Analysis rule fixed in advance: {question['analysis_rule']}")
        lines.append("")
    lines.extend(
        [
            "## What is not in this file",
            "",
            "Phone numbers, names, and every record of a person who withdrew. Withdrawal "
            "removes the row rather than flagging it, so it cannot be counted back in.",
            "",
        ]
    )
    return "\n".join(lines)


# -- taking the dataset where researchers actually work --------------------
#
# The .sav binary is proprietary; the documented interchange route is a CSV
# plus an import syntax file, and PSPP reads exactly that. R gets the same
# CSV with a reading script. Excel gets a real .xlsx, written with the
# standard library -- the file is a zip of XML, and a writing dependency for
# one sheet of text would be the tail wagging the dog.

def _csv_table(connection: sqlite3.Connection, study: sqlite3.Row) -> list[list[str]]:
    text = dataset_csv(connection, study)
    return [row for row in csv.reader(io.StringIO(text))]


def dataset_xlsx(connection: sqlite3.Connection, study: sqlite3.Row) -> bytes:
    """The dataset as a one-sheet .xlsx with inline strings."""
    import re as _re
    import zipfile

    table = _csv_table(connection, study)

    def column_name(index: int) -> str:
        name = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    def escape(value: str) -> str:
        value = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
        return (
            value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    rows_xml = []
    for row_index, row in enumerate(table, start=1):
        cells = "".join(
            f'<c r="{column_name(col)}{row_index}" t="inlineStr">'
            f"<is><t xml:space=\"preserve\">{escape(value)}</t></is></c>"
            for col, value in enumerate(row)
        )
        rows_xml.append(f'<row r="{row_index}">{cells}</row>')

    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows_xml)}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="dataset" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def spss_syntax(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """An .sps file that reads dataset.csv -- for SPSS and PSPP alike."""
    table = _csv_table(connection, study)
    header = table[0] if table else []
    numeric = {"record", "attempts", "asked_verbatim_reported", "wording_matched"}
    variables = "\n".join(
        f"  {name} {'F8.0' if name in numeric else 'A120'}" for name in header
    )
    return (
        "* ResearchCall dataset import for SPSS / PSPP.\n"
        "* Place dataset.csv next to this file, then run.\n"
        "GET DATA\n"
        "  /TYPE=TXT\n"
        "  /FILE='dataset.csv'\n"
        "  /DELIMITERS=','\n"
        "  /QUALIFIER='\"'\n"
        "  /FIRSTCASE=2\n"
        "  /VARIABLES=\n"
        f"{variables}.\n"
        "EXECUTE.\n"
    )


def r_script(connection: sqlite3.Connection, study: sqlite3.Row) -> str:
    """An .R file that reads dataset.csv and shows the first honest numbers."""
    del connection, study
    return (
        "# ResearchCall dataset import for R.\n"
        "# Place dataset.csv next to this script, then source it.\n"
        'dataset <- read.csv("dataset.csv", stringsAsFactors = FALSE)\n'
        "str(dataset)\n"
        "# Dispositions -- the loss structure comes first, not the means:\n"
        "table(dataset$status)\n"
    )
