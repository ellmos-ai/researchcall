# EVIDENCE — ResearchCall

Date: 2026-08-01

This file separates the operator-provided live measurements in `FINDINGS.md` from commands actually executed in this repository during the post-findings run. This run made no real call and no CALL-E network request.

## Measured service evidence incorporated, not repeated here

`FINDINGS.md` records one real CALL-E test call and associated API checks. The implementation and README now treat these as measured facts:

- double-quoted task text was spoken character-for-character, including an intentional typo;
- framing outside quotes was paraphrased and augmented by the planner;
- nonterminal `status` remained `PREPARING` during speech, while `activity` showed progress;
- the final transcript was a `[mm:ss] SPEAKER: Text` string in `result.transcript`, while top-level `transcript` was `null`;
- schema-validated results were available through REST, not MCP, and a cross-path ID lookup returned HTTP 404;
- a free response was interpreted into a category, making retained raw answers necessary;
- the measured call had about 40 seconds of setup time before ringing.

No claim is made that this local run independently repeated those live observations.

## Executed in this run

Baseline revision:

```text
> git log -1 --oneline
57da691 docs: add FINDINGS.md — measured behaviour from a real call
```

The clean baseline suite produced:

```text
> python -m unittest discover -s tests -v
...
----------------------------------------------------------------------
Ran 9 tests in 3.948s

OK
```

The first regression-first run after adding tests exited 1 as intended: 11 tests ran, with one failure and two errors for the then-missing `raw_answers` task/schema behavior and `progress_callback` support. After the implementation patch, the expanded suite passed.

### Editable installation and module invocation

A fresh venv was created under the ignored repository path `out/verification-findings-20260801/venv`. The combined creation/install harness timed out before returning a result, so its success was not assumed. Readback showed a working venv:

```text
> out\verification-findings-20260801\venv\Scripts\python.exe --version
Python 3.12.10
```

The first explicitly offline install attempt failed because a default Python 3.12 venv had no local `setuptools.build_meta`:

```text
> python -m pip install -e . --no-build-isolation --no-deps --no-index
Obtaining file:///C:/_Local_DEV/repos/researchcall
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.build_meta'
exit code 2
```

The ignored test venv was then configured to see the already installed system packages. Local `setuptools` was `82.0.1`. Repeating the same no-index install succeeded:

```text
> python -m pip install -e . --no-build-isolation --no-deps --no-index
Obtaining file:///C:/_Local_DEV/repos/researchcall
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Building wheels for collected packages: researchcall
  Building editable for researchcall (pyproject.toml): started
  Building editable for researchcall (pyproject.toml): finished with status 'done'
Successfully built researchcall
Installing collected packages: researchcall
Successfully installed researchcall-0.1.0
exit code 0
```

The installed module then worked from the repository root without `PYTHONPATH`:

```text
> python -m researchcall --help
usage: researchcall [-h] [--db DB]
                    {init,create-study,import-frame,draw,run-day,report,withdraw,demo}
                    ...

Dry-run-first standardized scientific telephone survey tooling.

positional arguments:
  {init,create-study,import-frame,draw,run-day,report,withdraw,demo}
    init                Initialize the local SQLite state database.

options:
  -h, --help            show this help message and exit
  --db DB
exit code 0
```

The successful pip output named an ephemeral wheel-cache directory under `C:\Users\User\AppData\Local\Temp`. An immediate readback returned `path not found`; no persistent verification artifact was found there. Persistent test artifacts are under the repository's ignored `out/` tree.

### Final static and automated tests

```text
> python -m compileall -q src tests
exit code 0; no output
```

