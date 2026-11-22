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

Follow-up integrity audit: same focused command — exit 0, **45 passed**. The Sutrakar must select an actual retrieved Shandilya ID and the complete selected source reaches author and verifier. Durable per-unit attempts and terminal outcomes prevent a restarted run from replaying eligible chapters or silently resetting the three-attempt limit. Publication checks displayed verse, commentary, cases, six guidance strings, and inventoried example section mentions against the validated content. The dispatcher rejects nonfinite prices, freezes role models and run settings across restarts, and enforces a persistent 600-second deadline. OpenAI and Anthropic SDK retries are disabled; Google no longer silently retries through a legacy client. Live adapters fail when provider-reported token usage is absent.

## 14 November bounded live pilot

The user supplied project-specific Google, OpenAI and Claude key paths, the Claude workspace ID path, and a ZIP containing `manuscript.db` and `chroma_db`. Only those explicit credentials were read in process memory; no secret value was printed or written to the repository. Metadata checks confirmed access to the frozen `gemini-3.8-flash`, `gpt-4o` and `claude-sonnet-5-5` IDs. The ZIP was extracted inside an isolated pilot workspace; the original remained untouched. The copied database had ten approved Sanskrit formulations and no structured historical example allocations. The copied Chroma collections contained 100 Shandilya and 23 IKS records. Twenty prior-edition case mentions representing six known entities were extracted from the prior canonical DOCX into the copied historical example register; this is a partial historical identity seed, not a complete book-wide identity certification.

The previous DOC-01–03 text extracts contained command output and tracebacks. They were replaced with UTF-8 extracts from the explicitly supplied original Word manuscripts. Original DOCX SHA-256: DOC-01 `8987a319445e25d1ae86fb4e3ccce06fc9dd8a4454f799407d92cdac0593c63a`; DOC-02 `991b7b041d8bd9a7bfa4a2a2e8ef21268169f42130e651f42962a7f9c289ea92`; DOC-03 `5c79fe9b68c02c63ceb79b8fb24b147c7a2cc26e5c93644d57b1bf08f5a05cdf`. Retrieval now keeps Devanagari combining marks, excludes URL-only and tool-output passages, and uses the Narada theme/English meaning as well as Sanskrit for vector queries. The evidence packet was checked before live dispatch.

The authorized one-candidate pilot used the existing five model assignments and a persisted **USD 5, 30-call, 600-second** ceiling. It stopped when the original window expired. Its ledger contains **11 calls: eight successful, three failed**; **USD 0.5883** of estimated reservations were consumed. Standard-rate estimated cost for observed usage on successful calls is **USD 0.1320**; failed-call billing and actual invoice cost are unknown. The first two Google calls failed on an optional null cache usage field, which was fixed and tested. A researcher response then failed JSON parsing; concise output instructions and fenced-JSON parsing were added. The final Sutrakar consultation call timed out. Google, OpenAI and Anthropic all returned successful calls, but the independent validator was never reached. **No composition attempt, stored draft, fifteen-gate result, scholar/author approval, or publication exists.** The earlier three precomposition technical attempts were reclassified once with an audit record; no provider call ledger, spend reservation, or deadline was reset. The report is in the projectless task's `outputs/council_live_pilot_20261114.json`.

Official standard text pricing checked on 14 November: [OpenAI GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o), [Claude Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [Gemini 3.8 Flash](https://aistudio.google.com/docs/pricing#gemini-3.8-flash). These are estimate inputs, not invoice proof. The isolated environment imported the three official SDKs and Chroma. The timed-out consultation led to configurable per-role timeouts clamped to the persisted run deadline; Google SDK HTTP retries are set to one attempt. Focused offline regression after live-diagnosed fixes: the same command above, with a writable `--basetemp` in the task workspace — exit 0, **54 passed**.

## Second bounded live window, 14 November

The user authorized a further 20-minute window with a **USD 4.40** additional estimated reservation ceiling and **19** additional provider calls, linking the immutable first-window ledger (11 calls, USD 0.5883345 reserved). The same isolated database, exact five roles and model IDs, source extracts, and historical example seed were used. This second window made **14 calls: 12 successful, two failed**, reserving **USD 1.0358525**. The two windows combined made **25 calls** and reserved **USD 1.624187** against the combined ceilings of 30 calls and below USD 5. Successful-call observed-usage estimates are USD 0.132043 in the first window and USD 0.287444 in the second, or USD 0.419486 combined. Failed-call billing and actual provider invoices remain unknown.

Two actual composition calls were made. Both returned incomplete output and were rejected before draft storage; the second had provider finish reason `max_tokens`, 12,748 input tokens and 8,192 output tokens at its configured 8,192 output-token ceiling. The independent validator was never called. **There is no draft, fifteen-gate decision, human approval or publication.** Five combined calls remain, insufficient for the uncached five-role sequence, composition and validator, so paid calls stopped. The second-window report is in the projectless task's `outputs/council_live_pilot_window2_20261114.json`. The original ZIP and source Word files were not changed; prior-edition example identity coverage remains partial.

The runtime now supports a separately reserved per-call composition output ceiling (`COUNCIL_COMPOSE_MAX_OUTPUT_TOKENS`, default 16,384) passed to the same Claude SDK model, with restoration of the frozen adapter setting after the call. Truncated responses retain sanitized finish/usage metadata and cannot be accepted. Validated precomposition role outputs can be checkpointed in the local review SQLite store under an exact hash of the model, request, and registered source-file contents; a resumed run reuses only matching checkpoints. The two completed live attempts predate checkpoint storage, so their response text cannot be reconstructed from audit hashes. Focused offline regression: **59 passed**. A future live run needs fresh explicit authorization with its own limits and linked prior ledgers.

## Outstanding

- A fresh, explicitly bounded live window is needed to continue the one-candidate path. Preserve both spent call ledgers and the two composition attempts; do not claim an eligible draft.
- A Sanskrit scholar and the author must review any future eligible exact draft. Long-form Word rendering remains blocked locally by absent LibreOffice. Historical manuscripts have not been retroactively certified; historical example identity coverage is partial.

Status: source and integration fixes committed locally; live pilot observed across all three providers but did not reach validation. No release or production-readiness claim.


## Reliability correction and completed live generation, 14 November

The subsequent user-approved loop produced one new chapter in three locally retained
unapproved versions using all five unchanged models. The final regression suite passed
64 tests. Latest assessed version: 7 PASS and 8 HUMAN_REVIEW_REQUIRED, no FAIL; full
AI eligibility and human acceptance remain unachieved. Total new reservations
USD 2.71725725, cumulative pilot reservations USD 4.34144425; actual invoices unknown.
No automatic approval or publication occurred. See
[reliability evidence](RELIABILITY_FIXES_20261114.md) and `../LOOP-ENGINEERING.md` for
source-handoff corrections, exact artifacts, call-cap stop and author-review next steps.
