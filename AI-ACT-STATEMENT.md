# Initial EU AI Act assessment: ResearchCall

**Date:** 2 August 2026
**Scope:** AI-assisted standardised scientific telephone surveys with an ethics and consent framework
**Notice:** This is a technical and editorial initial assessment, not legal advice. The research institution or specific operator must obtain legal and ethics review of the study, sampling source, roles, contracts, and legal bases before live fieldwork.

## Executive finding

For its currently documented intended purpose, ResearchCall is **not high-risk merely because a survey concerns employment or education**. The code collects standardised research data; it does not decide recruitment, termination, performance, educational access, or learning outcomes. Repurposing it to evaluate or profile people for such decisions would require a fresh Annex III assessment.

ResearchCall also presents a threshold scope issue. AI Act Article 2(6) excludes AI systems specifically developed and put into service for the sole purpose of scientific research and development. That exclusion is **plausible but is not established by the project's name**. Recital 25 distinguishes such systems from general AI systems merely used in research, which remain in scope. If ResearchCall is offered as a general survey service, commercial product, or for another purpose, the exclusion should not be assumed.

The safe operating assumption is therefore: **apply Article 50(1) and (5) unless the sole-scientific-purpose exclusion is documented for the concrete deployment**. Current code does not establish Article 50 compliance. The researcher-supplied introduction is supposed to disclose automation according to form help, but its content is not validated; a free-form greeting may precede it; “AI” is not mandatory; and transcript validation checks consent and questions rather than disclosure.

The ethics framework is more developed than in the other projects. Participation consent nevertheless occurs during the call. It cannot retrospectively justify processing the sampling number, sending it to the provider, and dialling.

## 1. Applicable duties

| Issue | Initial assessment | Reason |
| --- | --- | --- |
| AI Act Article 2(6) | **Plausible but open exclusion.** | It requires specific development and putting into service **solely** for scientific R&D. Product, operator, and deployment evidence are necessary; merely using a general system in a study is insufficient under Recital 25. |
| AI Act Article 50(1), (5) | **Treat as applicable conservatively.** | Without an evidenced Article 2 exclusion, the system interacts directly with natural persons. Clear AI disclosure is due no later than first interaction and applies from 2 August 2026. |
| AI Act Article 4 | **Applies by role if in scope.** | Providers and deployers must take measures supporting AI literacy for operators. Research leads, field teams, and hosts need competence on limits, bias, consent, privacy, and escalation. |
| AI Act Article 6 and Annex III | **Not currently high-risk.** | Standardised interviewing and rule-based coding are not the listed education or employment decisions. A study's subject alone does not alter the system's intended purpose. |
| GDPR Articles 5, 6, 9, and 89 | **Applies regardless of AI Act scope.** | Sampling numbers, contact data, answers, free text, and metadata are personal data. Special categories need a separate Article 9 condition; research needs appropriate safeguards and minimisation under Article 89. |

### High-risk boundary

A fresh assessment is mandatory before any study that intends ResearchCall or its output to:

- select applicants, evaluate workers, allocate tasks based on personal traits, or decide employment conditions;
- decide educational access or level, evaluate learning outcomes, or monitor exam behaviour;
- decide essential services, credit, or insurance;
- assess or profile people for another Annex III use case.

Surveying employees about workplace satisfaction or students about teaching quality does not itself perform those decisions. If answers generate an individual assessment for an Annex III decision, classification can change. Profiling natural persons in a relevant Annex III case is always high-risk under Article 6(3). Regulation (EU) 2026/1744 moved the Annex III high-risk duties to 2 December 2027; Article 50 applies now where Article 2(6) does not exclude the deployment.

## 2. What the code does and does not establish

### Existing controls

