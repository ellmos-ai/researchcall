# ResearchCall data flow

Status: code review on 2026-08-02. No live call was placed. This document distinguishes the offline web workbench from the separately gated live CLI path.

In the table, “leaves the computer” means leaving the machine that runs the Python process. If the workbench is remotely hosted, browser-to-host form submissions already disclose study data to the app operator and its infrastructure even though the workbench has no third-party/live transport.

## Operating modes

- The web workbench is fixture-only. Its routes cannot instantiate `LiveCallClient`; it uses a local workspace and vendored static assets.
- The CLI is dry-run by default. Live calls require `--live`, an exact bounded confirmation, a consent attestation and `CALLE_API_KEY`.
- The workbench binds to `127.0.0.1` by default, but `RESEARCHCALL_HOST` can change the binding. Loopback is not authentication or tenant isolation.

## Data switchboard

| Data | Collection and use | Storage | Retention implemented in code | Who can see it | Leaves the computer? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Workbench study design: research question, questionnaire/items, consent wording, ethics/sampling/analysis/reporting settings, completion times and amendments | Builds the eight-station plan and exact call task | One shared `workspace.json` in `RESEARCHCALL_WORKSPACE` (`out/workbench` by default) | No automatic expiry/delete workflow was found | Every visitor able to reach the unauthenticated workbench routes | No third-party request by the workbench code; infrastructure logging is deployment-specific | `src/researchcall/web/app.py:35-62, 135-312`; `src/researchcall/web/workspace.py:1-125` |
| Imported sampling-frame reference and raw E.164 phone | Identifies people, prevents duplicates, draws a sample and supplies the call destination | `frame.external_ref` and `frame.phone_e164` in the selected SQLite database (`researchcall.db` CLI default) | Kept until database removal or targeted withdrawal; no general timed expiry | CLI/operator and any application with database access | No in fixture mode; the selected raw number leaves in live mode | `src/researchcall/cli.py:34-78, 143-168`; `src/researchcall/sampling.py:29-76`; `src/researchcall/database.py:21-28` |
| Source CSV or source SQLite sampling frame | Supplies external references and phone numbers | Read from the operator-provided source path; ResearchCall also imports the selected columns into its database | Source-file retention/deletion is outside ResearchCall; the app does not remove the source | Operator/filesystem permissions | No transfer by this code | `src/researchcall/cli.py:43-49, 150-160`; `src/researchcall/sampling.py:17-49` |
| Study and sample plan | Stores study key/title/questionnaire JSON, drawn sample, assigned time window and exclusions | `study` and `sample` tables in SQLite; the fixture workbench uses `fieldwork.db` inside its artifact directory | No automatic timed expiry found | Operator; in a hosted workbench, all visitors can reach shared study/config/report routes | No transfer beyond the Python host in fixture mode; questionnaire/task leaves in live mode | `src/researchcall/database.py:12-43`; `src/researchcall/web/field_phase.py:37-55, 169-257` |
| Attempt metadata | Attempt number/window, timestamps, status, CALL-E run ID, idempotency key and detail JSON | `attempt` table in SQLite | No timed expiry; targeted withdrawal clears run ID and replaces detail JSON with a purge marker | Operator and shared report/workbench routes | Run ID/status originate from CALL-E in live mode | `src/researchcall/database.py:45-57`; `src/researchcall/runner.py:106-192, 309-323` |
| Live call request | Raw selected phone, exact questionnaire/consent task, result schemas, locale and pseudonymous sample ID metadata | Sent to CALL-E; response is processed in memory before selected fields are persisted | Provider-side retention is not specified in this repository | Participant, CALL-E and CLI process | **Yes, live CLI only:** to the configured URL (default HTTPS); the code does not enforce an HTTPS scheme for overrides | `src/researchcall/calls.py:218-261, 324-367`; `src/researchcall/cli.py:169-194` |
| Structured survey response | Consent state, raw and categorized answers, spoken wording/fidelity fields, refusal/callback/withdrawal fields | `response.structured_json` plus selected consent/fidelity fields in SQLite | No general timed expiry; withdrawal deletes the response | Operator; unauthenticated workbench report/export routes expose the current shared fixture study | Returned from CALL-E in live mode; no additional transfer at local save | `src/researchcall/database.py:59-69`; `src/researchcall/runner.py:248-349` |
| Call transcript | Used in memory to verify transcript format and whether required wording was spoken | Full transcript is **not persisted**; only flags such as availability/format and `transcript_persisted=false` enter attempt detail JSON | Process-memory lifetime; provider retention is unknown | CLI process and CALL-E; not included in local database/export by this code | **Yes in live mode:** received from CALL-E | `src/researchcall/calls.py:368-400`; `src/researchcall/runner.py:277-307` |
| Withdrawal data | External reference supplied to the CLI or withdrawal requested in the structured response | Withdrawal replaces the external reference with a local marker, nulls the phone, excludes samples, deletes responses and clears provider run IDs/detail | This local targeted purge is immediate on successful processing. Sample/attempt rows, timestamps, status and the idempotency key remain; the code does not request provider-side deletion | Operator/database; CALL-E may still hold previously transmitted data under provider rules | No new transfer by purge, but the retained idempotency key was previously sent to CALL-E | `src/researchcall/runner.py:106-192, 195-245, 325-326`; `src/researchcall/cli.py:204-207`; `src/researchcall/calls.py:324-367` |
| Dataset, free-text, codebook, findings and report output | Analysis and reporting | Web exports are generated in memory and returned; `report.md` is written in the workbench artifact directory; CLI report is printed or written to an operator path | File copies remain until user/operator deletion; no timed expiry | Anyone reaching unauthenticated web export/report routes; recipients of downloaded files | No automatic third-party transfer | `src/researchcall/export.py:1-154`; `src/researchcall/web/app.py:418-467`; `src/researchcall/web/field_phase.py:299-356`; `src/researchcall/cli.py:195-203` |
| Language preference | Selects interface language | `researchcall_lang` cookie | One year | Browser and app host | Sent with requests to the app host | `src/researchcall/web/app.py:35-40, 92-111` |
| CALL-E API key/base URL | Authenticates live CLI requests | Process environment only | Process/environment lifetime | CLI process; no web route accepts or stores a key | **Yes, live CLI only:** credential used for authorization | `src/researchcall/calls.py:218-244`; `src/researchcall/cli.py:169-194` |

## Export boundary

The dataset and free-text exporters use a pseudonymous sample/record number and exclude withdrawn records; they do not export phone numbers or external references. Free-text answers can nevertheless identify a person from their content and remain personal data unless genuinely anonymised.

Evidence: `src/researchcall/export.py:1-154`; `src/researchcall/reporting.py`.

## Important boundaries

- Pseudonymous sample IDs are still linked to the identifiable sampling frame inside the same database. They are not anonymous merely because an export omits the phone number.
- Questionnaire topics are configurable. The repository cannot prove that a future study avoids health, political, religious or other special-category data.
- The repository specifies neither CALL-E-side retention nor the legal entity, actual processing countries, subprocessors or transfer safeguards for the configured endpoint. Obtain these facts contractually.
- Browser, reverse-proxy, operating-system and infrastructure logs are deployment facts and must be added to the final data inventory and privacy notice.

See `HOST-READINESS.md` for the multi-user gap and `PRIVACY-TEMPLATE.md` for an operator-owned notice template.
