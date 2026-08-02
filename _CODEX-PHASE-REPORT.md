# Codex phase report — form surfaces

Date: 2026-08-02

Hackathon phase: 4 (build) completed for this scope; phase 5 (acceptance and evidence) prepared for user review.

Mode: local dry-run only

## Outcome

- Added one form definition for each previously uncovered station: research question, instrument, conversation/ethics frame, pretest, fieldwork, analysis, and reporting.
- Completed the existing sampling definition from its station skill and config, and moved its misplaced consent setting into the ethics definition.
- Every entry explicitly carries `field`, `station`, `label`, `question`, `type`, `options`, `default`, `help`, `required`, and `locked`.
- Locked methodological and ethical requirements generate neither agent questions nor UI fields. They remain present in config defaults.
- Integrated the previously untracked `src/researchcall/forms.py` and `pipeline/_shared/OBERFLAECHE-UND-TEXT.md` work rather than replacing it.
- Updated the English README to describe ResearchCall as an eight-station research procedure usable through a skill, config, and UI-ready form descriptors. It explicitly says that no graphical frontend is bundled.
- Added the access-free jury dry-run from the repository source tree.

## Source-bound decisions

- Station 5 is `05-pretest`, because `pipeline/SKILL.md`, the folder, `SKILL.md`, and `config.template.yaml` agree on that identity. The prompt's “05 Ethik/Einwilligung” wording was treated as a numbering mismatch, not as authority to duplicate the ethics station.
- No standalone recording-notice key exists in the station skills or configs, so none was invented. Recording or transcription disclosure is part of the required `ethics.privacy_text`; transcript retention remains the separate `fieldwork.keep_transcript` decision.
- Audit-log containers such as `revisions` and `rule_changes` were not turned into user settings. Repeatable decisions such as hypotheses, items, and jump rules use table fields.

## Actual runs and output

Form measurement from `load_fields()`, `interview()`, and `form()`:

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

The first focused regression run found a real dependency-free parser defect:

```text
Ran 4 tests in 0.557s
FAILED (errors=2)
AttributeError: 'NoneType' object has no attribute 'append'
```

After the narrow parser fix:

```text
Ran 4 tests in 0.269s
OK
```

Final static and full-suite result:

```text
python -X utf8 -m compileall -q src tests
exit_code=0; no output

python -X utf8 -m unittest discover -s tests -v
Ran 17 tests in 7.660s
OK
exit_code=0
```

Fresh jury dry-run after applying the README's `PYTHONPATH=src` step:

```text
mode=dry-run transport=fixture network=disabled
frame_imported=200 sample_drawn=50 attempts=50
terminal_statuses={"BUSY":5,"CANCELED":4,"COMPLETED":14,"DECLINED":9,"EXPIRED":4,"FAILED":4,"NO_ANSWER":5,"VOICEMAIL":5}
report=out\jury-dry-run-20260802-codex\report.md
exit_code=0
elapsed_seconds=5.903
```

The preceding attempt without source activation failed with `No module named researchcall` and created no workspace. Both outcomes are retained in `EVIDENCE.md`.

## Gates and limits

- The user-provided balance was `-0.05 USD`; it was not queried or changed. No real call, `--live` run, account operation, authentication, webhook, or CALL-E/AiRudder network request occurred.
- No push, remote mutation, release, publication, pull request, submission, video production, or external message occurred.
- Service concurrency, non-completed live outcomes, cancellation, quota sharing, CI, legal approval, and competition acceptance remain unverified.
- All writes stayed inside this repository. The disposable dry-run artifacts are under ignored `out/`.
- The requested local commit stopped at the managed filesystem gate: `git add` returned `fatal: Unable to create 'C:/_Local_DEV/repos/researchcall/.git/index.lock': Permission denied`. Nothing was staged or committed.

## User decisions required next

1. Review the measured evidence and decide whether the phase-5 gate “evidence stands” is approved before media work begins.
2. Decide whether a future station-config revision should add a dedicated, non-optional recording-notice key; the current source-bound model places that content inside `ethics.privacy_text`.
3. Create the local commit in a session with write access to `.git`, or commit the verified working tree manually. No push is required or authorized.
4. Retain control of every live call and every outward action: repository publication, video upload, pull request, and hackathon submission.

The local commit attempt happened after the final test and hygiene checks. The content is ready, but the commit remains blocked solely by the repository-metadata permission above.