```text
> python -m unittest discover -s tests -v
test_demo_runs_end_to_end_without_network (test_researchcall.ResearchCallTestCase.test_demo_runs_end_to_end_without_network) ... ok
test_duplicate_phone_cannot_create_two_person_attempts (test_researchcall.ResearchCallTestCase.test_duplicate_phone_cannot_create_two_person_attempts) ... ok
test_fixed_wording_filter_and_audit_schema_are_in_task (test_researchcall.ResearchCallTestCase.test_fixed_wording_filter_and_audit_schema_are_in_task) ... ok
test_fixture_keeps_raw_answer_separate_from_interpreted_category (test_researchcall.ResearchCallTestCase.test_fixture_keeps_raw_answer_separate_from_interpreted_category) ... ok
test_live_client_reads_bearer_only_from_calle_api_key (test_researchcall.ResearchCallTestCase.test_live_client_reads_bearer_only_from_calle_api_key) ... ok
test_live_mode_fails_before_client_creation_without_exact_intent (test_researchcall.ResearchCallTestCase.test_live_mode_fails_before_client_creation_without_exact_intent) ... error=Live mode requires --confirm-live "CALL 1" for this bounded quota
ok
test_live_rest_path_uses_activity_and_nested_result (test_researchcall.ResearchCallTestCase.test_live_rest_path_uses_activity_and_nested_result) ... ok
test_phone_validation_and_masking (test_researchcall.ResearchCallTestCase.test_phone_validation_and_masking) ... ok
test_random_draw_assigns_windows_and_every_sample_is_attempted_once (test_researchcall.ResearchCallTestCase.test_random_draw_assigns_windows_and_every_sample_is_attempted_once) ... ok
test_report_preserves_loss_structure_and_never_contains_phone_numbers (test_researchcall.ResearchCallTestCase.test_report_preserves_loss_structure_and_never_contains_phone_numbers) ... ok
test_sqlite_frame_source_is_opened_read_only (test_researchcall.ResearchCallTestCase.test_sqlite_frame_source_is_opened_read_only) ... ok
test_transcript_is_audited_in_memory_but_not_persisted (test_researchcall.ResearchCallTestCase.test_transcript_is_audited_in_memory_but_not_persisted) ... ok
test_withdrawal_erases_identifiers_and_excludes_record (test_researchcall.ResearchCallTestCase.test_withdrawal_erases_identifiers_and_excludes_record) ... ok

----------------------------------------------------------------------
Ran 13 tests in 2.944s

OK
```

### Installed offline demonstration

```text
> python -m researchcall demo --workspace out/verification-findings-20260801/demo --seed 42
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,"EXPIRED":4,"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
report=out\verification-findings-20260801\demo\report.md
exit code 0
```

Read-only inspection of the generated database and report produced:

```text
frame=200
sample=50
attempt=50
response=19
retry_duplicates=0
missing_timestamps=0
quick_check=ok
unmasked_fixture_phone=false
raw_answer_audit=true
nested_transcript_audit=true
time_window_outcomes=true
```

Repository checks before this evidence update produced `git diff --check` exit code 0, no U+FFFD replacement characters in changed files, and no JWT/OpenAI-style secret patterns in changed files. The German questionnaire fixture separately produced:

```text
contains_native_ä=true
contains_native_ö=true
contains_native_ü=true
replacement_character=false
```

## Implementation evidence covered by tests

- Only consent, questions, and preplanned follow-ups use double quotes in `task`; filter values and category labels use non-spoken backtick labels.
- `recipient_result_schema` requires both interpreted `answers` and uncorrected `raw_answers`.
- Structured fixtures without explicit `raw_answers` are rejected; interpreted categories are never fabricated as raw evidence.
- The REST test observes `activity` while `status=PREPARING`; progress snapshots intentionally contain no status or activity text.
- A top-level `transcript=null` does not mask the nested `result.transcript` string.
- Transcript format and quoted wording are audited in memory; full transcript text is absent from persisted attempt details.
- The live client reads the bearer token from `CALLE_API_KEY`; `CALLE_TOKEN` alone is rejected.
- The current dispatcher is serial but contains no asserted provider concurrency limit.

## Not executed in this run

