"""Which settings reach the machinery — and which are only recorded so far.

A form definition can be answered long before anything reads the answer. That gap
is the most dangerous thing a research tool can hide: a person who sets
``contact_rules.attempts_per_person`` and sees it saved will assume the calls are
repeated. If they are not, the study is wrong and nobody is told.

So the gap is written down here, once, and shown next to every control. The rule
is deliberately inverted against the usual habit: a field is *not effective* until
it appears in this table with a place where it takes effect. A new form definition
therefore fails :func:`unclassified` until somebody decides — and says out loud —
whether the machinery reads it.

The table lives in code, not in the YAML, on purpose. The YAML says what a
decision *is*; only the code knows whether the code reads it. Putting the claim
next to the definition would let it stay true-looking after the reader was removed.
"""

from __future__ import annotations

from typing import Iterable

from .forms import Field


#: Part of the frame. Locked, always in force, no control anywhere.
FRAME = "frame"
#: Reaches the words the agent says — the task text built for a call.
SCRIPT = "script"
#: Steers the run itself: who is drawn, when, how often, in which order.
RUN = "run"
#: Steers coding, the report or the export.
ANALYSIS = "analysis"
#: Recorded and kept, but nothing reads it yet.
DECLARED = "declared"

ORDER = (FRAME, SCRIPT, RUN, ANALYSIS, DECLARED)

# path -> (where it takes effect, why not yet / where exactly)
#
# The second element is an English sentence; ui.json carries the German. For an
# effective field it names the place, for a declared one the reason. Both are
# shown to the person setting the value.
EFFECTS: dict[str, tuple[str, str]] = {
    # --- 01 research question ------------------------------------------------
    "question": (SCRIPT, "Heads the codebook and the report."),
    "hypotheses": (
        ANALYSIS,
        "Each item names the hypothesis it serves; the codebook groups by it.",
    ),
    # --- 02 instrument -------------------------------------------------------
    "items": (SCRIPT, "Becomes the questionnaire the dry run actually asks."),
    "questionnaire.order": (
        RUN,
        "Randomised draws a fresh item order per respondent, filters respected.",
    ),
    "questionnaire.jump_rules": (
        RUN,
        "Compiled into a filter condition on every skipped item.",
    ),
    "questionnaire.parallel_forms": (
        DECLARED,
        "Two equivalent forms need paired items; the item grammar has no pairing yet.",
    ),
    # --- 03 ethics -----------------------------------------------------------
    "ethics.instruction": (SCRIPT, "First spoken block, quoted word for word."),
    "ethics.time_estimate": (
        SCRIPT,
        "Speaks a duration computed from the instrument, not a typed guess.",
    ),
    "ethics.privacy_text": (SCRIPT, "Spoken before consent is asked."),
    "ethics.consent_explicit": (FRAME, "Consent is asked before any question."),
    "ethics.right_to_stop": (FRAME, "The right to stop is stated in every call."),
    "ethics.number_origin": (SCRIPT, "Spoken block: where the number came from."),
    "ethics.on_refusal.ask_reason": (
        SCRIPT,
        "Adds the refusal question and a schema field that stores the answer.",
    ),
    "ethics.on_refusal.offer_callback": (
        RUN,
        "Offers a later call and re-queues whoever accepts, up to the callback limit.",
    ),
    "ethics.greeting": (SCRIPT, "Spoken opening, phrased freely by the agent."),
    "ethics.closing": (SCRIPT, "Spoken closing, phrased freely by the agent."),
    "ethics.policies": (
        DECLARED,
        "Policy files are named but not read; there is no policy reader yet.",
    ),
    "disclosure_level": (
        DECLARED,
        "The pipeline's L1-L5 catalogue is not in this repository, and inventing "
        "its wording would be worse than leaving it unused.",
    ),
    # --- 04 sampling ---------------------------------------------------------
    "sample.source": (
        DECLARED,
        "Named for the record; the dry run draws from a generated fictitious frame.",
    ),
    "sample.size": (RUN, "How many records are drawn."),
    "sample.method": (
        RUN,
        "Random draw or census. Stratified is refused rather than silently drawn at "
        "random, because the dry-run frame carries no stratifying attributes.",
    ),
    "sample.time_windows": (RUN, "The windows a record can be assigned to."),
    "sample.assign_windows_randomly": (
        RUN,
        "Off assigns windows in equal blocks instead of by lot.",
    ),
    "contact_rules.attempts_per_person": (
        RUN,
        "Extra attempts after no answer, busy or voicemail. The report states the "
        "number reached this way.",
    ),
    "contact_rules.spread_attempts": (
        RUN,
        "Sends a repeat attempt into a different time window.",
    ),
    "contact_rules.callback_after_refusal_max": (
        RUN,
        "Upper bound for people who refused but accepted a later call.",
    ),
    "contact_rules.daily_quota": (RUN, "Records worked per window in one run."),
    "contact_rules.concurrent_calls": (
        DECLARED,
        "The dry run is serial by design; the API's concurrency limit is unverified.",
    ),
    "contact_rules.calling_hours": (
        DECLARED,
        "Needs a scheduler with a clock; this tool has no daemon and no timer.",
    ),
    # --- 05 pretest ----------------------------------------------------------
    "pretest.export_questionnaire": (
        ANALYSIS,
        "On offers the instrument as a document to read and pass around; off "
        "withdraws the download.",
    ),
    "pretest.send_to_reviewers": (
        DECLARED,
        "Sending mail is a connector this build does not carry.",
    ),
    "pretest.call_reviewers": (
        DECLARED,
        "Calling a colleague is a real call, which this interface cannot place.",
    ),
    "pretest.self_test_calls": (
        DECLARED,
        "A test call to yourself is still a real call.",
    ),
    "pretest.instrument_check.calls": (
        RUN,
        "How many dry-run interviews the instrument check performs.",
    ),
    "pretest.instrument_check.syntactic_marker": (
        RUN,
        "Added as a deliberately clumsy item; smoothing it out is the tell.",
    ),
    "pretest.instrument_check.measure": (
        FRAME,
        "The check reports on exactly these five criteria — and says which two of "
        "them a dry run cannot decide instead of scoring them.",
    ),
    "pretest.instrument_check.report_result_honestly": (
        FRAME,
        "A failed check stays visible; nothing suppresses it.",
    ),
    # --- 06 fieldwork --------------------------------------------------------
    "fieldwork.storage": (
        DECLARED,
        "State is SQLite in the workspace; a file-per-record backend is not built.",
    ),
    "fieldwork.path": (
        DECLARED,
        "The workspace directory is set when the server starts, not per study.",
    ),
    "fieldwork.keep_raw_answer": (FRAME, "Raw wording is always kept beside the coding."),
    "fieldwork.keep_transcript": (
        ANALYSIS,
        "On, the verbatim transcript is stored with the attempt and shown beside "
        "the answer in the review; off, only the audit flags remain. Numbers are "
        "removed either way, and a withdrawal erases the text with the record.",
    ),
    "fieldwork.poll_interval_seconds": (
        DECLARED,
        "Only the live transport polls, and this interface cannot reach it.",
    ),
    "fieldwork.stop_on_error": (RUN, "Stops the run at the first failed record."),
    "fieldwork.resumable": (
        RUN,
        "On leaves finished records alone so a second run continues where it stopped.",
    ),
    # --- 07 analysis ---------------------------------------------------------
    "analysis.keep_raw_alongside_coded": (
        FRAME,
        "Raw answer and interpretation stay side by side.",
    ),
    "analysis.unlisted_answers": (
        ANALYSIS,
        "Applied when a returned answer fits none of the categories.",
    ),
    "analysis.free_comments": (
        ANALYSIS,
        "Decides whether free text enters the dataset, a second file, or neither.",
    ),
    "analysis.qualitative.methods": (
        DECLARED,
        "Counting is done; metaphor, framing and worldview analysis need a model "
        "this dry-run build does not call.",
    ),
    "analysis.qualitative.rating_models": (
        DECLARED,
        "Inter-rater reliability needs two models rating the same answers.",
    ),
    "analysis.report.response_rate": (FRAME, "The report always states the yield."),
    "analysis.report.dropout_by_window": (
        FRAME,
        "Losses are always broken down by time window.",
    ),
    "analysis.report.answers_by_window": (
        FRAME,
        "Answer distributions are always shown per window.",
    ),
    # --- 08 reporting --------------------------------------------------------
    "reporting.findings_file": (
        ANALYSIS,
        "Names the findings note the report offers for download, started from the "
        "numbers with the reading left open.",
    ),
    "reporting.journal_format": (
        DECLARED,
        "Manuscript templates are a later station of the pipeline.",
    ),
    "reporting.languages": (
        DECLARED,
        "The report is written in one language; a second version needs a translator.",
    ),
    "reporting.disclosure_level": (
        DECLARED,
        "Same catalogue as the conversation frame, and equally absent here.",
    ),
    "publication.target": (
        DECLARED,
        "Uploading anywhere is a step this build deliberately does not take.",
    ),
    "publication.source_check_before_upload": (
        FRAME,
        "No upload without a source check. This build uploads nowhere at all, so the "
        "rule holds by construction rather than by enforcement.",
    ),
    "publication.dry_run_first": (
        FRAME,
        "Any upload is rehearsed first. Nothing here uploads, which is the strictest "
        "form the rule can take.",
    ),
}


