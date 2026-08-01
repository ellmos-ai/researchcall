# ResearchCall

ResearchCall is a dry-run-first Python tool for standardized scientific telephone surveys. It draws a random sample, assigns each selected record to a randomized time window at draw time, allows exactly one attempt per selected record, and reports nonresponse without collapsing distinct CALL-E outcomes.

The default path is fully local: no account, credentials, SDK, network connection, or real call is needed. Fixtures exercise the same sampling, attempt, response, withdrawal, and reporting logic used by the gated live adapter.

## Methodological contract

- Questions use fixed wording and fixed answer categories.
- Conditional questions are the only preplanned follow-ups. The task explicitly forbids spontaneous probes and paraphrasing.
- Time windows are randomized when the sample is drawn, not chosen after an outcome is known.
- A database uniqueness constraint permits one attempt per sample record. There is no retry command.
- `run-day` processes at most the next `N` open records in one assigned time window. Recurrence belongs to the host scheduler; ResearchCall has no daemon or multi-day loop.
- Every claimed attempt receives `started_at` before the transport is invoked and `ended_at` on terminal, failed, or interrupted completion.
- `NO_ANSWER`, `DECLINED`, `BUSY`, `VOICEMAIL`, `FAILED`, `CANCELED`/`CANCELLED`, `EXPIRED`, and local `INTERRUPTED` remain distinct.
- Reports show completion yield, outcome structure by randomized time window, answer distributions by time window, and wording-fidelity evidence.

The report is descriptive. It does not turn differences between windows into claims of statistical significance.

## Setup

Requires Python 3.11 or newer. Runtime dependencies are limited to the Python standard library.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Offline demonstration

This command creates 200 fictitious frame rows, draws 50, randomly assigns their time windows, processes all 50 against mixed terminal fixtures, and writes an aggregate report:

```powershell
researchcall demo --workspace out/demo --seed 42
```

The demo is intentionally unable to select the live adapter. Its fixture phone values are fictitious, and no phone value is printed to the console or report.

## Normal workflow

Initialize state and register a questionnaire:

```powershell
researchcall --db survey.db init
researchcall --db survey.db create-study --study mobility-2026 --questionnaire .\questionnaire.json
```

The bundled questionnaire at `src/researchcall/fixtures/questionnaire.de.json` demonstrates exact German wording, fixed categories, a conditional follow-up, and real UTF-8 umlauts.

Import a CSV with `external_ref` and `phone_e164` columns:

```powershell
researchcall --db survey.db import-frame --study mobility-2026 --source .\contacts.csv
```

SQLite sources are opened read-only:

```powershell
researchcall --db survey.db import-frame --study mobility-2026 --source .\contacts.sqlite --table people --id-column participant_id --phone-column phone_e164
```

Frame identifiers and phone numbers must both be unique within a study. Phone numbers are validated as E.164 before import and again immediately before an attempt is claimed.

Draw and assign time windows reproducibly:

```powershell
researchcall --db survey.db draw --study mobility-2026 --count 50 --seed 42 --windows morning,afternoon,evening
```

Process a bounded morning quota in the default offline mode:

```powershell
researchcall --db survey.db run-day --study mobility-2026 --window morning --limit 10
```

Run the afternoon and evening quotas from the host scheduler as separate commands. ResearchCall never installs or hides a recurring schedule.

Create the aggregate report:

```powershell
researchcall --db survey.db report --study mobility-2026 --output out/report.md
```

## Wording fidelity: an explicit limitation

CALL-E has no dedicated script, wording, tone, or persona field. ResearchCall therefore places the exact consent text, every exact question, the filter rules, and the prohibition on paraphrasing in CALL-E's free-text `task`. Its `recipient_result_schema` requires:

- `asked_verbatim`
- `spoken_consent_wording`
- the actual `spoken_wording` for every question
- consent and withdrawal state
- answers constrained to the questionnaire's fixed categories

