# ResearchCall round 2 report — functional hardening and visual system

Date: 2026-08-02

Mode: local fixture-only workbench; no call, network request, push, upload, or publication

## Handoff readback

No file with `RUNDE2` in its name existed when this round started. The only root-level
file matching `REPORT` was `_CODEX-PHASE-REPORT.md`. It documents the earlier form
surface phase, but it does not contain the announced Opus concept-versus-current table
or a design handoff. This round therefore used the product concept, the research master
skill, the eight station form definitions, and the code's effect register as the
source-bound gap list. The later closeout read of `EVIDENCE.md` did contain Opus' section
“Round two — the settings now act”; its explicit `recorded without effect` list confirmed
the same remaining gaps, but there was still no separate comparison table or design
handoff file.

## Functional work

- Removed all locked-setting disclosure from rendered HTML. The overview no longer
  counts the hidden frame, station pages no longer mention it, and the human-readable
  configuration view is built only from visible form definitions. Locked defaults stay
  in the machine configuration returned by `/config.json`, where the pipeline needs
  them; they never become controls.
- Closed a false gate: direct POSTs to the instrument check and field-phase preparation
  now require completion through stations 5 and 6 respectively. The navigation and the
  action routes enforce the same sequence.
- Closed an implicit side effect: reopening a prepared field-phase page no longer starts
  or resumes fixture processing. It shows an explicit “continue” action; only that click
  creates the event stream.
- Closed a data-loss path: a prepared field-phase database is never deleted by the web
  interface. Turning resumability off now refuses replacement and tells the researcher
  to use a new workspace.
- Added resume integrity: the stored questionnaire and immutable sampling plan are
  compared with the current plan. A changed instrument, sample size, method, time-window
  set, assignment mode, or run rule cannot silently continue against old sampled data.
- Connected the existing report writer to the completed fixture run. `report.md` is now
  actually written before the final progress event. Earlier workspaces without that file
  are labelled as a preview rather than described as written output.
- Kept the honesty layer for controls that still have no reader. Their fields remain
  visible because they come from the YAML, but each is marked `recorded only` beside the
  control and its reason is generated from `effect.py`.

## Deliberately not functional

The following settings still record intent but do not perform the advertised external or
future capability: parallel questionnaire forms; ethics policy-file loading and the L1–L5
catalogue; external sampling-frame import in the web workbench; CALL-E concurrency and a
clock-based scheduler; reviewer email/calls/self-call; file-per-record storage and a
per-study storage path; persisted transcripts and live polling; model-based metaphor,
framing, worldview, or inter-rater analysis; manuscript templates, bilingual report
generation, and publication/upload. The interface says this at the point of decision.
No placeholder button was added for any of them.

## Visual work

- Replaced the warm editorial/serif styling with a restrained research-workbench system:
  Segoe/system sans typography, compact controls, squared panels, tabular numbers, and
  dense but readable spacing for long station forms.
- Took the palette from the ResearchCall video without copying its promotional treatment:
  deep navy `#0b0f19`/`#0f172a`, slate `#1e293b`, measured sky-blue `#38bdf8`, and a cool
  paper workspace. There are no gradients, hero cards, or marketing calls to action.
- Made the research pipeline persistent and legible with a sticky dark station rail,
  completion count, current-station marker, and a compact horizontal form on narrow
  screens.
- Improved data-reading surfaces: sticky table headers, grid-based metric cells, stronger
  input focus, and a dark monospaced field log that visually matches the video evidence
  screens.

No browser was connected to this session, so no screenshot-based visual acceptance is
claimed. The source and rendered-response tests were checked; live visual inspection on
port 8020 remains for the design finisher.

## Measured verification

The normal shell launcher was blocked before process creation by the Windows sandbox
(`CreateProcessAsUserW failed: 5`). A temporary repository-local verification entry point
therefore ran the same Python suite in an isolated Python process and was removed after
readback.

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

The detailed ignored log is `out/tests/codex-round2-verification.txt`.

## Local commit gate

The requested explicit staging command was attempted after verification:

```text
git add -- EVIDENCE.md _CODEX-RUNDE2-REPORT.md src/researchcall/web/app.py
  src/researchcall/web/field_phase.py src/researchcall/web/locales/ui.json
  src/researchcall/web/render.py src/researchcall/web/workspace.py tests/test_web.py
```

The Windows sandbox rejected process creation before Git started:

```text
CreateProcessAsUserW failed: 5 (Zugriff verweigert)
```

Nothing was staged and no local commit was created. No alternate process tool was used
to bypass the managed `.git` boundary, and no push was attempted.

## Recommendations for agy's design finish

1. Restart/reload the server on port 8020, then inspect overview, the long Instrument and
   Ethics forms, Sampling, Analysis, the prepared-fieldwork state, and a completed report
   at desktop and narrow widths. Do not claim visual acceptance from the source alone.
2. Keep the current visual boundary: this is a dense research instrument, not a landing
   page. Refine rhythm, alignment, focus states, and long-list scanning; do not add hero
   sections, promotional gradients, oversized cards, or HungryCall-style urgency.
3. Verify that the sticky rail and sticky table headings do not collide with the sticky
   header, especially at browser zoom levels above 100% and on a short viewport.
4. Preserve the YAML-only control contract and the negative locked-field regression.
   Design changes must not hard-code a form field, surface a locked path, or remove the
   `recorded only` truth labels from settings that still have no reader.
5. Keep every new interface string in both `en` and `de`, and check German text with real
   UTF-8 umlauts.
