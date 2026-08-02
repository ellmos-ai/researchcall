# Privacy notice template — ResearchCall

> **Template only — adaptation required.** This is not a deployable participant information sheet or privacy notice and is not legal advice. The controller must replace every `[REPLACE: ...]` marker, remove inapplicable options, verify provider facts and obtain study-specific legal/ethics review before processing real participant data.

Last updated: `[REPLACE: date]`<br>
Study title/reference: `[REPLACE]`

## 1. Controller and study contacts

Controller: `[REPLACE: institution/legal person deciding the study purposes and means]`<br>
Address: `[REPLACE]`<br>
Principal investigator/contact: `[REPLACE]`<br>
Privacy contact: `[REPLACE]`<br>
Data protection officer, if applicable: `[REPLACE or remove]`<br>
Ethics approval/reference, if applicable: `[REPLACE or explain why not applicable]`

Infrastructure hosting provider: `[REPLACE: provider, address and role; do not automatically label the infrastructure host as controller]`

## 2. Study purpose and participants

Research question and purpose: `[REPLACE in plain language]`<br>
Participant population and source: `[REPLACE]`<br>
Why this person was selected/contacted: `[REPLACE]`

## 3. Data, purposes and legal bases

| Purpose | Data used | Legal basis | Required or optional / consequence |
| --- | --- | --- | --- |
| Build/import the sampling frame | External reference, phone number and `[REPLACE: other source fields, if any]` | `[REPLACE: exact Article 6 basis and applicable national/research law]` | `[REPLACE]` |
| Draw and contact a sample | Pseudonymous sample ID, assigned time window, phone and attempt status | `[REPLACE]` | `[REPLACE]` |
| Conduct the interview | Consent record, answers, raw free text, spoken-wording checks and call metadata | `[REPLACE]` | `[REPLACE]` |
| Process special-category data, if any | `[REPLACE: exact categories or state none after questionnaire review]` | `[REPLACE: Article 9 exception plus applicable law/safeguards, or remove]` | `[REPLACE]` |
| Analyse/report research | Pseudonymous response dataset, coding and aggregate report | `[REPLACE]` | `[REPLACE]` |
| Secure and operate the service | `[REPLACE: verified server, security and audit log fields]` | `[REPLACE]` | `[REPLACE]` |

Research participation consent and GDPR consent are not automatically the same instrument. Do not use consent as a generic fallback; document the exact legal basis, withdrawal consequences and any applicable research-law safeguards.

## 4. Offline workbench and live CLI

- **Web workbench:** fixture-only; it stores one filesystem workspace on the application host and cannot place a live call.
- **Dry-run CLI:** uses local fixtures and SQLite.
- **Live CLI, if enabled:** sends the selected raw phone number, exact questionnaire/consent task, result schemas, locale and pseudonymous sample ID to the configured CALL-E endpoint. It receives structured results and a transcript. The full transcript is checked in memory but is not persisted by ResearchCall.

Deployment/study choice: `[REPLACE: modes actually used]`.

## 5. Recipients, processors and international transfers

| Recipient/category | Data and purpose | Role and location | Safeguard/contract |
| --- | --- | --- | --- |
| `[REPLACE: infrastructure host]` | `[REPLACE]` | `[REPLACE]` | `[REPLACE: Article 28 agreement if applicable]` |
| `[REPLACE: CALL-E contracting entity and subprocessors, or remove live mode]` | Phone, questionnaire task, locale, sample metadata and returned call material | `[REPLACE: verified role and processing countries]` | `[REPLACE: DPA and, if needed, Chapter V mechanism]` |
| Research team | Sampling frame, response data and analysis according to role | `[REPLACE: access groups and institutions]` | `[REPLACE]` |
| Research recipients/publication | `[REPLACE: aggregates, pseudonymous or truly anonymous data]` | `[REPLACE]` | `[REPLACE]` |

The code endpoint does not prove provider identity, actual processing countries, subprocessors, retention or transfer safeguards. Verify them from current contracts. Pseudonymised data remain personal data when the link can be restored.

## 6. Source and timing of information

Sampling-frame data come from `[REPLACE: source and whether publicly accessible]`. Complete the Article 14 analysis for data not obtained from the participant, normally providing information no later than the first communication when used for contact. Complete the Article 13 analysis for answers collected directly in the call. Provide a concise first layer during the call and the full participant information at `[REPLACE: URL/non-digital channel]`, as confirmed by legal/ethics review.

## 7. Storage, withdrawal and deletion

| Record | Period or deletion criterion |
| --- | --- |
| Original source frame | `[REPLACE: controller system and schedule]` |
| Imported external reference and phone | `[REPLACE; implement/test schedule]` |
| Attempt/run metadata | `[REPLACE]` |
| Structured answers and raw free text | `[REPLACE]` |
| Full transcript at CALL-E | `[REPLACE from verified provider terms; ResearchCall does not persist it locally]` |
| Workbench JSON, reports and exports | `[REPLACE]` |
| Logs and backups | `[REPLACE: fields, cycle and irreversible deletion point]` |

Current local withdrawal behavior: ResearchCall replaces the external reference, removes the phone, excludes the sample, deletes local responses and clears provider run IDs/detail for the affected sample. Sample/attempt timestamps, status and the idempotency key remain, and the code does not issue provider-side deletion. `[REPLACE: explain how a participant requests withdrawal, the legal/technical status of retained metadata, limits after genuine anonymisation/publication, and how provider data/backups are covered]`.

## 8. Automated decisions

ResearchCall automates sample drawing, contact-window assignment, configured coding and call-status handling. `[REPLACE: explain significance/effects and state whether any Article 22 decision occurs. Do not assume inapplicability.]`

## 9. Rights and complaints

Subject to the legal conditions and any valid research-specific limitations, individuals may have rights of access, rectification, erasure, restriction, objection and data portability, and may withdraw consent without affecting prior processing. Requests: `[REPLACE: channel, identity-verification and sample-link process]`.

Complaint authority: `[REPLACE: competent supervisory authority, address and URL]`.

## 10. Browser storage

The current workbench sets a `researchcall_lang` language cookie for one year. `[REPLACE: list authentication, reverse-proxy, consent, analytics or other deployed cookies/storage, or state that none are used after verification]`.

## 11. Changes and study results

Notice changes/version archive: `[REPLACE]`<br>
How participants can learn about study results: `[REPLACE or remove]`

## Pre-use checklist

- [ ] Every placeholder is replaced or removed and the questionnaire is attached to the review.
- [ ] Controller, processor and any joint-controller roles are documented.
- [ ] Article 6 basis, any Article 9 exception, national research rules and ethics requirements are documented.
- [ ] Sampling-frame source and Articles 13/14 delivery are documented and tested.
- [ ] Provider identity, location, retention, subprocessors, DPA and transfer safeguards are verified.
- [ ] Retention, withdrawal and deletion are implemented across source, local rows, provider data, logs and backups.
- [ ] Authentication and tenant authorization protect every study, write, report and export in any hosted deployment.
- [ ] DPIA necessity has been decided and recorded before high-risk processing.
- [ ] A qualified lawyer/data-protection officer and, where applicable, ethics body have reviewed the study-specific materials.