- The canonical form requires `ethics.instruction`; help text says its first sentence discloses automation and the commissioning body (`pipeline/_shared/forms/ethics.forms.yaml:3-15`).
- A privacy notice is required, and the explicit participation decision cannot be disabled (`pipeline/_shared/forms/ethics.forms.yaml:31-57`).
- The disclosure, the scope and duration, a one-sentence data statement, the right to stop and deletion on request are composed by the tool and inserted verbatim into every task, whichever path built the study (`src/researchcall/questionnaire.py`). The researcher's own introduction and long privacy notice are inserted as opening blocks — those exist only where a study was built in the workbench; a questionnaire loaded from a file carries no opening blocks, which is why the first field trial spoke neither (`FINDINGS.md`, section 14).
- The CLI will not start a live run without the quota-bound confirmation and `--consent-attested` (`src/researchcall/cli.py:169-188`). This is an operator attestation, not evidence of each recipient's prior consent.
- Returned evidence checks whether the consent sentence and standardised questions appear in bot transcript lines (`src/researchcall/runner.py:304-356`). Since the user decision of 2026-08-11 the transcript is stored with the attempt so a person can review the conversation; retention is switchable per study (`fieldwork.keep_transcript`), dialable numbers are removed before storing (`src/researchcall/safety.py:52-72`), and withdrawal or deliberate anonymisation erases the stored text with the record.

### The Article 50 gaps, and what closed them

The four gaps listed here until 2026-08-11 were not hypothetical: the first live call
made none of the disclosures, and the user said so (`FINDINGS.md`, section 13). They are
now addressed structurally rather than left to the instrument.

1. The disclosure no longer depends on `ethics.instruction`, which is free text with no
   validator. `build_task()` composes it from the study's own language and its named
   commissioning body (`src/researchcall/questionnaire.py`, `AI_DISCLOSURE`).
2. It is emitted before the opening blocks, quoted, with the instruction to say it before
   anything else.
3. The order in the task is unambiguous: disclosure, right to stop, consent, questions,
   withdrawal route at the end.
4. The disclosure and the right to stop are gate phrases, checked against the transcript
   exactly like the consent sentence; a call that did not speak them opens a review case
   (`src/researchcall/phrases.py`).

`ethics.commissioner` and `ethics.withdrawal_contact` are required settings, spoken
verbatim. A live run without them is refused; a dry run proceeds and reports
`disclosure_incomplete`.

**What this does not establish.** The measured fact is that quoted sentences are spoken
verbatim (`FINDINGS.md`, section 4); that the agent also honours the instructed *order*
is not measured, which is why the gate audit exists. The operator attestation
`--consent-attested` remains an attestation, not evidence of prior consent by each
recipient. The status is **an ethics framework whose Article 50 disclosures are now
enforced in the task and audited in the return, with their placement verified per call
rather than assumed**.

## 3. The called person did not consent in advance

ResearchCall models an explicit participation decision and a stop mechanism. That matters for the survey, but it does not automatically establish a basis for creating a sampling frame, storing a phone number, sending it to CALL-E, and causing the first ring.

Each study must document separately:

1. **Pre-contact phase:** sampling source, selection rule, Article 6 basis, necessity, prior invitation or another lawful contact route, exclusions, attempt count, and suppression logic. The boolean `--consent-attested` does not store that evidence.
2. **Information:** Article 14 normally applies no later than first communication where sample data came from registries, clients, or other sources; Article 13 applies to answers obtained directly. The call needs a concise first layer and an accessible full notice.
3. **Participation and data protection:** research participation consent and GDPR consent are not automatically the same instrument (`PRIVACY-TEMPLATE.md:25-36`). If consent is the legal basis, it must be voluntary, informed, specific, evidenced, and withdrawable for the relevant processing.
4. **Special categories:** political opinions, health, religion, trade-union membership, sex life, and other Article 9 data require a separate condition and safeguards. “Scientific research” is not a blanket permission; Article 9(2), any applicable national law, and Article 89 must be assessed.
5. **Withdrawal and objection:** the existing local purge is stronger than in the other apps, but it cannot delete unknown provider holdings. Contact data, provider data, exports, backups, and publication limits need one coherent process, including the point at which genuine anonymisation prevents linkage.
6. **Recording:** the repository evidences a transcript, not CALL-E's audio behaviour. Any audio recording requires a separate authority assessment, including German Criminal Code section 201 where applicable. Transcription remains data processing even without retained audio.

