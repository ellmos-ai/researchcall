# ResearchCall host-readiness finding

## Verdict

**Not ready for untrusted multi-user hosting.** The web workbench is safely fixture-only with respect to calls, but it is still a single shared workspace with no login or ownership checks. Every visitor would edit and download the same study state. The live CLI is a separate single-operator process, not a per-user service.

## Evidence

| Question | Current implementation | Consequence | Evidence |
| --- | --- | --- | --- |
| Accounts or authenticated sessions? | None. The only cookie is a language preference. | There is no authenticated user or owner identity. | `src/researchcall/web/app.py:42-111` and route set in the same file |
| Per-user workspaces? | No. The server resolves one startup-wide `RESEARCHCALL_WORKSPACE`, default `out/workbench`. | All visitors read and overwrite one `workspace.json` and one artifact directory. | `src/researchcall/web/app.py:35-62`; `src/researchcall/web/workspace.py:91-125, 166-168` |
| Per-user database? | No. The fixture field phase uses one database inside that shared workspace; CLI commands use one operator-supplied `--db`, default `researchcall.db`. | Studies, frames, samples, attempts and responses are not tenant-separated. | `src/researchcall/web/field_phase.py:50-55, 169-257`; `src/researchcall/cli.py:29-35` |
| Object-level authorization? | No. Station edits, config, exact task, fieldwork start/stream, report and exports are unauthenticated routes. | Any visitor can change the shared design, start fixture work and download shared outputs. | `src/researchcall/web/app.py:113-469` |
| Can each user provide their own API key? | No. The web workbench has no live transport at all. The separate CLI reads one `CALLE_API_KEY` from its process environment. | A hosted workbench cannot call; turning the CLI into a service would share one operator key unless a tenant secret design is added. | `src/researchcall/calls.py:218-244`; `src/researchcall/cli.py:169-194`; `README.md:62-63` |
| Safe retention controls? | A targeted withdrawal purge exists, but no general timed retention/deletion workflow exists for studies/workspaces/exports. | Withdrawal is stronger than in the other apps, but it is not a complete host retention system. | `src/researchcall/runner.py:195-245`; `src/researchcall/web/workspace.py`; `src/researchcall/web/field_phase.py` |
| Network exposure? | Default host is `127.0.0.1`, overridable with `RESEARCHCALL_HOST`. | It can be externally bound while remaining unauthenticated. | `src/researchcall/web/app.py:475-482` |

## Required work before multi-user hosting

1. Add accounts, secure authenticated sessions and explicit researcher/admin roles.
2. Give every study/workspace/database object a tenant/user owner. Enforce object-level authorization on every page, write, stream, report and export; use isolated storage paths that cannot be selected by request input.
3. Replace the single filesystem workspace with a tenant-aware storage model and concurrency controls. Move durable field jobs to an authenticated queue if multiple workers are required.
4. Keep the web workbench fixture-only unless live calling is deliberately designed as a separate service. If live service is added, store per-tenant credentials in an encrypted secret store or use an operator-only credential with explicit quotas and authorization. Never accept a raw API key through an unprotected form.
5. Define and implement retention/deletion for source frames, SQLite rows, workspace JSON, reports, exports, logs and backups. Preserve and test the existing withdrawal purge semantics.
6. Add CSRF protection, secure cookie settings, TLS, rate limits, audit events, export controls and monitoring. If live service is added, enforce HTTPS for every outbound CALL-E base URL. Perform a separate security review.
7. Add study-level governance: legal basis, special-category screening, participant information/consent, ethics approval where applicable, data minimisation and a DPIA trigger decision.
8. Verify CALL-E roles, contracting entity, processing countries, subprocessors, provider retention, Article 28 terms and any Chapter V transfer mechanism before live use.

The privacy notice template is only one launch artifact. Completing it does not provide tenant isolation, ethics approval or a legal basis for a study.
