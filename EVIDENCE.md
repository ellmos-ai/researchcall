# EVIDENCE — ResearchCall

Date: 2026-08-01

This file records observed local evidence. It does not claim a live call, remote acceptance, publication, or legal approval.

## Executed

Environment check:

```text
> python --version
Python 3.12.10
```

Static compilation check:

```text
> python -m compileall -q src tests
exit code 0; no output
```

The first full test run did not pass. Seven tests ended in Windows `PermissionError: [WinError 32]` during temporary-directory cleanup because `initialize()` and the demo treated the SQLite context manager as if it closed the connection. The connection lifecycle was corrected. The final repeated command produced:

```text
> python -m unittest discover -s tests -v
test_demo_runs_end_to_end_without_network (test_researchcall.ResearchCallTestCase.test_demo_runs_end_to_end_without_network) ... ok
test_duplicate_phone_cannot_create_two_person_attempts (test_researchcall.ResearchCallTestCase.test_duplicate_phone_cannot_create_two_person_attempts) ... ok
test_fixed_wording_filter_and_audit_schema_are_in_task (test_researchcall.ResearchCallTestCase.test_fixed_wording_filter_and_audit_schema_are_in_task) ... ok
test_live_mode_fails_before_client_creation_without_exact_intent (test_researchcall.ResearchCallTestCase.test_live_mode_fails_before_client_creation_without_exact_intent) ... error=Live mode requires --confirm-live "CALL 1" for this bounded quota
ok
test_phone_validation_and_masking (test_researchcall.ResearchCallTestCase.test_phone_validation_and_masking) ... ok
test_random_draw_assigns_windows_and_every_sample_is_attempted_once (test_researchcall.ResearchCallTestCase.test_random_draw_assigns_windows_and_every_sample_is_attempted_once) ... ok
test_report_preserves_loss_structure_and_never_contains_phone_numbers (test_researchcall.ResearchCallTestCase.test_report_preserves_loss_structure_and_never_contains_phone_numbers) ... ok
test_sqlite_frame_source_is_opened_read_only (test_researchcall.ResearchCallTestCase.test_sqlite_frame_source_is_opened_read_only) ... ok
test_withdrawal_erases_identifiers_and_excludes_record (test_researchcall.ResearchCallTestCase.test_withdrawal_erases_identifiers_and_excludes_record) ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.852s

OK
```

The end-to-end verification ran from `src` so the package could be invoked without installing anything outside this repository:

```text
> python -m researchcall demo --workspace ../out/verification-final-20260801 --seed 42
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,"EXPIRED":4,"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
report=..\out\verification-final-20260801\report.md
```

The generated SQLite state was inspected read-only:

```text
frame=200
sample=50
attempt=50
retry_duplicates=0
missing_timestamps=0
excluded_withdrawals=4
```

Database integrity check:

```text
> PRAGMA quick_check
ok
```

The generated report was also checked programmatically:

```text
unmasked fixture phone pattern present: false
time-window outcome table present: true
NO_ANSWER / DECLINED / BUSY / VOICEMAIL distinctions present: true
fixture-only wording caveat present: true
```

## Assumptions recorded

- The live adapter follows the locally reviewed CALL-E Developer API example: `POST /v1/calls`, then bounded polling of `GET /v1/calls/{id}`. Exact response shapes remain unverified without an account.
- `de-DE` is used as the recipient locale because Germany and German are documented as supported; this exact live locale value was not tested.
- A withdrawal keeps an anonymized attempt tombstone (randomized time window, timestamps, terminal operational status) so the one-attempt audit remains provable. Direct identifiers, structured response, and provider run ID are erased, and the tombstone is excluded from analysis.
- The returned `asked_verbatim` and actual-wording fields are remote-agent evidence, not independent proof. A transcript review would still be required for a live standardization claim.
- Calls are serial because the concurrency limit is not documented. Transcript growth during an active call is not assumed and is not used.

## Not executed

- No CALL-E account registration or authentication.
- No real phone call.
- No `--live` execution and no network request to CALL-E/AiRudder.
- No live transcript or wording-fidelity review.
- No concurrency, webhook, remote cancellation, or mid-call transcript test.
- No CI run.
- No push, remote mutation, release, publication, pull request, or video.
- No local commit could be created in this session. `git add -- EVIDENCE.md README.md pyproject.toml src tests` failed with `fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied`. The alternative local Git command service was rejected before execution. The working tree therefore remains uncommitted.

The initial PowerShell sandbox runner also failed before process start with `CreateProcessAsUserW failed: 5 (Zugriff verweigert)`. Read-only FileCommander/Node-backed tooling was used instead; repository writes were made with patch operations only.

Early test runs used Python's default temporary directory and cleaned those temporary files automatically. The test harness was then corrected to place all test databases under the repository's ignored `out/tests/` directory, matching the repository-only write boundary for the final run.