Ethics approval is important governance but does not itself replace GDPR Articles 6, 9, or transparency duties. Conversely, a GDPR legal basis is not a research-ethics approval.

## 4. Hosting duties by server mode

Roles follow actual purposes, means, contracts, and branding. The research institution may be the controller; a host may be a processor, joint controller, AI Act provider, or deployer. The deployment must allocate these roles in writing.

| Mode in `../huckepack/KONZEPT.md` | Operator requirement |
| --- | --- |
| `local` | The web workbench is fixture-only for calling but uses one shared workspace without accounts; the live CLI is a separate single-operator path (`HOST-READINESS.md:3-30`). External hosting requires study/tenant isolation, authentication, permissions, retention, and export controls. |
| `huckepack-gift` | If live research is offered, the host provides the key and execution. Browser persistence removes neither transit processing nor responsibility for disclosure, sample approval, provider transfer, quotas, and a rights channel. |
| `huckepack-only-host` | A researcher provides their own key, but sample, task, and result transit the host. Roles, processing terms, secret protection, deletion routes, and provider transfers remain necessary. |
| `pay-membership` | Stub only. Accounts, institutional tenants, roles, study approvals, billing, secret management, rights, deletion, export, and incident procedures are prerequisites. |

`DATA-FLOW.md:17-41, 45-71` documents the live data route, pseudonymisation limits, possible special categories, and piggyback transit. `PRIVACY-TEMPLATE.md:25-77` separates legal bases, special categories, first-contact information, and local withdrawal. `HOST-READINESS.md:19-30` additionally requires study governance, a DPIA decision, and verified CALL-E terms.

### Release criteria before live fieldwork or hosting

- Document whether Article 2(6) applies to the concrete sole-research deployment; otherwise apply Article 50 in full.
- Immutable verbatim AI sentence as the first bot utterance, without a preceding greeting, plus automated transcript evidence.
- Study file covering purpose, sampling source, pre-contact basis, Article 9 screening, ethics approval, Articles 13/14 information, redial limits, and suppression.
- Separate, evidenced participation and data-protection decisions; workable withdrawal, objection, access, and deletion procedures.
- GDPR Article 35 DPIA threshold assessment, especially for large-scale sensitive data, vulnerable groups, or systematic evaluation.
- Verified CALL-E roles, contracting entity, subprocessors, countries, retention, deletion route, Article 28 terms, and any Chapter V mechanism.
- Mode-appropriate tenant isolation, security, export control, retention, and Article 4 AI-literacy measures.
- New Annex III assessment before every education, employment, or other decision-making use.

## 5. Sources and evidence limits

This assessment builds on, but does not reproduce, the following in-house Um:bruch analyses:

- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\website\src\content\blog\ai-act-transparenzpflichten-ab-august-2026.md`, the primary editorial analysis.
- `...\ki-reviews\eu-ai-act-transparenz-code-of-practice.md` and `eu-ai-act-transparency-code-of-practice.md`.
- `...\ki-reviews\eu-ai-act-haftungsluecke.md` and `eu-ai-act-liability-gap.md`.
- `C:\Users\User\OneDrive\.TOPICS\.UMBRUCH\_editorial\entwuerfe\2026-07-03_eu-ai-act_leitartikel_synthese.md`, treated as a draft.

Primary and authority sources: [Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj), [Article 2 and the research exclusion](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-2), [Recital 25](https://ai-act-service-desk.ec.europa.eu/en/ai-act/recital-25), [Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj), [Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50), [Annex III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), [GDPR including Article 89](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng), [European Commission on research consent](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/legal-grounds-processing-data/grounds-processing/how-consent-processing-scientific-research-obtained_en), and [German Criminal Code section 201](https://www.gesetze-im-internet.de/stgb/__201.html).

The concrete Article 2(6) classification, study-specific legal and ethics approvals, sampling provenance, Article 9 condition, CALL-E audio and contract facts, provider retention, countries, and subprocessors are not evidenced and remain open.
