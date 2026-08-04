# DevPost submission form — ResearchCall

> **Copy-and-paste sheet.** Every heading below is a field of the DevPost submission
> form. The text under it is finished and goes into that field unchanged.
>
> **Nothing here has been submitted.** Submitting and uploading the video are the
> user's steps.
>
> **No Markdown tables anywhere below.** The DevPost editor does not render them, so
> everything comparative is written as a list on purpose.
>
> **Every placeholder is marked with an `ATTRAPPE` comment.** Search this file for
> `ATTRAPPE` before submitting and replace each one. The list is repeated at the end.

---

## Project name

```
ResearchCall
```

---

## Elevator pitch

*(DevPost limit: 200 characters. The text below is 145.)*

```
Standardised telephone surveys: identical wording, one call per person, and nonresponse reported by cause instead of one number called "reached".
```

---

## Project story

*(DevPost calls this "About the project". The headings below are DevPost's own suggested
structure — keep them as headings in the editor.)*

### Inspiration

Telephone surveys are still how a lot of social research reaches people who are not on a
panel. They are also expensive, slow, and — the part that matters here — *fragile*: the
moment one interviewer rephrases a question to be friendly, the answers stop being
comparable.

A voice agent can hold a wording perfectly. That is exactly the property an interviewer
cannot guarantee, and it is worth more than the speed.

But the same automation makes it trivially easy to produce something that looks like a
survey and is not one: call until you have enough answers, retry the people who did not
pick up, and report "312 reached". Every one of those steps destroys the thing that made
the numbers mean anything. So the tool had to be built the other way round — the method
first, the calls as one step inside it.

### What it does

- Draws a random sample from an imported frame and assigns each drawn record a randomised
  time window **at draw time** — before any outcome is known, so the exposure cannot be
  chosen after the fact.
- Places **one call per person by default**. Raising that bound is an explicit setting, and
  only an availability outcome — `NO_ANSWER`, `BUSY`, `VOICEMAIL` — reopens a record. A
  refusal never does; only an explicit invitation to call back does. A repeat goes into a
  *different* time window, because dialling the same time of day twice measures the same
  availability twice, and the report states how many records were affected — so the drift
  towards people who are easier to reach stays visible instead of disappearing into the
  completion rate.
- Speaks a fixed wording. The consent sentence, every question and every preplanned
  follow-up are quoted; spontaneous probing and paraphrasing are explicitly forbidden in
  the task.
- Keeps the participant's raw answer beside every interpreted category. A category with no
  non-empty raw source text is rejected.
- Keeps eight terminal outcomes apart — `NO_ANSWER`, `DECLINED`, `BUSY`, `VOICEMAIL`,
  `FAILED`, `CANCELED`, `EXPIRED`, plus a local `INTERRUPTED`. "Reached" is never one
  number.
- Reports completion yield, outcome structure by randomised time window, answer
  distributions by window, and wording-fidelity evidence — descriptively, without turning
  differences between windows into significance claims.
- Honours withdrawal with an anonymised audit tombstone: reference and phone number erased,
  responses erased, the record excluded from every report denominator, and only the window,
  timestamps and terminal status left for integrity auditing.
- Runs all of it offline against fixtures, with no account, credentials, network or call.

It has three surfaces on one method: a command line, a `SKILL.md` station router for
somebody else's agent, and a bilingual web workbench. The workbench is a *surface*, not a
second implementation — and it cannot place a call at all: no route accepts a live flag and
the web package never imports the live client.

### The one thing to try first

No installation, account, credentials, network or real call:

- `$env:PYTHONPATH = "src"`
- `python -m researchcall demo --workspace out/jury-demo --seed 42`

Measured output of that exact command on 2026-08-02:

- `mode=dry-run transport=fixture network=disabled`
- `frame_imported=200 sample_drawn=50 attempts=50`
- `COMPLETED 14, DECLINED 9, NO_ANSWER 5, BUSY 5, VOICEMAIL 5, CANCELED 4, EXPIRED 4, FAILED 4`

Fourteen complete interviews out of fifty attempts — and the other thirty-six do not
collapse into a single "not reached". That difference is the entire point. The demo's phone
values are fictitious, no phone value is printed anywhere, and the demo is structurally
unable to select the live adapter.

