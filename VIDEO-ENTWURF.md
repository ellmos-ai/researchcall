# ResearchCall demo video draft

**Status:** Concept only; no video, audio, or synthetic product footage is produced by this document.  
**Target runtime:** 2:55, with a hard final-export ceiling of 2:59.  
**Language:** English voiceover and English on-screen editorial text. Existing German questionnaire text may remain visible as authentic product input.  
**Capture principle:** The recommended cut uses fresh screen recordings of the real CLI, source, tests, and generated report on the development PC. Every product claim below is tied to repository behavior or explicitly labelled as a limitation.

## 1. Storyline

Telephone interviewing is an established but expensive research method, and replacing interviewers with a calling language model could make it cheaper while quietly destroying the standardization that makes a survey useful. The story opens on the most intuitive source of bias: calling only in the morning overrepresents people who are available then, so a topline such as “312 reached” hides more than it reveals. ResearchCall changes the unit of evidence by randomizing a morning, afternoon, or evening window at sample draw, allowing one timestamped attempt per selected record, and retaining distinct terminal outcomes. A real offline run then turns 200 fictitious frame records into a sample of 50 and produces a report that exposes the loss structure by assigned window. The demo widens from nonresponse to auditability: fixed questions, raw answers beside interpreted categories, consent, withdrawal, and wording checks remain inspectable rather than being flattened into a success count. It closes honestly: the dry-run proves the local workflow and report, while acoustic word-for-word delivery is not claimed as verified.

## 2. Storyboard

| Time | What is visible on screen | Exact English voiceover | Competition criterion |
| --- | --- | --- | --- |
| 0:00–0:15 | Fresh screen recording of the generated Markdown report, already positioned on **Fieldwork summary**. A restrained editorial overlay asks: **“What does ‘312 reached’ hide?”** A small persistent label reads **“OFFLINE FIXTURE DEMO”**. | “Telephone interviewing is established, useful, and expensive. A language model could make fieldwork cheaper. It could also destroy the methodology that makes the answers worth using.” | Real World Impact; Quality of Idea |
| 0:15–0:36 | The report remains real and readable while a simple clock overlay marks morning, afternoon, and evening. The cursor settles on the report’s statement that recorded attempts are never retried. The number 312 remains clearly editorial, not presented as ResearchCall output. | “Call only in the morning and you disproportionately reach people who are available in the morning. Report only ‘three hundred and twelve reached,’ and nobody can judge the resulting bias. Availability has silently become selection.” | Real World Impact; Quality of Idea |
| 0:36–1:00 | Real terminal capture from the repository root: type and run `python -m researchcall demo --workspace out/video-demo --seed 42`. Hold on the actual lines `mode=dry-run transport=fixture network=disabled`, `frame_imported=200 sample_drawn=50 attempts=50`, the terminal-status JSON, and the report path. Label: **“LIVE SCREEN CAPTURE — DRY RUN — NO ACCOUNT / NO NETWORK / NO CALL COST”**. | “ResearchCall starts from a different premise. In this live screen capture, the built-in demo imports two hundred fictitious records, draws fifty, assigns their fieldwork, processes every selected record through local fixtures, and writes the report. No account, network request, or call cost is involved.” | Technical Implementation; Product Experience and Demo |
| 1:00–1:24 | Real editor capture: briefly show `sampling.py` at the seeded random draw and `rng.choice(windows)`, then `database.py` at the unique attempt constraint, and `runner.py` at `started_at` and terminal completion. End on a terminal readback from the generated database showing 50 attempts, 50 non-empty start timestamps, and 50 non-empty end timestamps. | “At draw time, each sampled record receives a randomized morning, afternoon, or evening window. The database permits one attempt per sample record. The runner writes a start timestamp before transport and an end timestamp on every terminal, failed, or interrupted result.” | Quality of Idea; Technical Implementation |
| 1:24–1:57 | **Strongest scene.** Open the newly generated `out/video-demo/report.md` in Markdown preview and slowly pan across **Outcome structure by assigned time window**. Highlight the window rows first, then the separate `NO_ANSWER`, `DECLINED`, `BUSY`, and `VOICEMAIL` columns. Keep the actual fixture counts visible. Finish on the report’s interpretation rule. | “This is the methodological payoff. Outcomes stay attached to the randomized time window. ‘No answer’ remains a time-of-day availability signal. ‘Declined’ remains active refusal. Busy and voicemail remain separate. ResearchCall does not collapse them into generic loss. The report also keeps answer distributions by window and labels every difference descriptive, not statistically significant. Now nonresponse is visible, inspectable, and reportable.” | Real World Impact; Quality of Idea; Product Experience and Demo |
| 1:57–2:20 | Real editor and report capture: show the fixed German questionnaire, the quoted `say exactly` task construction, and the schema fields `raw_answers`, `answers`, `consent`, `withdrawal_requested`, and `spoken_wording`. Cut to **Raw-answer audit** in the report; do not reveal any raw response text. | “Standardization is more than outcome codes. ResearchCall places consent and fixed questions in quoted task text, keeps the participant’s raw words beside each interpreted category, and records consent and withdrawal. Aggregate reports expose raw-answer coverage without printing private response text.” | Quality of Idea; Technical Implementation |
| 2:20–2:42 | Hold on the generated report’s **Wording fidelity** section, where the fixture-only warning and zero transcript audits are visible. Add a two-line editorial overlay: **“TEXT LEVEL: STRONGLY INDICATED”** and **“ACOUSTIC FIDELITY: NOT VERIFIED”**. Do not play reconstructed, synthetic, or operator-remembered call audio. | “The wording claim has a deliberate limit. Text-level evidence strongly indicates that double-quoted questions pass through verbatim. Acoustic fidelity is not verified. The tool records returned wording and can audit a final transcript, but this video does not present word-for-word spoken audio as proven.” | Technical Implementation; Product Experience and Demo |
| 2:42–2:55 | Real terminal capture of `python -m researchcall --help`, followed by a tight editor view of the live gates: `--live`, exact `--confirm-live "CALL N"`, `--consent-attested`, E.164 validation, and environment-only `CALLE_API_KEY`. Close on the title **“ResearchCall — make survey bias auditable.”** | “Offline is the default. Live calls require bounded intent, consent attestation, a valid number, and an environment-only key. ResearchCall makes a survey’s weaknesses visible—not just its completed calls.” | Technical Implementation; Product Experience and Demo; Real World Impact |