def effect_of(field: Field | str) -> str:
    """Where this setting takes effect, or ``DECLARED`` when nothing reads it."""
    path = field if isinstance(field, str) else field.path
    entry = EFFECTS.get(path)
    return entry[0] if entry else DECLARED


def reason_of(field: Field | str) -> str:
    """The sentence shown beside the field: where it acts, or why it does not."""
    path = field if isinstance(field, str) else field.path
    entry = EFFECTS.get(path)
    return entry[1] if entry else "Not classified yet."


def is_effective(field: Field | str) -> bool:
    return effect_of(field) != DECLARED


def unclassified(fields: Iterable[Field]) -> list[str]:
    """Field paths with no entry. A new definition lands here until someone decides."""
    return sorted(field.path for field in fields if field.path not in EFFECTS)


def stale(fields: Iterable[Field]) -> list[str]:
    """Entries for paths no definition carries any more."""
    known = {field.path for field in fields}
    return sorted(path for path in EFFECTS if path not in known)


def declared_only(fields: Iterable[Field], station: str | None = None) -> list[Field]:
    """The settings of one station (or of all) that are recorded but not read."""
    return [
        field
        for field in fields
        if (station is None or field.station == station) and not is_effective(field)
    ]


def summary(fields: Iterable[Field]) -> dict[str, int]:
    """How many settings sit in each class — counted, never asserted."""
    counts = {name: 0 for name in ORDER}
    for field in fields:
        counts[effect_of(field)] += 1
    return counts
