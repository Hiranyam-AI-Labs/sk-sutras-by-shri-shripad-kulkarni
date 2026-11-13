# Fifteen-gate council workflow

Status: implementation milestone, not a release. Governance baseline: 2026.11.11.1.

## Outcome and acceptance

- AC-01: Every contemporary Udyam chapter uses versioned fifteen-gate evaluation; missing evidence never becomes PASS. `src/agents/acceptance_policy.py` and tests.
- AC-02: The five frozen roles exchange source, challenge, draft and verifier evidence through a bounded service. `src/orchestration/council_service.py` and actual runner integration tests.
- AC-03: Every live call passes a dated model rate, run budget, call limit and truthful usage audit. `src/providers/dispatch.py`; mocked budget tests.
- AC-04: Repeated people and businesses, aliases and related entities are allocated durably; author exception is version-bound. `src/database/example_registry.py` and tests.
- AC-05: AI validation, scholar review, author approval and frozen manifest are separate exact-content states. `src/orchestration/review_store.py` and tests.
- AC-06: Publication requires seven substantive sections and an approved content hash. `src/doc_export/manifest_export.py` and tests.

## Scope and evidence

Capabilities: AI workflow, API/data boundary, publication. Existing Python, SQLite, LangGraph and provider adapters retained. No new dependency declared. Current test command and results are recorded in `docs/IMPLEMENTATION_STATUS_20261113.md`. No real provider call, deployment or historical manuscript rewrite occurred.

## Remaining work before release

- Bind actual author and scholar review actions in API/UI to `ReviewStore`, and commit example reservations only after human approval.
- Render Word/PDF exclusively from a frozen approved manifest; check layout and assembled-book diversity.
- Persist truthful dispatch audit transactionally with retries and reconcile provider billing when supplied.
- Validate actual source passage relevance, complete live model pricing and credentials, and run controlled UAT and Sanskrit scholar review.

This change is intentionally not marked complete or production ready.
