# ResearchCall

ResearchCall is a dry-run-first Python tool for standardized scientific telephone surveys. It draws a random sample, assigns each selected record to a randomized time window at draw time, allows exactly one attempt per selected record, and reports nonresponse without collapsing distinct CALL-E outcomes.

The default path is fully local: no account, credentials, SDK, network connection, or real call is needed. Fixtures exercise the same sampling, attempt, response, withdrawal, and reporting logic used by the gated live adapter.

## Methodological contract

- Questions use fixed wording and fixed answer categories.
- Conditional questions are the only preplanned follow-ups. The task explicitly forbids spontaneous probes and paraphrasing.
- Every interpreted category keeps the participant's raw answer beside it. A category without non-empty raw source text is rejected.
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
python -m researchcall --help
```

The editable install is required when invoking `python -m researchcall` from the repository root. Running directly from an uninstalled `src` layout otherwise requires an explicit `PYTHONPATH=src`, which is not the documented workflow.

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

## Wording fidelity: confirmed quoted-task behavior

An operator-provided real CALL-E test on 2026-08-01 confirmed the critical mechanism: text enclosed in straight double quotes in `task` was spoken character-for-character, including an intentional typo. The same measured run showed that framing instructions outside quotes were paraphrased and that the planner added behavioral instructions of its own.

ResearchCall therefore places the consent sentence, every question, and every preplanned follow-up in double quotes. Filter logic, answer categories, privacy limits, and other framing instructions remain outside the quotes. Its `recipient_result_schema` requires:

- `asked_verbatim`
- `spoken_consent_wording`
- the actual `spoken_wording` for every question
- the participant's uncorrected `raw_answers` for every question
- separately interpreted `answers` constrained to the fixed categories
- consent and withdrawal state

The real test positively answers the specification's open feasibility question for the measured service behavior. It is not treated as a permanent guarantee for every future call. For each live result, ResearchCall still compares schema-reported wording and checks the final nested transcript for every expected quoted sentence. A mismatch remains visible instead of being counted as standardized.

Raw answers are methodologically separate from categories. The measured answer `2. Ja, unzufrieden.` was interpreted as `dissatisfied`; ResearchCall retains both values so that the categorization remains auditable. Aggregate reports count raw-answer coverage but do not print raw response text.

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

### REST is the primary live transport

Schema-validated collection is available only through the Developer REST API: `POST /v1/calls` with `Authorization: Bearer $CALLE_API_KEY`. The MCP/CLI `plan_call` path exposes no `result_schema` or `recipient_result_schema`, so it cannot provide the standardized result contract ResearchCall requires. A measured cross-path lookup returned HTTP 404: MCP run IDs and REST call IDs occupy separate ID spaces. ResearchCall therefore creates and polls the same call through REST; it does not start through MCP and then attempt REST retrieval.

The key is read only from `CALLE_API_KEY`, is never printed or persisted, and is not validated by a guessed prefix. `CALLE_BASE_URL` may override the endpoint without changing credential handling.

Example syntax only; it was not executed during development:

```powershell
$env:CALLE_API_KEY = "<secret>"
researchcall --db survey.db run-day --study mobility-2026 --window morning --limit 1 --live --confirm-live "CALL 1" --consent-attested
```

The current runner dispatches one-recipient REST calls serially as a conservative default and sends a deterministic, non-personal `Idempotency-Key`. This is not a claim that the service forbids parallel calls: concurrency remains unmeasured, and the code does not encode a provider concurrency ceiling. Each call and attempt remains independently addressable so a later, separately verified dispatcher can preserve the same schema and idempotency rules. The database claims the sample before the request, so an interruption or transport error does not make that person eligible for a retry.

The measured call had about 40 seconds of setup time before ringing, independent of its later conversation length. Plan a serial quota with roughly `40 × N` seconds of setup overhead for `N` calls, plus ringing, conversation, and final synchronization time. The CLI prints this as a planning observation, not a guaranteed duration.

### Live progress and final transcript

`status` is used only to recognize a terminal outcome. In the measured call it remained `PREPARING` while the conversation was already in progress, so ResearchCall never presents it as a progress bar. Live progress is derived from changes to `activity`; the CLI prints only a sanitized event count. It does not print activity text, phone numbers, or answers. Streaming activity can contain an initial recognition followed by a corrected duplicate, so it is progress evidence rather than the final scientific record.

After completion, the transcript is read from `result.transcript`, not the top-level `transcript` field (which was `null` in the measured result). It is a single string with `[mm:ss] BOT: Text` and `[mm:ss] USER: Text` lines. ResearchCall validates that format and checks for the expected quoted sentences in memory. It persists only audit flags, not the full transcript.

The content guard rejects questionnaires that explicitly request medical, legal, financial, or emergency advice. It is a narrow technical backstop, not legal review. The operator remains responsible for consent, lawful contact, research ethics, and jurisdiction-specific requirements. For German private persons, use informed participants; business respondents are the safer demonstration setting described in the project specification.

## Data-flow disclosure

Offline fixture mode stays inside the local process and SQLite file. It performs no authentication and no network operation.

Live mode sends the selected phone number, locale, exact questionnaire task, result schema, and a pseudonymous sample ID to the external CALL-E/AiRudder service. The documented CALL-E agent/MCP infrastructure is hosted in Singapore at `https://seleven-mcp-sg.airudder.com`; the Developer API base used by the adapter defaults to `https://api.heycall-e.com` and can be changed with `CALLE_BASE_URL`. Service-side security, audit, and operational logs may exist. Do not put unnecessary personal data into the questionnaire or task.

ResearchCall stores terminal status, timestamps, a provider run ID until withdrawal, and the schema-constrained result, including raw answers needed to audit category interpretation. It intentionally does not store full transcripts: the final nested string is inspected in memory and discarded after audit flags are derived. Access tokens are read from environment variables and are never written to the database, report, logs, examples, or source code.

## Side effects and abort behavior

- `init`, `demo`, imports, sampling, attempts, responses, and withdrawal operations write only to the selected local SQLite database and requested report directory.
- Dry-run `run-day` consumes a sample's one allowed attempt using a fixture result. Use a disposable database for demonstrations.
- `Ctrl-C` records `ended_at` and local status `INTERRUPTED`, then exits with code 130. CALL-E exposes no cancellation tool in the verified contract, so interrupting local polling cannot be presented as cancellation of a call already in progress.
- Polling is bounded per live call: first read after approximately 60 seconds, then every 10 seconds until a terminal result or timeout. `activity`, not nonterminal `status`, supplies progress. There is no unbounded daemon loop.

## Verified and unverified scope

Verified locally: offline 200-to-50 demonstration, random time-window assignment, single-attempt invariant, timestamps, mixed fixtures, raw-answer/category separation, withdrawal exclusion, wording and nested-transcript audit paths, aggregate report, E.164 validation, output masking, SQLite read-only import, REST schema payload construction, `activity`-based progress handling while status remains `PREPARING`, and live-gate rejection before client creation.

Measured externally and recorded in `FINDINGS.md`: one real test call spoke quoted wording exactly (including an intentional typo), exposed progress through `activity` while `status` stayed `PREPARING`, returned the final transcript as a string in `result.transcript`, interpreted a free answer into a category, incurred about 40 seconds of setup time, and demonstrated separate MCP/REST ID spaces with an HTTP 404 cross-lookup.

Still unverified: service concurrency limits, voicemail/busy/no-answer behavior beyond fixtures, whether REST and MCP share one quota, remote cancellation, CI, publication, or any jurisdictional approval. No real call is made by the repository test suite. See `EVIDENCE.md` for literal executed commands and output.