- No CALL-E account registration, authentication, real phone call, `--live` execution, webhook, or network request to CALL-E/AiRudder.
- No new live test of wording, activity duplication, transcript timing, setup latency, REST/MCP ID separation, voicemail, busy, or no-answer behavior.
- No parallel-call test; service concurrency remains unverified.
- No CI run.
- No push, remote mutation, release, publication, pull request, or video.

## Local commit attempt

The requested local commit could not be created because the managed sandbox exposes `.git` read-only. The direct attempt produced:

```text
> git add -- EVIDENCE.md README.md src/researchcall/calls.py src/researchcall/cli.py src/researchcall/fixtures/outcomes.json src/researchcall/questionnaire.py src/researchcall/reporting.py src/researchcall/runner.py tests/test_researchcall.py
fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied
exit code 128
```

The alternative FileCommander process call was rejected before execution. A final PowerShell-backed attempt also failed before command execution with `CreateProcessAsUserW failed: 5 (Zugriff verweigert)`. No file was staged, no commit was created, and no push was attempted.

## Form surface completion run — 2026-08-02

This run completed the station form definitions and integrated the previously untracked `forms.py` and `OBERFLAECHE-UND-TEXT.md` work. It made no real call and no CALL-E network request.

Two source-bound assumptions were applied:

- The prompt called station 5 “Ethik/Einwilligung”, but the canonical router, folder, station skill, and config all define `05-pretest`. The form file therefore represents the pretest. Consent and withdrawal remain in canonical station `03-ethics`.
- No standalone recording-notice config key exists in a station skill or config template. No such field was invented. Recording or transcription disclosure is required as content of `ethics.privacy_text`, and `fieldwork.keep_transcript` remains the linked storage decision.

### Regression-first parser result

The first focused run loaded every file through PyYAML, but exposed a real failure in the dependency-free fallback when an `options:` block started as `None`:

```text
> python -X utf8 -m unittest discover -s tests -p test_forms.py -v
test_dependency_free_reader_preserves_inline_list_defaults ... ERROR
test_every_entry_declares_the_complete_form_contract ... ERROR
test_every_station_file_loads_individually ... ok
test_locked_fields_create_neither_questions_nor_form_fields ... ok
AttributeError: 'NoneType' object has no attribute 'append'
----------------------------------------------------------------------
Ran 4 tests in 0.557s

FAILED (errors=2)
```

After changing only that fallback initialization, the same focused suite produced:

```text
> python -X utf8 -m unittest discover -s tests -p test_forms.py -v
test_dependency_free_reader_preserves_inline_list_defaults (test_forms.FormDefinitionTestCase.test_dependency_free_reader_preserves_inline_list_defaults) ... ok
test_every_entry_declares_the_complete_form_contract (test_forms.FormDefinitionTestCase.test_every_entry_declares_the_complete_form_contract) ... ok
test_every_station_file_loads_individually (test_forms.FormDefinitionTestCase.test_every_station_file_loads_individually) ... ok
test_locked_fields_create_neither_questions_nor_form_fields (test_forms.FormDefinitionTestCase.test_locked_fields_create_neither_questions_nor_form_fields) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.269s

OK
```

### Measured three-surface output

The measurement imported `load_fields`, `interview`, and `form` from the repository `src` tree, loaded `pipeline/_shared/forms`, grouped by `Field.station`, and printed the lengths of the station field list and both renderings. Its exact output was:

```text
01-research-question: fields=2 questions=2 form_fields=2
02-instrument: fields=4 questions=1 form_fields=4
03-ethics: fields=12 questions=5 form_fields=10
04-sampling: fields=11 questions=2 form_fields=11
05-pretest: fields=8 questions=1 form_fields=6
06-fieldwork: fields=7 questions=0 form_fields=6
07-analysis: fields=8 questions=0 form_fields=4
08-reporting: fields=7 questions=0 form_fields=5
TOTAL: fields=59 questions=11 form_fields=48
exit_code=0
```

These are generated counts, not estimates. Questions with a default are suppressed unless required. Locked fields contribute to config defaults but produce neither a question nor a visible form field.

### Fresh jury dry-run

