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

## Annex A - Server modes (piggyback)

> **Still a template.** Pick the one block that matches `RESEARCHCALL_SERVER_MODE`, delete the others, keep replacing every marker. A mode changes what has to be written here; it does not remove the need to write it - and for a study it does not touch the ethics file at all.

**Which mode is deployed:** `[REPLACE: local | huckepack-gift | huckepack-only-host]` - verifiable at `[REPLACE: URL]/huckepack/mode`.

### A.1 If the mode is `local`

Sections 1-11 apply unchanged. Database and workbench file are on the host; the operator is the controller for both.

### A.2 If the mode is `huckepack-gift` or `huckepack-only-host`

**Replace section 7 (Storage, withdrawal and deletion) with:**

> This installation keeps no study database. The sampling frame, the attempts, the answers **and the workbench file with your station entries** are stored by your browser on your device. While you work, a copy is held in this server's working memory so the same queries can run; it is discarded at the latest `[REPLACE: confirm SESSION_TTL_SECONDS]` after your last request, when you delete your data, and when the server restarts. Nothing is written to a file on the server.
>
> Deleting your browser data deletes the study, and we cannot restore it. Use "back up data". **That file is the sampling frame**: it contains the link between record number and person, telephone numbers included. It is not encrypted.
>
> `[REPLACE: server, proxy and infrastructure logs exist regardless and must be described here after verification]`

**Replace section 10 (Browser storage) with:**

| Name | Purpose | Lifetime |
| --- | --- | --- |
| `[REPLACE: language cookie]` | Interface language | `[REPLACE]` |
| `huckepack.session` (local storage) | Identifies your working copy on the server | Until you delete your data |
| `huckepack` (IndexedDB) | **The study**: database and workbench file | Until you delete it |
| `huckepack.calle-key` (local storage) | *Only in `only-host`:* your own CALL-E key | Until you press "forget" |

`[REPLACE: assess device-storage consent per row under the applicable implementation of Article 5(3) ePrivacy Directive - in Germany section 25 TDDDG.]`

**Sections 1, 2, 6, 8 and 9 stay exactly as they are.** They concern the **participants** - people who are called, recorded and analysed. Where the researcher's copy of the data lives changes nothing about their position, their information rights or the ethics approval.

**One thing does change, and against them:** withdrawal and access. If the operator holds no copy, only the researcher at that browser can act on a withdrawal. `[REPLACE: name who receives a withdrawal, how they are reached, and how it is honoured. A study whose participants cannot withdraw in practice has a consent problem, not a documentation problem.]`

### A.3 Only in `huckepack-only-host` - the researcher's own key

> You enter your own CALL-E key. It stays in your browser, is shown only by its last four characters, and is sent to this server with a run so calls are placed in your name and billed to your account with `[REPLACE: entity]`. This server does not store it and does not log it.

`[REPLACE: who is controller for the fieldwork calls under the deployed setup?]`

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
- [ ] The deployed `RESEARCHCALL_SERVER_MODE` is stated, and only the matching block of Annex A remains.
- [ ] In a piggyback mode: checked on the running installation that neither the database nor `workspace.json` appears on disk.
- [ ] It is written down how a participant withdraws when the operator holds no copy.
- [ ] Device-storage consent assessed per row of Annex A.2.
