# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-14

### Added
- Created `llms.txt` machine-readable repository map and discoverability reference for AI agents.
- Added comprehensive interactive Mermaid 8-station pipeline architecture diagram to `README.md` and `README_de.md`.
- Added ecosystem, architecture, standard compliance, and test badges to `README.md` and `README_de.md`.
- Added GFM callout box for rapid LLM context resolution.

### Features
- Complete 8-station survey methodology pipeline (Research Question, Instrument, Conversation & Ethics Frame, Sampling, Pretest, Fieldwork, Analysis, Reporting).
- Local-first, offline-by-default Web Workbench built on FastAPI and HTMX.
- Standard-library-only CLI core with zero third-party runtime dependencies for dry-runs.
- Verbatim wording fidelity verification and syntactic marker tests in pretest station.
- Randomized time-window allocation at sample draw time.
- Single-attempt invariant with optional bounded refusal callbacks.
- Nonresponse decomposition preserving distinct outcome states without collapsing (AAPOR aligned).
- Gated live CALL-E adapter with consent attestation and bounded execution quota.