The total planned runtime is 175 seconds. During editing, shorten pauses or trims rather than speeding the narration; the exported master must remain below three minutes.

## 3. Strongest single scene

**Scene 5, 1:24–1:57: the real outcome-by-randomized-window table.** It compresses the entire contribution into one functioning product view: the randomized exposure variable is visible in the rows, the distinct mechanisms of nonresponse are visible in the columns, and the fixture counts prove that the report is generated rather than illustrated. It simultaneously communicates real-world research bias, the reusable methodological idea, non-trivial implementation, and an understandable product result.

## 4. Thumbnail ideas

1. A crop of the real time-window outcome table behind the headline **“312 reached. But who was missed?”**
2. The real report table with morning, afternoon, and evening rows color-framed, plus the headline **“Make survey bias visible.”**
3. A split view of the real dry-run terminal output and report, connected by **“200 → 50 → auditable nonresponse.”**

## 5. What the video does not show, and why

- **No claim of acoustically verified word-for-word delivery.** At the text-output level, the available evidence strongly indicates that double-quoted questions are passed through verbatim. Acoustic fidelity is **not verified**, so the video must not present it as proven, play reconstructed audio, or use a checkmark beside a spoken-word claim.
- **No real call in the recommended cut.** The complete story can be demonstrated through the local fixture path without an account, network access, or cost. This also keeps the capture reproducible before project live calls are authorized.
- **No fabricated CALL-E interface or progress bar.** The project is a CLI plus Markdown report, and measured service behavior says nonterminal `status` can remain `PREPARING` while `activity` changes. A polished dashboard would suggest a product surface that does not exist.
- **No implication that fixture outcomes prove provider behavior.** `NO_ANSWER`, `DECLINED`, `BUSY`, and `VOICEMAIL` are exercised locally; their real service behavior has not been verified in this repository run.
- **No parallel-call claim.** The live adapter dispatches serially, while the provider’s concurrency limit remains unmeasured.
- **No retry, daemon, hidden schedule, or multi-day automation.** The one-attempt rule and host-triggered bounded quotas are intentional parts of the methodology and safety design.
- **No names, unmasked phone numbers, raw response text, access keys, or full transcripts.** The demo uses fictitious fixture data and aggregate output only.
- **No causal or statistical-significance claim from the fixture table.** The counts demonstrate reporting structure, not population findings.
- **No claim of CI, publication, competition acceptance, legal approval, or completed video production.** Those outcomes are outside the verified repository evidence and outside this draft.

