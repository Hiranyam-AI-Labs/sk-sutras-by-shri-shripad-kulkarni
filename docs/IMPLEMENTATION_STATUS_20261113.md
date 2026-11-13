# Fifteen-gate workflow implementation checkpoint

Date: 13 November 2026 (IST). This is an engineering checkpoint, not a release or author approval.

## Implemented locally

- `src/agents/acceptance_policy.py`: versioned fifteen-gate fail-closed evaluator. Deterministic short-form, apparatus presence, 70–110 whitespace-token Marathi Bhashya, two sourced regional cases, three DOs and DONTs, structured business assessment, and duplicate checks. Scholarly gates require explicit evidence; AI eligibility is not author approval.
- `src/database/example_registry.py`: SQLite identity/alias and founder-company relation registry, chapter reservations, rejection release, committed allocations, and author exceptions bound to exact content hash and prior chapters. Source provenance is mandatory on registration.
- `src/orchestration/review_store.py`: immutable draft versions, exact content fingerprints, separate AI/scholar/author states, and a frozen manifest restricted to latest author-approved versions with exact committed example allocations. SHA-256 is an integrity identifier, not provenance proof.
- `src/orchestration/source_evidence.py`: local passage retrieval with source ID, file hash, paragraph location, and verbatim text; prompt handoff assertion.
- `src/orchestration/council_service.py`: injected offline five-role orchestration with Sutrakar arbitration and independent consultation, challenge response by the researcher, bounded revision attempts, persisted drafts, and AI validation stopping at human review.
- `src/providers/dispatch.py`: explicit per-model estimated rate and run cap check before each adapter call; audit stores response hash, usage and finish reason without inventing HTTP status or actual billing cost.
- `src/doc_export/manifest_export.py`: JSON publication input validator rejects mismatched content hashes, non-PASS gates and missing seven-section substantive text; no fallback content is generated. It does not render a Word/PDF book.
- `src/config.py` and the legacy runner no longer create directories, change working directory, hydrate credentials, or mirror to a machine-specific artifact path at import time.
- `scripts/run_dynamic_live_council.py` now exposes a `DynamicLiveCouncilRunner` that routes each role through `BudgetedDispatcher` and `CouncilService`, obtains vector candidates and registered source passages, and returns explicit human-review or partial status. Its former direct-call implementation is private and disabled. The CLI no longer overwrites canonical Python data or publishes a book.
- The legacy runner rejects execution before paid calls. It is not a production replacement until evidence, revision, allocation, approval, and publication flows are integrated end to end.

## Verification evidence

From the repository root, isolated `.venv`:

`./.venv/Scripts/python.exe -m pytest tests/test_council_service.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **17 passed**.

`./.venv/Scripts/python.exe -m pytest tests/test_manifest_export.py tests/test_dispatch.py tests/test_council_service.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **20 passed**.

`./.venv/Scripts/python.exe -m pytest tests/test_live_runner_wiring.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **22 passed** with fake dispatch and no provider network calls.

`./.venv/Scripts/python.exe -m pytest tests/test_live_runner_wiring.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py tests/test_providers.py tests/test_validator_agent.py -q -p no:cacheprovider` — exit 0, **34 passed** including existing provider and validator regressions. Rates must now carry an effective date; a missing model rate blocks the runner before the first call.

`python -m pip install -r requirements.txt` in the isolated environment was interrupted during dependency backtracking; the full suite was not run. Focused test dependencies were installed locally. No live provider calls, deployment, historical manuscript repair, or production migration occurred.

## Blocked and outstanding

- The user explicitly authorized DOC-01–04 and IKS passage payloads for existing provider prompts. Local registered passages replace the legacy canned DOC excerpts and are passed with the Agent 3 bridge to the author and verifier prompts, guarded by a handoff assertion. No live call has been made. Source selection quality still requires verification before execution is re-enabled.
- The live entry point is wired to the injected workflow and dispatch boundary. Full seven-section content authored in the production payload, durable persistence of provider telemetry, Word/PDF renderer integration, editorial assessment of actual source selection and real-provider execution remain outstanding. The current run stops at human review; it does not auto-publish.
- Qualified Sanskrit review and exact author sign-off remain human actions. Existing historical manuscripts have not been retroactively certified.

Status: partial implementation; no commit or release claim.