### Why not just use the CALL-E app?

Use it. For a single call the CALL-E chat is faster than anything we could build.

What it cannot produce is a **survey**. Fifty respondents with identical wording, randomly
assigned time windows, one timestamped attempt each, and a completion yield with its
nonresponse structure is not merely tedious in a chat — it is *methodologically
unobtainable*. Each chat call phrases itself anew, and without fixed wording there is no
instrument, only anecdotes.

The four categories the vendor app offers — Personal Message, Ask a Business, Book or
Reschedule, Follow Up — are single-call patterns. Volume, comparability and nonresponse
structure are the gap.

### How we built it

- Python 3.11+ with no runtime dependency beyond the standard library for the command line,
  so the dry run works on a machine with nothing installed. The `web` extra adds FastAPI and
  Uvicorn and is the only part that needs them.
- The pipeline is eight gated stations: research question, instrument, conversation and
  ethics frame, sampling, pretest, fieldwork, analysis, reporting. Gating is enforced —
  station N+1 opens once N is finished, a station will not close while a required answer is
  missing, and a value changed afterwards is stored as an amendment and marked as added
  later.
- Every human decision has exactly one form definition, readable three ways: as a config
  value, as a spoken question for an agent, and as a UI field descriptor. A translation
  table in code would have created a second source of truth that never reaches the question
  an agent asks, so field text lives in the definition itself.
- Of 59 decisions, an interface shows 48, an agent asks 11, and 11 are part of the frame.
  The eleven locked ones — explicit consent, the right to stop, keeping the raw answer
  beside its interpretation, reporting nonresponse by window — are not disabled controls;
  they are not controls. `/config` states them so nothing is hidden.
- The result schema was designed before the spoken text, and the wording written to satisfy
  it.

### Challenges we ran into

Measured against the real service, and several of these contradict the documentation:

- **Quoted text survives; unquoted text does not.** In one real call, text in straight
  double quotes came back in the transcript character for character, including a marker
  typo planted on purpose, while framing instructions outside the quotes were rephrased and
  the planner added behavioural instructions of its own. That single behaviour is what makes
  a fixed instrument possible at all — so consent sentence, questions and follow-ups are
  quoted and everything else is deliberately left outside.
- **What that proves is narrower than it looks, and we wrote the limit down.** What exists
  is a transcript line, not a recording. Whether the `BOT:` lines are the spoken text or the
  text the bot was told to speak is open. The marker's presence suggests generated text
  rather than back-transcribed audio — an indication, not proof. An earlier internal note
  claimed more than that and was retracted.
- **`status` is not progress.** It stayed on `PREPARING` while the conversation was already
  under way, so it is used only to recognise a terminal outcome; progress comes from
  `activity`, and the CLI prints a sanitised event count rather than the text.
- **The transcript is not where the documentation puts it.** Top-level `transcript` was
  `null`; the text is a string in `result.transcript`.
- **Result schemas are REST-only.** The MCP/CLI `plan_call` path exposes no `result_schema`,
  so it cannot carry the standardised result contract. A cross-path lookup returned HTTP
  404 — MCP run IDs and REST call IDs are separate ID spaces.
- **About 40 seconds of every call is setup** before ringing, independent of conversation
  length, so a serial quota needs roughly `40 x N` seconds of overhead before anybody
  speaks.

### Accomplishments that we're proud of

- The contact rule is enforced by the database, not by discipline. The sample is claimed
  before the request goes out, so an interruption or transport error does not quietly make
  that person eligible again — and a refusal can never be turned into a second attempt.
- Every setting is classified by where it actually takes effect — the call, the run, the
  analysis, the frame — or as *recorded only*, with the reason, and the badge sits on the
  control itself. An unclassified setting fails the test suite. Writing that register was
  the check: three settings it first called effective turned out not to be, and were either
  connected or moved to the honest column.
- The workbench is provably unable to call: verified by test that no route accepts a live
  flag, that the web package never imports the live client, and that no response of any
  route contains a phone number.
- Withdrawal actually removes the person from every denominator, rather than marking them
  and leaving the arithmetic alone.
- 191 tests and 506 subtests, all green, all offline — measured in the current local
  evidence run.
