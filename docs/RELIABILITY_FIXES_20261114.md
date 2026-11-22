# Narrow generation reliability correction

Status: reliability implementation and live generation verified; manuscript quality acceptance pending scholar/author review.
Baseline: eb71629, governance 2026.11.11.1. Acceptance: R-01 through R-05 in the active OpenSpec change.

The change retains all five roles and the configured Gemini, GPT-4o and Claude model IDs.
Complete compositions are saved before verification; assessments attach to the same
immutable content version. Exact-request checkpoints now also cover composition and
verification. Composition permits two paid continuations at most; every continuation
uses the existing dispatcher reservation and persistent deadline. Partial outputs stay
in the local audit database and are never marked successful compositions. The initial
preflight represents eight calls. Sourced principal case identities can be enrolled as
pending human review after independent gates pass, preserving repeat restrictions.

## Verification

Working directory: repository root; interpreter: `.venv/Scripts/python.exe`.

`-B -m pytest tests/test_live_runner_wiring.py tests/test_review_v2_api.py tests/test_dispatch.py tests/test_council_service.py tests/test_manifest_export.py tests/test_acceptance_policy.py tests/test_example_registry_unittest.py tests/test_review_store.py tests/test_source_evidence.py tests/test_providers.py tests/test_validator_agent.py -q -p no:cacheprovider --basetemp logs/reliability-tests-2`

Exit 0: **62 passed**. Includes partial-response retention, separately dispatched
continuation, exact composition checkpoint reuse and draft retention after verifier timeout.
Subsequent targeted command: `.venv/Scripts/python.exe -B -m pytest tests/test_council_service.py tests/test_live_runner_wiring.py tests/test_dispatch.py tests/test_review_store.py -q -p no:cacheprovider --basetemp logs/reliability-tests-3` — exit 0, **31 passed**, including previously unknown candidate-example enrollment.
Input hashes are in ignored `logs/reliability-pilot/tested-inputs.json`.

## Live gate and resumption

The prepared pilot uses a copied SQLite database and Chroma index; original archives
remain untouched. Its new reservation limit is USD 3.30, keeping prior USD 1.624187 plus
new reservations below USD 5; deadline is 1,200 seconds and new call cap is 30. These
are estimate reservations, not provider invoice costs. Existing dated rate inputs
are reused; no new price-verification claim is made.

The launch was rejected before process creation by automatic approval review: sending
registered manuscript/source passages and generated review material to the three
external API providers needs explicit payload authorization. No new paid call occurred.
The user subsequently explicitly authorized execution and API use for this action, with generated manuscripts retained locally for author review. The bounded process then started successfully. After approval, execute `logs/reliability-pilot/run.py` with the
project interpreter; inspect its local report, saved draft and fifteen gate results.
Diagnose any failure, apply the smallest correction, rerun affected offline checks,
then resume within the same durable budget/deadline. Never reset a spent ledger.

No scholar/author approval, publication, deployment or quality certification occurred.
UI and document rendering gates are not applicable to this correction; no associated
customer PDF was changed. Sanskrit quality and source/case factuality require live
assessment and human review. Historical example identity coverage remains partial.

Delivery: intended files are staged. The local commit attempt failed because Git author identity is unset; no identity or global setting was invented. No push occurred.


## Completed live engineering loop

The user explicitly authorized external API execution while retaining manuscripts
locally for author review. The isolated run used the unchanged five models, the same
persisted 1,200-second deadline and USD 3.30 new reservation ceiling across both
iterations. It made **30 successful provider calls**, reserving **USD 2.71725725**;
combined with earlier pilots the reservation is **USD 4.34144425**. Provider invoice
cost remains unknown. Thirty calls is the per-action cap; it is not a reset of the
prior 25-call ledgers. Zero new human approvals and zero publication manifests exist.

Iteration 1 stored and independently assessed UDYAM-1 v1, but deterministic checks
rejected a near-duplicate and an incomplete example inventory. Subsequent arbitration
rejected the opening-source pairing. This is a rejected draft, not a new accepted sutra.

Diagnosis: later roles had a thesis but not consistently the full Narada source;
composition lacked the existing-formulation inventory and the already-used example
packet was insufficiently explicit. The correction carries canonical Narada and existing
formulations into author/verifier evidence, explicitly treats allocated examples as
unavailable and prohibits copying formulations from author source manuscripts.

Iteration 2 used the next canonical source unit without resetting deadline or spend.
It produced UDYAM-2 in three complete saved versions:

| Version | Generated formulation | Marathi words | Assessment |
| --- | --- | --- | --- |
| 1 | उद्यमः न्यासप्रेमरूपः | 77 | 7 PASS; 8 HUMAN_REVIEW_REQUIRED |
| 2 | प्रेमरूपो न्यासोद्यमः | 75 | 7 PASS; 8 HUMAN_REVIEW_REQUIRED |
| 3 | प्रेमरूपोद्यमः फलार्पितः | 88 | Verifier NOT RUN: call cap reached; pending draft retained |

These are revisions of one chapter, not three distinct new book chapters. V2 is the
latest independently assessed version. Remaining review gates concern source/analogy
interpretation, Sanskrit formulation, IKS/Yoga grounding and factual example provenance.
The first two versions use different principal identities from the known historical
seed; complete book-wide identity coverage is still not certified. No gate was waived.

Technical generation/retention goal: PASS. All-fifteen-gate AI eligibility: NOT ACHIEVED.
Scholar/author acceptance: PENDING. The final draft survived the blocked validator call,
which demonstrates the draft-retention correction with a real provider sequence.
No truncation occurred in this run, so continuation recovery is covered by offline
regressions rather than a live truncation event.

Final offline suite: same 11-module command above with basetemp
`logs/reliability-source-handoff-tests`, exit 0, **64 passed**. This includes the
live-diagnosed canonical-source/canon handoff regression.

Local-only evidence and author copies (ignored by Git):
`logs/reliability-pilot/report-iteration1.json`, `report.json`, `manuscript.db`,
`UDYAM-2-draft-v1.json` through `UDYAM-2-draft-v3.json`, and
`UDYAM-2-v1-AUTHOR-REVIEW.txt` through `UDYAM-2-v3-AUTHOR-REVIEW.txt`.
Exports were checked against exact stored JSON and visible formulation. They are
explicitly labelled unapproved review copies, not publication exports.

Next action: author and Sanskrit-scholar review of assessed v2 with its gate report;
verify and register case/Yoga/Shandilya references before any eligibility/publication
claim. Repeated calls alone cannot establish missing human/source evidence.