The first module invocation omitted the README's source-path activation and failed before creating a workspace:

```text
> python -X utf8 -m researchcall demo --workspace out/jury-dry-run-20260802-codex --seed 42
C:\Program Files\Python312\python.exe: No module named researchcall
```

The documented source activation was then applied and the same unused workspace succeeded:

```text
> $env:PYTHONPATH='src'
> python -X utf8 -m researchcall demo --workspace out/jury-dry-run-20260802-codex --seed 42
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,"EXPIRED":4,"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
report=out\jury-dry-run-20260802-codex\report.md
exit_code=0
elapsed_seconds=5.903
```

`elapsed_seconds` was measured by the local process wrapper around the command. The output path is ignored by Git. No account, credential, SDK call, network request, or phone call was used.

### Final static and automated tests

```text
> python -X utf8 -m compileall -q src tests
exit_code=0; no output
```

```text
> python -X utf8 -m unittest discover -s tests -v
test_dependency_free_reader_preserves_inline_list_defaults (test_forms.FormDefinitionTestCase.test_dependency_free_reader_preserves_inline_list_defaults) ... ok
test_every_entry_declares_the_complete_form_contract (test_forms.FormDefinitionTestCase.test_every_entry_declares_the_complete_form_contract) ... ok
test_every_station_file_loads_individually (test_forms.FormDefinitionTestCase.test_every_station_file_loads_individually) ... ok
test_locked_fields_create_neither_questions_nor_form_fields (test_forms.FormDefinitionTestCase.test_locked_fields_create_neither_questions_nor_form_fields) ... ok
test_demo_runs_end_to_end_without_network (test_researchcall.ResearchCallTestCase.test_demo_runs_end_to_end_without_network) ... ok
test_duplicate_phone_cannot_create_two_person_attempts (test_researchcall.ResearchCallTestCase.test_duplicate_phone_cannot_create_two_person_attempts) ... ok
test_fixed_wording_filter_and_audit_schema_are_in_task (test_researchcall.ResearchCallTestCase.test_fixed_wording_filter_and_audit_schema_are_in_task) ... ok
test_fixture_keeps_raw_answer_separate_from_interpreted_category (test_researchcall.ResearchCallTestCase.test_fixture_keeps_raw_answer_separate_from_interpreted_category) ... ok
test_live_client_reads_bearer_only_from_calle_api_key (test_researchcall.ResearchCallTestCase.test_live_client_reads_bearer_only_from_calle_api_key) ... ok
test_live_mode_fails_before_client_creation_without_exact_intent (test_researchcall.ResearchCallTestCase.test_live_mode_fails_before_client_creation_without_exact_intent) ... error=Live mode requires --confirm-live "CALL 1" for this bounded quota
ok
test_live_rest_path_uses_activity_and_nested_result (test_researchcall.ResearchCallTestCase.test_live_rest_path_uses_activity_and_nested_result) ... ok
test_phone_validation_and_masking (test_researchcall.ResearchCallTestCase.test_phone_validation_and_masking) ... ok
test_random_draw_assigns_windows_and_every_sample_is_attempted_once (test_researchcall.ResearchCallTestCase.test_random_draw_assigns_windows_and_every_sample_is_attempted_once) ... ok
test_report_preserves_loss_structure_and_never_contains_phone_numbers (test_researchcall.ResearchCallTestCase.test_report_preserves_loss_structure_and_never_contains_phone_numbers) ... ok
test_sqlite_frame_source_is_opened_read_only (test_researchcall.ResearchCallTestCase.test_sqlite_frame_source_is_opened_read_only) ... ok
test_transcript_is_audited_in_memory_but_not_persisted (test_researchcall.ResearchCallTestCase.test_transcript_is_audited_in_memory_but_not_persisted) ... ok
test_withdrawal_erases_identifiers_and_excludes_record (test_researchcall.ResearchCallTestCase.test_withdrawal_erases_identifiers_and_excludes_record) ... ok

----------------------------------------------------------------------
Ran 17 tests in 7.660s

OK
exit_code=0
```