- The limits are written down at the same volume as the results. `EVIDENCE.md` records the
  literal commands and output, and a separate section states what remains unverified.

### What we learned

- Randomise the exposure before you know the outcome. Assigning time windows at draw time
  costs nothing and removes an entire class of post-hoc selection.
- A repeat call is not automatically wrong — repeating after a *refusal* is. Separating the
  two, and pushing any repeat into a different time window, keeps the ordinary practice of
  calling back without quietly buying the completion rate from the people who happen to be
  easy to reach.
- Make a control that changes nothing say so. Classifying every setting by where it takes
  effect found three that we had believed were doing something and were not.
- Keep the provider's status vocabulary intact. Busy, voicemail, no answer and declined are
  four different facts about why somebody is missing.
- A voice agent's greatest research value is not speed — it is that it will say the same
  sentence the four-hundredth time exactly as it said it the first.

### What's next for ResearchCall

- A pretest with informed participants, and then a real field phase. Neither has happened.
- Verifying service concurrency, which is currently unmeasured — the runner dispatches
  serially as a conservative default rather than encoding a ceiling it cannot confirm.
- Weighting and design effects for the report, which today stays deliberately descriptive.
- A second channel for the people a telephone does not reach, since that is the group the
  nonresponse structure keeps pointing at.

---

## Built with

*(DevPost expects a list of tags. Enter them one at a time.)*

```
python
sqlite
fastapi
uvicorn
htmx
call-e
rest-api
pytest
```

---

## Try it out links

- Repository: https://github.com/lukisch/researchcall
- Pull request to `CALLE-AI/awesome-phone-call-agents`:
  https://github.com/CALLE-AI/awesome-phone-call-agents/pull/78
  Known status: open. Before submission, verify the pushed commit and mergeability in
  GitHub; this form makes no conflict-status claim.

---

## Video demo link

<!-- ATTRAPPE: user gate — nothing has been uploaded and no render has been approved.
     The current v5 composition exists at C:\_Local_DEV\_calle-videos\researchcall\.
     Replace with the real YouTube URL after upload. -->

```
<the user inserts the public video URL directly in DevPost>
```

Requirements to check at upload time: under three minutes, publicly visible, English
narration or English subtitles, and it must show the project functioning.

---

## Repository link

```
https://github.com/lukisch/researchcall
```

---

## Pull request URL

*(Hackathon-specific required field: the PR to `CALLE-AI/awesome-phone-call-agents`.)*

```
https://github.com/CALLE-AI/awesome-phone-call-agents/pull/78
```

Known status: open. Verify the pushed commit and mergeability in GitHub before submitting.

---

## CALL-E account e-mail

<!-- ATTRAPPE: user gate — the user supplies this at submission time. It is deliberately never
     written into the repository. -->

```
<the user enters this directly in the form>
```

---

## Pre-existing project?

```
No. This repository was created during the hackathon submission period and every commit
in it is dated after 2026-07-23.
```

---

## Image gallery / thumbnail

Three thumbnail drafts, 1280x720, at
`C:\_Local_DEV\_calle-videos\researchcall\thumbnails\`:

- `researchcall-thumb-a.png` — "What does '50 reached' hide?" with the measured outcome
  breakdown. Recommended: it is the argument and the evidence in one frame.
- `researchcall-thumb-b.png` — wording fidelity, with the marker that came back unchanged.
- `researchcall-thumb-c.png` — the eight stations, with the call as station six.

The repository banner (1200x300) is `banner.png` in the repository root.

---

## Checklist of every ATTRAPPE in this file

The repository and pull-request URLs are filled in. The remaining user gates are:

1. **Video demo link** — needs an approved v5 render and the real YouTube URL after the
   user uploads it.
2. **CALL-E account e-mail** — the user types it into the form directly; it is not stored
   here.

---

## Notes for whoever fills the form in

- Paste the sections as plain text. There is no Markdown table anywhere in this file
  because the DevPost editor will not render one.
- Do not add a number that is not in this file. The demo figures and test counts are
  recorded in `EVIDENCE.md`.
- The wording-fidelity claim is deliberately hedged in the story text above. Do not
  "tighten" it into a proof when filling the form in — the underlying evidence note was
  explicitly retracted once for exactly that overstatement.
- The two remaining items in the checklist above are user gates.
