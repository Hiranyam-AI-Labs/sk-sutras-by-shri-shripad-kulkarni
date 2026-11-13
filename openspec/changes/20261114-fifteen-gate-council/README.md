# Fifteen-gate council workflow

Status: implementation milestone, not a release. Governance baseline: 2026.11.11.1.

## Outcome and acceptance

- AC-01: Every contemporary Udyam chapter uses versioned fifteen-gate evaluation; missing evidence never becomes PASS. `src/agents/acceptance_policy.py` and tests.
- AC-02: The five frozen roles exchange source, challenge, draft and verifier evidence through a bounded service. `src/orchestration/council_service.py` and actual runner integration tests.
- AC-03: Every live call passes a dated model rate, durable run budget, call limit and truthful usage audit. `src/providers/dispatch.py`; mocked restart and budget tests.
- AC-04: Repeated people and businesses, aliases and related entities are allocated durably; author exception is version-bound. `src/database/example_registry.py` and tests.
- AC-05: AI validation, credentialed scholar review, author approval and frozen manifest are separate exact-content states. Author approval atomically commits example reservations. `src/orchestration/review_store.py`, `src/api/routers/review_v2.py`, `src/ui/app.py` and tests.
- AC-06: Publication requires seven substantive sections and an approved content hash. Word/PDF render only from a stored manifest rechecked against current approvals and allocations. `src/doc_export/manifest_export.py` and synthetic export tests.
- AC-07: Actual indexed IKS IDs are checked against the local corpus before passages reach the researcher, author and verifier. The runner counts eligible drafts, not attempted candidates. `src/orchestration/source_evidence.py`, runner and tests.

## Scope and evidence

Capabilities: AI workflow, API/data boundary, publication. Existing Python, SQLite, LangGraph and provider adapters retained. Word/PDF use the declared `python-docx` and `reportlab` dependencies. Current test results are recorded in `docs/IMPLEMENTATION_STATUS_20261113.md`. No real provider call, deployment or historical manuscript rewrite occurred.

## Remaining work before release

- Validate actual source relevance and Sanskrit, confirm current model prices and credentials, and run controlled UAT with the client's spend cap.
- Complete scholar and author review of real drafts, freeze a full edition, and verify long-form Word/PDF pagination and assembled-book diversity. LibreOffice is unavailable for local Word page rendering.
- Reconcile actual provider billing if and when billing metadata is supplied; current audit stores only available usage and estimated reservations.

This change is intentionally not marked complete or production ready.