### Not executed in this run

- No CALL-E account registration, authentication, real call, `--live` execution, webhook, or CALL-E/AiRudder network request.
- No external message, upload, push, release, publication, pull request, submission, or video production.
- No service concurrency, voicemail, busy, no-answer, remote cancellation, quota-sharing, CI, or jurisdictional behavior was tested.

### Local commit gate

The requested local commit was attempted after the lock had been removed and the verified file list had been narrowed explicitly. Staging failed because this managed session exposes `.git` read-only:

```text
> git add -- EVIDENCE.md README.md _CODEX-PHASE-REPORT.md pipeline/_shared/OBERFLAECHE-UND-TEXT.md pipeline/_shared/forms/README.md pipeline/_shared/forms/analysis.forms.yaml pipeline/_shared/forms/ethics.forms.yaml pipeline/_shared/forms/fieldwork.forms.yaml pipeline/_shared/forms/instrument.forms.yaml pipeline/_shared/forms/pretest.forms.yaml pipeline/_shared/forms/reporting.forms.yaml pipeline/_shared/forms/research-question.forms.yaml pipeline/_shared/forms/sampling.forms.yaml src/researchcall/forms.py tests/test_forms.py
fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied
```

No alternative write path was used to bypass the repository-metadata restriction. No file was staged, no commit was created, and no push was attempted.

---

# EVIDENCE — workbench run, 2026-08-02

Building the bilingual web surface. **No real call, no CALL-E network request, no
account, no credential, no upload, no push.** Everything below was executed in this
repository; output is reproduced literally.

Baseline revision:

```text
> git log -1 --oneline
fbc9536 feat(forms): one definition, three ways in — form templates for all eight stations
```

## What the form definitions actually contain

Counted from `forms.load_fields()` at the start and again after the English text was
added; the numbers did not move, because only translations were inserted:

```text
> python -c "... forms.load_fields() ..."
01-research-question shown=2 locked=0 asked=2
02-instrument shown=4 locked=0 asked=1
03-ethics shown=10 locked=2 asked=5
04-sampling shown=11 locked=0 asked=2
05-pretest shown=6 locked=2 asked=1
06-fieldwork shown=6 locked=1 asked=0
07-analysis shown=4 locked=4 asked=0
08-reporting shown=5 locked=2 asked=0
total=59 shown=48 locked=11 asked=11
```

The interface renders these counts and no others; `tests/test_web.py` compares the
controls in the returned HTML against `forms.form()` per station and language.

## Translations

English `label_en` / `question_en` / `help_en` and option `label_en` were inserted into
all eight `*.forms.yaml` files by a one-off insert-only script with a hand-written
translation table. Nothing existing was rewritten: of the 49 lines the diff removes, all
49 reappear as the prefix of an added line (the option maps, which gained a key).

```text
> python manage_translations.py --check --fields
[ok] 59 form definitions carry every language.
[i] 70 interface key(s) in use, 70 in the table
[ok] every interface string has every language.
exit_code=0
```

## Test suite

```text
> python -m unittest discover -s tests
----------------------------------------------------------------------
Ran 42 tests in 13.236s

OK
exit_code=0
```

17 of these are the pre-existing tests, unchanged and still passing. 25 are new: 7 for
the language layer of the form definitions, 18 for the workbench.

One new test failed on first run and was corrected: `test_german_keeps_real_umlauts`
asserted that a capital `Ü` appears on the German station-1 page, which it has no reason
to. The assertion was wrong, not the page; it now checks for real `ä ö ü ß`, for the
absence of HTML entities, and for `abschließen` rather than `abschliessen`.

## Field phase, executed against fixtures

Nine records, drawn from a locally generated frame of fictitious reserved-range numbers,
processed one at a time through `runner.run_day` with `FixtureCallClient`:

```text
stream events: 10 | last: {'done': True, 'processed': 9, 'totals': {'BUSY': 1,
'CANCELED': 1, 'COMPLETED': 2, 'DECLINED': 1, 'EXPIRED': 1, 'FAILED': 1,
'NO_ANSWER': 1, 'VOICEMAIL': 1}}
GET /report -> 200
yield shown: 22.2%
phone numbers leaked into any page: False
```

The 22.2% completion yield is what these fixtures produce for nine records. It is a
property of the fixture file, not a measurement of anything real.

### Not executed in this run

- No CALL-E account, authentication, real call, `--live` path, webhook, or any network
  request to CALL-E/AiRudder. The web package does not import `LiveCallClient` and reads
  no credential; a test asserts both.
- No push, publication, pull request, upload, release, or video.
- No browser was driven. The interface was exercised through `fastapi.testclient`, so
  the HTML is verified as text; its appearance in a real browser is unverified.
- Concurrency, voicemail/busy/no-answer behaviour beyond fixtures, and every other
  service property listed in the earlier section remain unverified.

---

# Round two — the settings now act (2026-08-02)

Round one built the surface; this round connected it. Every claim below was produced by
running the code in this repository, offline, and is quoted as it appeared.

## Test suite

```text
81 passed, 1 warning, 365 subtests passed in 29.66s
```

Was 42 passed / 287 subtests before this round. `tests/test_instrument.py` is new
(34 tests): item grammar, skip rules, per-respondent order, conversation frame,
coding rules, contact rules against a live database, export, instrument check, and
the effect register. Five more were added to `tests/test_web.py`, among them one that
asserts the *absence* of an effect is visible on the control itself.

## Translation completeness

```text
[ok] 59 form definitions carry every language.
[i] 186 interface key(s) in use, 186 in the table
[ok] every interface string has every language.
```

118 new German strings were written by hand, including the sentence shown beside every
control. `manage_translations.dynamic_keys()` now also reads the effect register and the
instrument-check notes, so a new one of either cannot be forgotten.

## Command line, unchanged

```text
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,"EXPIRED":4,
"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
```

Same numbers as before the change: with the default of one call per person, 50 records
produce 50 attempts.

## A questionnaire built in the workbench, run end to end

Four items (dichotomous, scale, reversed scale, open with two probes), one skip rule,
randomised order, one extra attempt per person, twelve records:

```text
questions: 4 open: 1 minutes: 5
consent: Sie können das Gespräch jederzeit beenden, ohne einen Grund zu nennen.
         Möchten Sie an der Befragung teilnehmen?
prepared: {'frame': 60, 'drawn': 12, 'resumed': 0}
processed: 17 {'BUSY': 2, 'CANCELED': 1, 'COMPLETED': 4, 'DECLINED': 4, 'EXPIRED': 1,
'FAILED': 1, 'NO_ANSWER': 2, 'VOICEMAIL': 2}
included: 11 attempts: 16 repeated: 4
```

The spoken scale carries its poles:

```text
Wie zufrieden sind Sie mit dem Takt? Bitte antworten Sie auf einer Skala von 1 bis 5,
wobei 1 „sehr unzufrieden“ bedeutet und 5 „sehr zufrieden“.
```

The dataset, one row per person, with the reversed item carried twice:

```text
record,assigned_window,final_window,attempts,status,consent,asked_verbatim_reported,
wording_matched,q1,q2,q3,q3_recoded,q4_text,refusal_reason
1,evening,evening,1,COMPLETED,granted,1,1,yes,1,2,4,(fixture) free answer for q4,
2,morning,afternoon,2,NO_ANSWER,,,,,,,,,
3,morning,evening,3,DECLINED,declined,1,1,,,,,,(fixture) topic not relevant to me
```

Record 2 was dialled in the morning, did not answer, and was dialled again in the
afternoon. Record 3 declined, invited a later call, and was dialled twice more within the
configured limit of three.

## Instrument check, 20 dry-run interviews