ResearchCall independently compares the returned wording with the questionnaire. This is useful audit evidence, but the fields are still produced by the remote agent. Fixture success proves the local enforcement and audit path only. Strict live standardization cannot be claimed until a real, consented test verifies the transcript. If CALL-E paraphrases, ResearchCall reports the mismatch instead of treating that interview as standardized.

## Consent, withdrawal, and minimization

The fixed consent sentence is asked first. If consent is not granted, the task requires the interview to end without survey questions. A withdrawal request triggers an anonymized audit tombstone:

- external reference and phone number are erased;
- structured responses and provider run identifiers are erased;
- the sample record is marked `WITHDRAWN` and excluded from every report denominator;
- only the randomized window, attempt timestamps, and terminal operational status remain for integrity auditing.

Use the local withdrawal command when a request arrives outside a call:

```powershell
researchcall --db survey.db withdraw --study mobility-2026 --external-ref participant-0042
```

Reports use IDs and aggregates only. They never include names or unmasked phone numbers. The tool stores no transcript and sends no background history, names, addresses, or unused frame attributes to CALL-E.

## Live-call safety gate

No live call is possible without all of the following:

1. `--live`
2. `--confirm-live "CALL N"`, exactly matching the bounded `--limit N`
3. `--consent-attested`
4. a valid E.164 number already in the selected frame row
5. `CALLE_API_KEY` supplied only through the environment

Example syntax only; it was not executed during development:

```powershell
$env:CALLE_API_KEY = "<secret>"
researchcall --db survey.db run-day --study mobility-2026 --window morning --limit 1 --live --confirm-live "CALL 1" --consent-attested
```

The live adapter is deliberately serial because CALL-E's concurrency ceiling is not confirmed. It creates one-recipient API calls and sends a deterministic, non-personal `Idempotency-Key`. The database claims the sample before the request, so an interruption or transport error does not make that person eligible for a retry.

The content guard rejects questionnaires that explicitly request medical, legal, financial, or emergency advice. It is a narrow technical backstop, not legal review. The operator remains responsible for consent, lawful contact, research ethics, and jurisdiction-specific requirements. For German private persons, use informed participants; business respondents are the safer demonstration setting described in the project specification.

## Data-flow disclosure

Offline fixture mode stays inside the local process and SQLite file. It performs no authentication and no network operation.

Live mode sends the selected phone number, locale, exact questionnaire task, result schema, and a pseudonymous sample ID to the external CALL-E/AiRudder service. The documented CALL-E agent/MCP infrastructure is hosted in Singapore at `https://seleven-mcp-sg.airudder.com`; the Developer API base used by the adapter defaults to `https://api.heycall-e.com` and can be changed with `CALLE_BASE_URL`. Service-side security, audit, and operational logs may exist. Do not put unnecessary personal data into the questionnaire or task.

ResearchCall stores terminal status, timestamps, a provider run ID until withdrawal, and the schema-constrained result. It intentionally does not store transcripts. Access tokens are read from environment variables and are never written to the database, report, logs, examples, or source code.

## Side effects and abort behavior

- `init`, `demo`, imports, sampling, attempts, responses, and withdrawal operations write only to the selected local SQLite database and requested report directory.
- Dry-run `run-day` consumes a sample's one allowed attempt using a fixture result. Use a disposable database for demonstrations.
- `Ctrl-C` records `ended_at` and local status `INTERRUPTED`, then exits with code 130. CALL-E exposes no cancellation tool in the verified contract, so interrupting local polling cannot be presented as cancellation of a call already in progress.
- Polling is bounded per live call: first status read after approximately 60 seconds, then every 10 seconds until a terminal result or timeout. There is no unbounded daemon loop.

## Verified and unverified scope

Verified locally: offline 200-to-50 demonstration, random time-window assignment, single-attempt invariant, timestamps, mixed fixtures, withdrawal exclusion, wording audit, aggregate report, E.164 validation, output masking, SQLite read-only import, and live-gate rejection before client creation.

Not verified: account authentication, real calls, the live Developer API adapter, exact live wording, transcript timing, concurrency limits, remote cancellation, CI, publication, or any jurisdictional approval. See `EVIDENCE.md` for literal executed commands and output.

