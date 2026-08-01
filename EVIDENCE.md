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