```text
- Test interviews attempted: 20
- Interviews with consent granted: 5
- Results the schema rejected: 0
- asked_verbatim: 3 of 5 (60.0%)
- spoken_wording: 3 of 5 (60.0%)
- ethics_blocks_complete: 3 of 5 (60.0%)
- filters_respected: 10 of 10 (100.0%)
- syntactic marker: asked 5 times, returned untouched 5 times
- item order (randomised): 15 distinct orders
```

**60 %, not 100 %, is the point.** The fixture file deviates from the required wording in
some records on purpose; a check that scored perfectly would only prove that it measures
nothing. What it measures is the local harness — the dry run has no agent. Two criteria
are reported as not measurable rather than scored: unplanned follow-ups and the order the
agent really spoke in, both of which need a live transcript.

## A bug the dry run found

The first end-to-end run coded every scale answer as *outside the categories*. Cause: the
demo fixture carries answers for ids `q1`–`q3`, and an instrument built in the workbench
may use the same ids for entirely different items — `satisfied` landed in a five-point
scale. `FixtureCallClient` now uses a recorded answer only when it fits the item it is
being given to, unless a pattern asks for an out-of-category answer with
`allow_unlisted`. Without the run, the demo would have spent its time reporting a coding
problem that only the fixture had.

## Not executed in this round

- No CALL-E account, credential, real call, `--live` path, webhook, or network request.
  `network=disabled` above is the CLI stating its own transport.
- No push, publication, pull request, upload, release, or video.
- No browser. The interface was exercised through `fastapi.testclient`; its appearance in
  a real browser remains unverified, and design is explicitly the next agent's task.
- The German strings were written, not reviewed by a second person.
- Parallel forms, the L1–L5 disclosure catalogue, mail and colleague calls in the
  pretest, storage backends, calling hours and concurrency remain **recorded without
  effect** — 19 settings, each with its reason in `src/researchcall/effect.py` and shown
  beside its own control.
- Writing the register caught three of my own false claims: `reporting.findings_file`
  and `pretest.export_questionnaire` were classified as effective while nothing read
  them, and `fieldwork.keep_transcript` still is nothing but a switch with no wire.
  The first two were connected (a findings note at `/export/findings.md`, and the
  download that the export setting now actually governs); the third was moved to the
  honest column. This is the register working as intended: it is checkable, and it was
  checked against the code rather than against my memory of it.
- `sample.method: stratified` is **refused**, not silently drawn at random: the dry-run
  frame carries no stratifying attributes, and a random draw reported as stratified would
  be a method claimed but never run.

---

# Round two hardening and visual system — Codex rotation (2026-08-02)

This rotation made no real call, no CALL-E/AiRudder request, and no network request from
the workbench. It also made no push, upload, publication, release, or external contact.

## Actual verification

The normal PowerShell-backed command launcher was rejected before Python started:

```text
windows sandbox: runner failed during SpawnChild:
CreateProcessAsUserW failed: 5 (Zugriff verweigert)
```

A temporary repo-local import entry point then ran `compileall`, the complete `unittest`
discovery suite, `git diff --check`, and `git status` in an isolated Python process. Its
readback was:

```text
compileall_ok=True
tests_run=85
subtests_run=497
failures=0
errors=0
skipped=0
successful=True
git_diff_check_exit=0

Ran 85 tests in 21.692s
OK
```

The temporary entry point was removed after readback. Its ignored literal output remains
at `out/tests/codex-round2-verification.txt`.

## What the new regressions establish

- Locked field paths appear in none of the overview, station, instrument, pretest,
  fieldwork, report, or human-readable configuration HTML in either language. Locked
  defaults remain in the machine config, not as controls.
- Direct pretest and fieldwork actions enforce the same station gates as the navigation.
- Opening a prepared fieldwork page does not create an `EventSource` or continue work;
  continuation requires the explicit action.
- A completed fixture run writes `report.md`, and the written bytes equal `/report.md`.
- An existing field-phase database is preserved byte-for-byte when the current instrument
  or immutable sampling plan differs, and when resumability is switched off.

No browser was connected to this session. HTML responses and source were tested, but the
new visual system was not accepted from screenshots or a real interactive browser.