If a future cut adds footage from an authorized real call, that scene must be visibly labelled **“RECORDED REAL CALL — DATE — AUTHORIZED PARTICIPANT”** for its full duration. It must use masked identifiers and may show only verified, consented material. It cannot replace the acoustic-fidelity caveat unless the recording itself is reviewed against the exact questionnaire wording.

## 6. Recording list

### Preparation before capture

- Use the actual development PC at 1920×1080 or higher, with a terminal and editor font large enough to remain readable after a 1080p export.
- Work only in this repository. Use the installed editable package or the verified module invocation from the repository root.
- Confirm that `CALLE_API_KEY` and `CALLE_BASE_URL` are not displayed. Do not open environment files, secrets, real contact sources, or a database containing real people.
- Reserve a fresh ignored output path such as `out/video-demo`; it must not exist before the take because the demo intentionally refuses to overwrite prior state.
- Keep `src/researchcall/fixtures/questionnaire.de.json`, `sampling.py`, `database.py`, `runner.py`, `questionnaire.py`, and the generated `report.md` ready in editor tabs.
- Prepare one terminal-only SQLite readback that prints aggregate timestamp completeness from the generated database and no identifiers or phone fields; rehearse it before recording.
- Set capture audio to narration only. Disable notifications and hide unrelated windows, paths, usernames, tokens, and repository history.

### Capture order

1. **Report opening plate — dry-run:** after generating the report, record the Fieldwork summary for scenes 1 and 2; add the “312 reached” question only as an editorial overlay in post-production.
2. **Fresh demo execution — dry-run:** record the full terminal command and its real output for scene 3. Do not cut away before `network=disabled`, the 200-to-50 counts, terminal statuses, and report path are readable.
3. **Sampling and attempt implementation — dry-run code path:** record the seeded draw and randomized window assignment in `sampling.py`, the unique attempt constraint in `database.py`, and timestamp handling in `runner.py` for scene 4.
4. **Timestamp aggregate readback — dry-run:** against the just-created fixture database, record an aggregate-only query confirming attempt, non-empty start, and non-empty end counts; show no sample IDs or phone columns.
5. **Outcome table — dry-run:** record a slow, steady pan across the actual generated time-window table and interpretation rule for scene 5. Capture at native scale so every status label and fixture count remains legible.
6. **Questionnaire and schema — dry-run implementation:** record the real questionnaire, quoted-task construction, result-schema fields, and Raw-answer audit for scene 6; never open persisted raw-answer values.
7. **Wording limitation — dry-run:** record the generated fixture report’s Wording fidelity section for scene 7, including “Only fixture evidence is present” and the zero transcript-audit counts.
8. **CLI and safety close — dry-run plus uninvoked live path:** record `python -m researchcall --help`, then the source-defined live gates and key handling for scene 8. Do not execute `--live`.
9. **Test evidence — dry-run, optional B-roll:** record a fresh `python -m unittest discover -s tests -v` run for short inserts only if it passes during capture. Do not reuse the historical 13-test count as though it were a current run.
10. **Real-call capture — not required for this storyboard:** no scene in the recommended 2:55 cut needs a real call. If one is later commissioned, obtain explicit authorization, record it separately, mask all identifiers, apply the full-duration recorded-call label above, and retain the acoustic-fidelity caveat until the audio has actually been checked.

### Scene provenance summary

| Scenes | Provenance | Real call required? |
| --- | --- | --- |
| 1–7 | Fresh screen recording of the fixture demo, generated report, and the code path that produced it | No |
| 8 | Fresh screen recording of CLI help and source-defined safety gates; live mode remains uninvoked | No |
| Optional test B-roll | Fresh local test run, used only if it passes during capture | No |
| Optional future CALL-E insert | Newly recorded, authorized, masked real call with a persistent recording label | Yes |
