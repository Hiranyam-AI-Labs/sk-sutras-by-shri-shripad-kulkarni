# Fifteen-gate workflow implementation checkpoint

Updated: 14 November 2026 (IST). This is an engineering checkpoint, not a release or author approval.

## Implemented locally

- `src/agents/acceptance_policy.py`: versioned fifteen-gate fail-closed evaluator. Deterministic short-form, apparatus presence, 70–110 whitespace-token Marathi Bhashya, two sourced regional cases, three DOs and DONTs, structured business assessment, and duplicate checks. Scholarly gates require explicit evidence; AI eligibility is not author approval.
- `src/database/example_registry.py`: SQLite identity/alias and founder-company relation registry, chapter reservations, rejection release, committed allocations, and author exceptions bound to exact content hash and prior chapters. Source provenance is mandatory on registration.
- `src/orchestration/review_store.py`: immutable draft versions, exact content fingerprints, separate AI/scholar/author states, and a frozen manifest restricted to latest author-approved versions with exact committed example allocations. SHA-256 is an integrity identifier, not provenance proof.
- `src/orchestration/source_evidence.py`: local passage retrieval with source ID, file hash, paragraph location, and verbatim text; prompt handoff assertion.
- `src/orchestration/council_service.py`: injected offline five-role orchestration with Sutrakar arbitration and independent consultation, challenge response by the researcher, bounded revision attempts, persisted drafts, and AI validation stopping at human review.
- `src/providers/dispatch.py`: explicit dated per-model estimated rate and run cap check before each adapter call; SQLite reservations and sanitized metadata persist across process restarts. Audit stores response hash, usage and finish reason without inventing HTTP status or actual billing cost.
- `src/api/routers/review_v2.py` and `src/ui/app.py`: role-specific reviewer credentials and exact version/hash inspection and approval. Author approval commits matching example reservations in the same SQLite transaction; legacy review controls cannot approve a new manuscript version.
- `src/doc_export/manifest_export.py`: Word/PDF renderer reloads a frozen manifest, rechecks current approvals and example allocations, rejects mismatched hashes, non-PASS gates and missing seven-section substantive text, and writes to new edition paths. It does not generate fallback prose.
- `src/config.py` and the legacy runner no longer create directories, change working directory, hydrate credentials, or mirror to a machine-specific artifact path at import time.
- `scripts/run_dynamic_live_council.py` exposes a `DynamicLiveCouncilRunner` that routes five roles through `BudgetedDispatcher` and `CouncilService`, obtains Shandilya candidates and vector-retrieved IKS IDs checked against the local corpus, and returns an eligible count or explicit shortfall. It checks recent and historical Sanskrit formulations for duplicates. Its former direct-call implementation is private and disabled. The CLI does not publish or auto-approve.
- The legacy runner rejects execution before paid calls. The new runner has not been exercised against live providers.

## Verification evidence

From the repository root, isolated `.venv`:

`./.venv/Scripts/python.exe -m pytest tests/test_council_service.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **17 passed**.

`./.venv/Scripts/python.exe -m pytest tests/test_manifest_export.py tests/test_dispatch.py tests/test_council_service.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **20 passed**.

`./.venv/Scripts/python.exe -m pytest tests/test_live_runner_wiring.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py -q -p no:cacheprovider` — exit 0, **22 passed** with fake dispatch and no provider network calls.

`./.venv/Scripts/python.exe -m pytest tests/test_live_runner_wiring.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py tests/test_providers.py tests/test_validator_agent.py -q -p no:cacheprovider` — exit 0, **34 passed** including existing provider and validator regressions. Rates must now carry an effective date; a missing model rate blocks the runner before the first call.

`python -m pip install -r requirements.txt` in the isolated environment was interrupted during dependency backtracking; the full suite was not run. Focused test dependencies were installed locally. No live provider calls, deployment, historical manuscript repair, or production migration occurred.

## 14 November offline verification

`./.venv/Scripts/python.exe -m pytest tests/test_live_runner_wiring.py tests/test_review_v2_api.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py tests/test_providers.py tests/test_validator_agent.py -q -p no:cacheprovider` — exit 0, **38 passed**. Provider responses were synthetic; no paid calls were made. A synthetic frozen edition was exported to DOCX and PDF; PDF text extraction and two rendered PNG pages were checked. Word structure/text was checked with `python-docx`; Word page rendering was unavailable because LibreOffice `soffice.exe` is absent.

## Blocked and outstanding

- The user explicitly authorized DOC-01–04 and IKS passage payloads for existing provider prompts. Local registered passages replace the legacy canned DOC excerpts and are passed with the Agent 3 bridge to the author and verifier prompts, guarded by a handoff assertion. No live call has been made. Source selection quality still requires verification before execution is re-enabled.
- Live role outputs, Sanskrit fidelity, source relevance, prices and credentials still require a controlled user-approved UAT run. The current run stops at human review; human sign-off and edition freeze are separate actions. No real manuscript edition has been exported.
- Qualified Sanskrit review and exact author sign-off remain human actions. Existing historical manuscripts have not been retroactively certified.

Status: offline implementation complete for the scoped integration; no release or production-readiness claim.