## Local commit attempt

After verification, the requested narrow staging command named only this rotation's eight
files. The sandbox rejected process creation before Git started:

```text
> git add -- EVIDENCE.md _CODEX-RUNDE2-REPORT.md src/researchcall/web/app.py
  src/researchcall/web/field_phase.py src/researchcall/web/locales/ui.json
  src/researchcall/web/render.py src/researchcall/web/workspace.py tests/test_web.py
windows sandbox: runner failed during SpawnChild:
CreateProcessAsUserW failed: 5 (Zugriff verweigert)
```

Nothing was staged, no commit was created, and no push was attempted.

---

# Test-mode station tour — Codex (2026-08-02)

This round added an off-by-default, bilingual test mode to the workbench. It opens all
eight station pages and the pretest/fieldwork prerequisite views only while active. The
normal sequential gate remains unchanged.

The tour state is separate from study state: 48 visible declared fields receive fixture
example values, while the 11 `locked: true` fields receive no example and remain absent
from forms, agent questions, and human-readable HTML. Test-mode fieldwork writes under
`test-mode-artifacts/`, not beside real-study artifacts. The web package still exposes no
live-call client, API-key path, or live flag.

## Actual verification

```text
tests_run=90
subtests_run=506
failures=0
errors=0
skipped=0
successful=True
```

The pre-existing 85 tests / 497 subtests stayed green; five tests and nine subtests were
added. A focused web run also completed with `Ran 32 tests ... OK`. In addition:

```text
python -X utf8 -m compileall -q src tests
exit=0

python -X utf8 manage_translations.py --check --fields
[ok] 59 form definitions carry every language.
[i] 193 interface key(s) in use, 205 in the table
[ok] every interface string has every language.

git diff --check
exit=0
```

`git diff --check` emitted only line-ending conversion warnings for tracked text files.

## Not executed

- No CALL-E account, credential, real call, `--live` path, webhook, or network request.
- No push, publication, pull request, upload, release, or external contact.
- No browser or screenshot acceptance; routes and rendered HTML were exercised through
  `fastapi.testclient`.

## Local commit attempt

The narrow staging attempt named only this round's eight files. Git could not write the
managed repository index:

```text
fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied
```

Nothing was staged and no local commit was created. The concurrent logo/banner files
were not included, and no push was attempted.

---

# Configuration layout stack — Codex (2026-08-03)

The configuration page now gives its JSON configuration and the recorded-only values
one full-width row each. Its dedicated `config-stack` grid replaces the shared
two-column `split` class on this page only; the paper styling and other split layouts
are unchanged.

## Actual verification

Before the change, `GET http://127.0.0.1:8020/config` returned HTTP 200 and rendered the
two areas inside `<div class="split">`. The shared CSS assigned the right column a width
of 290–370 px on viewports wider than 1100 px.

The completed test run used an isolated, subsequently removed directory inside the
repository because the runner could not write to the system Pytest temp directory:

```text
python -c "import sys, pytest; sys.path.insert(0, 'src'); raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--basetemp',sys.argv[1]]))" C:\_Local_DEV\repos\researchcall\.pytest-layout-6d17c5ff-4836-4ec8-bea0-edd52ba63d52

124 passed, 1 warning, 506 subtests passed in 28.53s
```

## Not executed

- No CALL-E account, credential, real call, `--live` path, webhook, or external network
  request was used.
- No push, publication, pull request, upload, release, or external contact was made.

---

# Current offline suite readback for DevPost — Codex (2026-08-04)

The operator re-ran the complete suite after the data-phase build and before updating
the active DevPost form:

```text
python -m pytest -q
190 passed, 1 warning, 506 subtests passed in 39.19s
exit=0
```

The only warning is the pre-existing Starlette `TestClient` / `httpx` deprecation
warning. No live call, network request, push, publication, upload or DevPost action was
performed. ResearchCall video v5 remained a local, unapproved composition during this
readback.
