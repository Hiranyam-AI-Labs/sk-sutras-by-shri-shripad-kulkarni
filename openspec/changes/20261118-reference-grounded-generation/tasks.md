# Execution evidence

- Architecture and historical paid-run review: completed; legacy runner limited to20 and old export boundaries unsuitable.
- Model metadata: all three configured model IDs accessible after supplying required Anthropic workspace header. Metadata is not inference success or a balance check.
- Public reference research:28 located passages across17 works;3 edition-check items excluded pending verification.
- Four-voice council, structural acceptance, V19 exporter and paid runner: implemented with shared thematic discussion, one substantive repair limit and a separate Claude guard. All five existing models unchanged.
- Offline tests before batch optimization:163 council/acceptance/export tests passed;19 runner/SDK contract tests passed. Batch optimization and Claude guard require their own checks before inference.
- Source plan check: PASS;100 briefs,20 chapter groups,200 immutable cases,117 available and40 assigned source passages,839 forbidden strings.100 is a working target, not a ceiling.
- Updated batch/cost tests:42 runner/batch/guard tests passed; sidecar123 council/runner tests passed. Renderer25 tests passed. Fixture opening9pages and closing pixel-identical at two raster scales. These are scoped offline results, not full-product certification.
- Paid pilot1: PASS,18calls,3-word/30-character formula,672 Marathi exposition words, no repair. Reservations$0.861013total/$0.524812Claude. Usage-based estimates$0.550344total/$0.418670Claude, not invoices.
- Actual reviewed pilot:19pages, all visually inspected; first9andclosing pixel-identical at two scales, formula/cases/rawprovidertext preserved. Two source-supported editorial overlays recorded separately from model verdicts. DOCX SHA256a717adc9949b60f1a817640ac02d777c1c523088230557dea04c3a812494a257.
- Shared five-entry pilot: saved discussion reused across resumes. Diagnosed/recovered an OpenAI nested-key omission and Claude proposal truncation. Sonnet5.5 adaptive thinking defaults high and counts toward max_tokens; now high for proposals/composition, medium for routine discussion. Truncated responses are retained and stop immediately instead of being retried as schema errors. Explicit one-stage recovery records preserve failed attempts and costs.
- Candidate5 remains REVIEW_REQUIRED after one full repair and one validator reconsideration. No further Claude spending on it. User count flexibility supports quarantine, never weakened acceptance. Optional filtered-run/export path includes only PASS entries, preserves rawsource IDs and records sequential displayed numbering. Offline smoke tests verify excluded drafts cannot enter the book.
- Candidate6 passed. Shared pilot1..6 yielded five accepted drafts and one held draft; the next batch completed discussion but two consecutive composition-review holds stopped the run at9.
- Diagnosed a prompt conflict: a semantic ban over a mixed author/classical formula ledger contradicted the intended modern business interpretation. Corrected the future prompt and performed exactly one independently logged policy review for each of5,8,9, using the existing GPT-4o validator. All three still returned REVIEW_REQUIRED. No original review was replaced and no Claude call was made for this recovery. Paid generation remains stopped; do not reset the stop or retry until a separately justified calibration resolves the problem.
- Six saved candidates1,2,3,4,6,7 pass automated structural and independent review; candidates5,8,9 remain excluded. This is a partial review edition, not a complete100-sutra book or complete reader journey. Local editorial checks also identified qualifiers, grammar notes and semantic overlap risks; recorded overlays do not imply scholarly approval.
- Latest scoped tests before recovery:172 council/runner/batch/narrow-repair/exclusion tests passed in84.81s. A sole400–499word shortfall with substantive reviewerPASS now permits one append-only exposition paragraph instead of a full rewrite, followed by both full checks. No tests called paid providers.
- Final paid accounting:85 calls across all phases,40Claude; combined reservations$6.526232, Claude reservations$4.035906. Reported-token estimates$4.55775425combined/$3.393444Claude; invoices unknown. Guards remain$35cumulativeClaude and$59.817801combinedreservation ceiling. No process continues in the background.
- Scale decision: FAIL for unattended100-entry production under current quality gates. Models and four-discussion/fifth-validator separation remain unchanged. Preserve all checkpoints; first calibrate the validator against evidence-labelled examples and provide decision-context comparisons before considering another paid scale attempt.
- Final six-entry Word rendering and preservation checks: PASS.38pages individually inspected;20/20protected first-nine/closing pixel comparisons at two scales passed; protected XML/style/footer/source hashes match; six centered formulas,12caseidentities, sequential numbering, citation targets and Marathi comparative prose checked. Accepted V19 manual-break justification spacing is recorded, with no clipping/overlap/glyph loss. DOCX SHA256af3ee31c19d6ab2234b0f8dee0ce358a9f2baef20e898f96ddae2d78dc70a0fa.76 export/audit/editorial tests passed in4.77s. Packaged LibreOffice remains unavailable; hidden WordCOM/PDFium fallback documented, not claimed as packaged-renderer success.
- Packaging: local review artifact only. Standalone portability and scoped commit deferred because the new workflow depends on untracked legacy modules, pre-existing dispatch edits, ignored historical evidence and local template/credential paths. packaging_review.json lists exact dependencies and runtime versions. No unrelated staged work was committed or pushed.
- Author/scholar approval: PENDING; never automated.

## Approved validator reliability implementation — 2026-11-18

- Implemented isolated fifth-agent review of the current draft, canonical sources and prior business decisions; removed peer/prior-verdict anchoring from this path. All five roles/models remain unchanged.
- Added typed, evidence-bearing objections, locally checked mechanical claims, structured scholarly uncertainty, immutable input-bound review caching, and exact reviewed-text binding through export. Generic pending author approval cannot itself block an otherwise sound review copy.
- Prepared targeted corrections for saved candidates5,8,9 without paid composition. The first unchanged candidate requires calibrated review, candidate8 needs the Biocon factual qualification, and candidate9 restores the already-saved responsibility/equanimity formulation and correct grammatical derivation. No manuscript publication or automatic author approval.
- Added a mandatory ten-case balanced calibration gate before production credential access, source/fixture provenance checks, cumulative $1 calibration reservation accounting, and serialized execution. A stale correction cannot silently reuse a saved repair from another seed.
- Initial GPT-4o calibration FAIL:8calls,$0.364395reserved,0Claude; generic uncertainties blocked four positives, planted source/case errors were missed, and a false word-count objection stopped the eighth probe. Raw failed evidence retained.
- Diagnosed follow-up v2.2 presents exact claims alongside canonical passages/cases and computed objective counts. The same ten drafts and expected labels remain frozen; v2.1 fixtures archived. No relabeling to force a pass. Projected follow-up reservation$0.4917975, cumulative$0.8561925. Full generation remains BLOCKED pending all ten passes.
- Offline verification before follow-up:187 affected tests PASS plus13 calibration/provenance tests PASS. Additional execution-lock and production-gate tests pending. No Claude calls or new book generation during this phase.

### Final outcome of the approved reliability phase

- Offline PASS:391 tests across three non-overlapping suites (187review/runner/export/audit/fixture/integration,30calibration/provenance/gate/lock,174council/batching/repair/spend). Calibration lock and mandatory run-ID accounting are covered. Tracked diff whitespace check PASS. These verify implementation controls, not semantic/Sanskrit correctness.
- Follow-up v2.2 FAIL on its first probe. The validator returned AUTHOR_REVIEW on explicitly qualified modern analogies and put SOURCE_DISTORTION in the uncertainty list, outside the allowed concrete uncertainty categories. The exact raw response and invalidity reason remain in independent_review_v2.db. Remaining nine probes NOT_RUN; no result was converted into PASS.
- Current-phase paid total:9GPT-4o calls,$0.4126475reserved; reported-token estimate$0.1481525, invoice unknown;0Claude. All-phase ledger94calls/$6.9388795reserved. No further paid process is active and no approved calibration record exists.
- Full generation BLOCKED by the user's explicit conditional authorization, not by missing permission. No new full book produced. All four original document hashes match: author104-entry consolidation, latestsix-entry review, V19opening template and protectedclosing template.
- Evidence: logs/author-research-generation-20261118/validator_reliability_final_evidence.json and validator-calibration-v22-report.json. Implementation remains local; unrelated staged work and legacy dependency ownership prevent a clean isolated commit. No push, publication or author approval.
- Next technical gap: demonstrate reliable distinction between an attributed modern analogy and a false claim about a source. A further diagnosed change should test that distinction with paired positive/negative controls, retain genuine ambiguity for human review, and pass the unchanged balanced semantic suite before Claude or full production. Do not weaken uncertainty handling, accept an invalid response, silently substitute models, or spend on unchanged retries.

### v2.3 — Approved analogy/attribution correction

- User authorized this targeted fix and a small calibration; Claude/full generation remains conditional and is not part of this calibration execution.
- Added mandatory source_checks before the overall verdict: exact comparison/source identity, separately quoted historical claim and modern application, canonical passage, classification and concise reason. Every supplied comparison must be covered exactly once. FALSE_ATTRIBUTION/DISTORTED_MEANING must have a matching blocker; UNRESOLVED_SOURCE needs a concrete source uncertainty; resolved qualified analogies cannot simultaneously be held for generic source uncertainty.
- A synthetic rubric contrast teaches the difference between modern application, an invented historical rule, and the same invented rule with an appended disclaimer. It contains no evaluation labels or manuscript source facts. No substring-based automatic semantic PASS was added.
- Closed ancestor-field and wrong-source consistency bypasses. Calibration now requires the exact expected defect categories/rules, with no extra uncertainties, rather than merely containing the expected category. Frozen ten-case contents and labels remain unchanged; v2.2 input archived.
- Offline pre-calibration checks:273 tests passed before the final two audit regressions; final checks pending. Projected ten-call reservation$0.5158225; previous calibration reservations$0.4126475; total remains below$1. No paid call in this v2.3 phase yet.

- v2.3 live result: four positive controls PASS, including the three corrected held drafts. Exact-copy control incorrectly received READY. The false-attribution control was correctly classified and explained but the response omitted a duplicate evidence.contradiction field, so strict parsing stopped after6calls ($0.3133725reserved,0Claude). Overall calibration FAIL; remaining four controls NOT_RUN. This establishes improved analogy handling, not production readiness.
- Diagnosed v2.4 follow-up: keep mandatory issue.reason as the explanation instead of requiring the same explanation again in SOURCE_DISTORTION/CASE_FACT evidence. Add mandatory objective-violation/copy coverage so a model cannot pass a draft while omitting a measured failure. No model change or automatic acceptance; frozen ten-case content/labels unchanged.
- Automatic approval review rejected a proposed generalized cumulative$2 budget allowance. Replaced it with a narrower fixed-round guard: only v23/v24 share a$1 new-round ceiling, and the exact nine historical calls/$0.4126475 must still match the ledger. No arbitrary run IDs receive a fresh allowance. The projected current-round total is$0.83526, including v2.3; historical total$1.2479075. This is the newly authorized targeted calibration round, not an increase in Claude/full-generation permission.

### Final v2.4 evidence — calibration remains FAIL

- Final offline suite:369tests PASS in21.59s. Source classification, current-text grounding, exact defect/rule scoring, objective omission, budget locks, export binding and cache recovery covered. This is code/control verification, not semantic certification.
- v2.4 controls001–004 PASS. Control005 correctly identified EXACT_COPY but used field `formula` instead of `new_sutra`. Added a narrowly scoped objective-field normalizer requiring the entire exact current formula and subsequent full predicate/comparator validation. The original failed raw response remains intact; one explicit, hashed recovery record allows zero-call replay without changing REVISION_REQUIRED to PASS. Four positive cached responses also replayed without API calls. Audit33/33assertions PASS.
- Control006 again correctly classified FALSE_ATTRIBUTION and supplied a grounded blocker, but its separate source_claim_quote paraphrased the canonical meaning instead of quoting the current draft. Strict validation rejected that invented quotation. It was not normalized, rewritten, recovered, or accepted. Controls007–010 NOT_RUN. No approved calibration record exists.
- Current newly authorized round:12GPT-4o calls across v23/v24, $0.6303825reserved; reported-token estimate$0.296985, not invoice;0Claude. No further paid process active. Full generation remains BLOCKED because the complete calibration has not passed, despite improvement in the targeted distinction.
- All five models unchanged. Original104-entry consolidation, six-entry review, V19opening and closing documents have unchanged hashes. No new manuscript, commit, push, automatic author approval or publication.
- Evidence: logs/author-research-generation-20261118/analogy_validator_final_evidence.json, validator-calibration-v24-report.json, archived stopped-at005 report, v24_field_alias_recovery.json and v24_alias_offline_verification.json. Prior failures and exact fixture contents/labels preserved.
- Remaining technical gap is reliable evidence selection/serialization. A next diagnosed change should let the validator select references to supplied text and materialize quotations deterministically, rather than regenerating redundant quote strings. It must retain independent semantic judgment and pass all unchanged controls; the present invalid source quote cannot authorize generation.

### v2.5 — Approved evidence-reference selection

- Implemented typed, content-bound draft/source/case references, comparison-specific selection menus and deterministic quote materialization. The model supplies judgments and selected IDs; it cannot provide replacement quotations or field names. Unknown/stale/wrong-type references, wrong source/comparison/case ownership and misplaced objective objections reject.
- Kept all canonical semantic, source-consistency, objective-limit, exact-copy and duplication checks. Raw provider responses and selected-reference audit records persist. No generated-quote fallback, automatic retry, forced PASS or reuse of failed v2.4 quotation responses.
- Production calibration identity now covers both the reviewer and evidence resolver. All five agents/models and four-discussion/fifth-independent architecture preserved. Original manuscripts/templates untouched.
- Same ten complete fixture records/labels preserved; v2.4 archived and v2.5 manifest frozen. Offline:442tests PASS (206canonical/cache plus236selector/calibration/fixture/integration/export/audit/runner); targeted field-grounding audit8/8PASS.
- New user-authorized v25 round limited to this exact run ID and$1, verifying historical21calls/$1.04303 before every reservation. Previous guards unchanged. Ten-call projection$0.6623475. Paid calibration NOT_RUN at this checkpoint; Claude/full generation NOT_RUN.
- Pre-call proof: logs/author-research-generation-20261118/v25_offline_verification.json and validator_calibration_v25_refresh.json. Scope remains local; mixed existing index/dependency ownership still prevents an isolated release commit.

### Final v2.5 result — evidence selection works; duplicate-decision control fails

- Final offline verification:476tests PASS in25.22s. Strict reference typing/ownership, content hashes, objective-field binding, raw-response retention, mandatory semantic gates, production blocking and budget limits covered.
- All ten live responses materialized using supplied references. Controls001–009 PASS, including qualified analogies, false attribution, exact copying, invented business facts and both mechanical negatives. Control010 incorrectly returned READY for a different formula with an identical business summary and action. Expected DUPLICATE_DECISION remained unchanged; overall calibration FAIL.
- Control007 initially supplied both business owner identity and canonical evidence ID. Added explicit compatibility only when both IDs match the exact same current case. An audited, zero-call recovery preserved the original FAILED row/raw response and retained REVISION_REQUIRED. Six earlier positives/negatives replayed without new calls. No generated-quote fallback or verdict rewriting.
- Replay audit found an empty-record truthiness bypass; fixed by unconditional record validation for FAILED rows. Empty/null/list/falsy and tampered records reject. Final targeted audit14/14PASS; original failure/recovery evidence retained.
- Paid round:10GPT-4o calls,$0.6623475reserved under$1; reported-token estimate$0.3713475, invoice unknown;0Claude. All phases116calls/$8.2316095reserved. No paid process remains active.
- Production gate verified BLOCKED before credentials: no approved calibration record exists. No Claude, full generation, new book, automatic author approval or publication. All five models and four original document hashes unchanged.
- Evidence: logs/author-research-generation-20261118/evidence_reference_validator_final_evidence.json, validator-calibration-v25-report.json, archived stopped-at007 report, v25_case_reference_recovery.json and v25_recovery_offline_verification.json.
- Remaining gap is semantic duplication detection. The next scoped change should require an explicit comparison of business decision and action against prior chapters, preserving the positive distinct-decision controls and the failed duplicate control. Do not relabel it, accept nine of ten, or authorize production from the current READY response.

### v2.6 — Decision/action comparison: calibration PASS

- User authorized this narrow fix, offline verification and one small calibration. All five roles/models remain unchanged. Added paired current/prior business decisions and actions with mandatory per-chapter DISTINCT, SAME_DECISION or EXACT_COPY judgments. Missing comparisons, contradictory blockers and omitted exact decision/action matches fail closed; semantic paraphrases still require the independent model's judgment.
- The same ten complete fixture records and expected labels are unchanged. Different practical decisions sharing a philosophical theme remain eligible. Duplicate objections select the prior chapter identity; code retrieves supplied decision/action text instead of generating quotations.
- Pre-call offline checks passed524 tests. Final affected runs passed555 unique tests:445 validator/selector/calibration/fixture tests in19.57s and110 runner/export/audit/editorial tests in6.13s, both exit0. Focused audits passed33decision checks and23case-reference/recovery probes.
- Live control007 correctly rejected the invented business fact but selected a supplied business-case owner ID instead of its hash ID. Added lookup only for a unique canonical case owner, retaining current-example ownership and all grounding checks. Preserved its original FAILED row/raw response, archived the stopped report, and recorded explicit immutable zero-call recovery. No judgment or expected outcome was rewritten. Controls001–006 replayed from their cache,007 replayed through the audited recovery, and only008–010 required new calls.
- All ten live controls PASS: four legitimate positive controls READY; exact copying, false attribution, invented case facts, overlong formula, short exposition and duplicate decision each correctly rejected. Control010 explicitly selected PRIOR-002 as SAME_DECISION despite different Sanskrit wording. The distinct-decision control003 remained READY.
- Production require_validator_calibration accepted the exact current implementation, rubric, fixtures and revision hashes without initializing a provider. validator-calibration-approved.json now exists as technical calibration evidence; it is not author approval. No Claude calls, full generation, new manuscript or publication occurred in this phase.
- Current round:10GPT-4o calls, $0.6941925 reserved under the fixed$1 cap; reported-token estimate$0.4003825, invoice unknown. All-phase ledger126calls/$8.925802reserved; historical Claude calls unchanged. No paid process remains active.
- Four protected original book/template hashes match. Evidence: logs/author-research-generation-20261118/duplicate_decision_validator_final_evidence.json, validator-calibration-v26-report.json, v26_case_owner_recovery.json and v26_recovery_offline_verification.json. The ten-control gate is cleared; future manuscript judgments and scholarly review are not guaranteed by calibration. Existing local packaging/commit limitation remains; no unrelated staged work was committed or pushed.


## Authorized full-book-v26 resume — 2026-11-18

Checkpoint recorded 2026-11-18T19:30:22+05:30; parent-reported state, not a new sidecar provider execution. Preserve all earlier task/history entries.

- [x] Record explicit user authorization to resume the 100-entry working target under `full-book-v26` after v2.6 calibration.
- [x] Record parent-reported active run limits: $50.891999 run cap; $35 durable cumulative Claude reservation cap, with historical reservations retained.
- [x] Record parent-reported checkpoint: saved entries 001–008 now PASS. Technical PASS remains distinct from editorial, semantic and author/scholar approval.
- [ ] Parent: finish or stop the run according to existing budget/provider/quality gates; record actual completed and held entries. Do not infer 100-entry completion from this checkpoint.
- [ ] Reassess selected outputs: canonical cases unchanged and globally distinct, selected reference IDs/evidence present, review hashes bound to exact text, 2–4-word/32-character formulas, and exposition of at least 500 Devanagari word tokens.
- [ ] Review significant source/case overclaims, Sanskrit grammar, Marathi-only reader text and repeated business decisions/actions; preserve pending author decisions.
- [ ] Reconcile run and all-phase calls, provider/model IDs, tokens, reservation consumption and usage-based estimates; retain failed/truncated-call accounting and distinguish estimates from invoices.
- [ ] Parent: export/render the final V19 review artifact, verify protected first-nine/closing pages and source/template preservation, and inspect numbering, citations, formulas and case records.
- [ ] Parent: append final results, accounting and QA evidence. Final results remain PENDING; no publication or automatic author approval.


### 2026-11-18 — Entry-020 decision-check recovery and same-run resume

Recorded 2026-11-18T19:55:01+05:30; execution and test results below are reported by the parent, not independently rerun by this documentation sidecar. Production stopped at entry 020 because the raw independent review omitted 18 of its 19 required decision checks. The original FAILED response and its audit remain preserved; the decision-coverage requirement was not relaxed.

Added an explicit, one-attempt complete GPT-4o re-review with all existing checks retained. Parent reports 555 existing tests plus 27 new tests PASS. The same ten frozen calibration controls all PASS through cached replay using retained pre_v2 provenance; the replay callback forbids API access. Calibration is bound to the current implementation. These cached results are not ten new live model observations.

One paid GPT-4o recovery then returned entry 020 READY with all 19 decision checks. Reported reservation increment: approximately $0.0922225 ($5.71991675 minus $5.62769425); zero Claude calls for this recovery. Reservation consumption is not an invoice. The same `full-book-v26` run resumed entries 001–020 from cache without new paid calls for those entries; entry 021 composition is ongoing at this checkpoint.

Phase-final results remain PENDING. The parent retains run control and will record the final completed/held set, accounting and artifact QA. This recovery does not grant automatic author/scholar approval, certify all future chapters, or establish completion of the 100-entry target.

- [x] Record entry-020 missing-decision-coverage stop and preserved original FAILED evidence.
- [x] Record bounded one-attempt recovery, parent-reported 582 passing tests, and ten cached frozen controls PASS with API-forbidden replay/current implementation binding.
- [x] Record paid recovery READY with 19/19 decision checks, its reservation delta and zero Claude recovery calls.
- [ ] Parent: finalize the resumed run and append final validation/accounting; entry 021 composition is ongoing and phase-final results are PENDING.


### 2026-11-18 — Entry-022 truncated composition; bounded continuation preparation

Recorded 2026-11-18T20:03:54+05:30; this checkpoint records the parent's reported execution/test evidence. Twenty-one chapters PASS. Production stopped at entry 022 when the Sutrakar response reached its 14,000-token maximum at high effort. The saved partial response contains six complete fields: title, formula, grammar, translation, exposition (reported 601 words), and references. No final entry-022 draft has been accepted. The raw HARDFAILED attempt and partial response remain preserved.

Preparation is underway for one explicit continuation using the same Sonnet model, a 6,000-token ceiling and medium effort, requesting only the seven missing fields while preserving the six recovered fields exactly. Continuation-helper tests are PENDING. This is preparation, not evidence that the continuation has run, passed validation or produced an accepted draft.

For future full compositions, the parent reports increasing the output ceiling from 14,000 to 18,000 tokens while keeping high effort and the same model. Seventy-four runner/effort/spend/narrow-repair tests PASS in 3.36 seconds. The reported additional reservation is $0.04 per full composition call; existing budget caps remain unchanged. These passing tests do not cover the still-pending continuation-helper checks.

Reported accounting at this checkpoint: current resume 82 calls / $7.4282205 reserved; all phases 208 calls / $16.3540225 reserved; cumulative Claude reservations $8.33924. Reservations are not invoices. No API process is currently running. Final-book results remain PENDING; the parent owns any subsequent execution, acceptance checks, accounting and final artifact QA.

- [x] Record 21 passing chapters and entry-022 truncation with six complete saved fields; no accepted final draft.
- [x] Record preservation of the raw HARDFAILED attempt and exact-field continuation constraint.
- [x] Record 74 runner/effort/spend/narrow-repair tests PASS in 3.36 seconds for the future full-composition ceiling change; model/high effort and caps unchanged.
- [ ] Complete continuation-helper tests; currently PENDING.
- [ ] Parent: execute at most the explicitly prepared same-model continuation, if its required checks pass, then validate the merged result without modifying the saved failure or recovered fields.
- [ ] Parent: record subsequent run results and final-book QA/accounting. No API process is active at this checkpoint; final book PENDING.


### 2026-11-18 — Entry-025 local exposition repair; fresh review pending

Recorded 2026-11-18T20:24:59+05:30; parent-reported checkpoint. Generation is paused with 24 entries PASS. Entry 025 has an actual 499-word exposition shortfall; the validator also selected example 0 incorrectly for decision evidence. Neither defect is represented as a passing review.

The parent prepared a 43-word Marathi safe-practice paragraph in `editorial_exposition_additions.json`, bound to the exact seed. No formula or example changes are included. Council `editorial_additions` handling and the runner loader skip already-amended saved seeds, apply the addition once, and retain `local_editorial` provenance with zero provider calls for the local addition. A fresh independent review is mandatory; local word-count repair does not supply or override that review.

Ten focused tests PASS, including the three-resume regression for single application. The broader 197-test run is ONGOING; its result is not yet claimed. The independent-review implementation is unchanged, so the parent reports its existing calibration remains valid. No further Claude call is part of this repair checkpoint.

Generation remains PAUSED at 24 PASS. Fresh independent review, subsequent generation and final-book results are PENDING. The parent retains execution and finalization ownership; this documentation update neither resumes the run nor grants author approval.

- [x] Record entry-025's actual 499-word shortfall and invalid example-0 selection in validator decision evidence.
- [x] Record the exact-seed-bound 43-word local Marathi addition, unchanged formula/examples, zero-call provenance and apply-once handling.
- [x] Record 10 focused tests PASS, including three-resume regression coverage.
- [ ] Complete broader 197-test run; currently ONGOING.
- [ ] Obtain and record a fresh independent review of the locally amended draft; no inherited PASS or automatic verdict override.
- [ ] Parent: record subsequent execution and final-book results. Current generation PAUSED at 24 PASS; no further Claude call for this repair.


### 2026-11-18 — Entries 024–025 comparison-coverage recovery; same-run resume

Recorded 2026-11-18T20:26:38+05:30; parent-reported execution and test results. Entry 025's fresh review of the amended 542-word exposition returned READY but omitted a required comparison. That incomplete response did not satisfy all checks. The existing one-attempt GPT recovery identified by the supplied prefix `ddd7a540...` subsequently passed all checks. No additional Claude call was used for the entry-025 editorial addition.

The parent also reports successful prior comparison-coverage recovery for entry 024, identified by the supplied prefix `369ad883...`. These identifiers are recorded as supplied prefixes, not invented complete hashes. Recovery results remain distinct from the original incomplete responses; missing coverage was not waived or silently filled.

Updated verification: 198 integration tests PASS in 75.22 seconds, plus 10 focused tests PASS. This supersedes the earlier checkpoint's ongoing broader-test status. The same `full-book-v26` run has resumed, with a reported reservation checkpoint of approximately $8.9405. Reservations are not invoices, and this rounded checkpoint is not a final accounting total.

Final generation results, final accounting and final-book QA remain PENDING. The parent retains run control and finalization. This sidecar updates documentation only; no code, provider call, budget change or author approval.

- [x] Record the amended entry-025 exposition at 542 words and the fresh READY response's missing comparison; incomplete coverage did not pass all gates.
- [x] Record existing one-attempt GPT recovery `ddd7a540...` passing all checks, with no additional Claude call for the local edit.
- [x] Record entry-024 comparison-coverage recovery `369ad883...` succeeding.
- [x] Record 198 integration tests PASS in 75.22 seconds plus 10 focused tests PASS; broader verification is no longer pending.
- [x] Record same-run `full-book-v26` resume and approximately $8.9405 reservation checkpoint.
- [ ] Parent: complete or stop subsequent execution under existing gates, then record final accounting and artifact QA. Final-book results remain PENDING.


### 2026-11-18 — Entry-026 PASS; typed-archive loader fix and batch 027–031 discussion

Recorded 2026-11-18T20:32:35+05:30; facts reported by the parent. Current checkpoint: 26 entries PASS, no exclusions. Entry 026's comparison-coverage omission was recovered through one GPT review identified by the supplied prefix `ed051ed7...`, yielding READY. The prefix is retained as supplied; no complete identifier is inferred.

The generic typed-archive entry-024 seed-loading bug was fixed in `load_draft_overrides`: typed archives are skipped while legacy override handling is retained. Reported verification: 38 tests PASS in 5.01 seconds, plus 12 focused tests PASS in 1.63 seconds; the real entry-025 seed-hash check also PASS. These are reported scoped results, not a final book-wide validation.

Entries 001–026 replayed from cache without new paid calls. The same process is running batch 027–031 discussion. Current-run reservation checkpoint is approximately $9.3297; this is a reservation amount, not an invoice or final total. Final generation results, accounting and artifact QA remain PENDING.

- [x] Record 26 entries PASS with no exclusions and entry-026 one-GPT coverage recovery `ed051ed7...` yielding READY.
- [x] Record `load_draft_overrides` skipping typed archives while retaining legacy overrides; 38 tests PASS (5.01 seconds), 12 focused tests PASS (1.63 seconds), and real entry-025 seed-hash check PASS.
- [x] Record cache-only replay through entry 026, batch 027–031 discussion running in the same process, and approximately $9.3297 current-run reservations.
- [ ] Parent: append subsequent results and final validation/accounting. Final-book results remain PENDING.


### 2026-11-18 — Thirty-five PASS; supervisor stop at entry-036 truncation

Recorded 2026-11-18T20:57:16+05:30; parent-reported checkpoint. Entries 032–035 passed, bringing the saved set to 35 passing entries with no exclusions. Coverage failures for entries 028, 029, 030, 031, 032 and 035 were handled. Entry 035 underwent one content revision before READY.

The supervisor was updated to allow the exact cached-review error only with proof of the original FAILED coverage failure and its hash binding. Reported verification: 22 supervisor tests PASS in 1.93 seconds. Recovery remains limited to one per key, at most 100, under fixed caps and a single process. This is a bounded diagnosed-error path, not permission to retry arbitrary failures.

At entry 036, a provider truncation at the 18,000-token ceiling was not recognized as a recoverable supervisor condition. The supervisor correctly STOPPED without an automatic retry. Preparation is underway for a missing-three-field continuation based on ten complete saved fields. No continuation execution, merged acceptance or entry-036 PASS is claimed here. No API process is currently running.

Final generation results, accounting and artifact QA remain PENDING. The parent retains continuation/run control and finalization; this sidecar records supplied facts only.

- [x] Record 35 passing entries, no exclusions, handled coverage failures for 028/029/030/031/032/035, and entry-035 READY after one content revision.
- [x] Record 22 supervisor tests PASS in 1.93 seconds for the exact cached-review error path with original FAILED coverage/hash proof; one recovery per key, at most 100, fixed caps and single process.
- [x] Record entry-036 18,000-token truncation causing a correct supervisor STOP without automatic retry; no API process active.
- [ ] Parent: finish preparation and validation of the explicit three-missing-field continuation using ten complete saved fields; execution and acceptance remain unclaimed.
- [ ] Parent: append subsequent results and final accounting/artifact QA. Final-book results remain PENDING.


### 2026-11-18 — Entry-036 continuation structurally accepted; independent review pending

Recorded 2026-11-18T21:00:50+05:30; parent-reported evidence. Forty-seven continuation tests PASS, including the actual entry-036 preparation. One continuation using the same Sonnet model, a 6,000-token ceiling and medium effort filled the three missing fields. All ten complete saved fields were preserved. The merged entry passes structural assessment; independent review remains PENDING, so no entry-036 final acceptance is claimed.

Evidence is recorded in `logs/author-research-generation-20261118/chapter036-continuation-evidence.json`. This sidecar records the parent's report and evidence path without independently reopening the artifact or running providers.

Reported reservation checkpoint: current run $16.51003525; cumulative Claude $13.449646. Reservations are not invoices or final accounting. The single supervisor has resumed with the current core unchanged and all model assignments retained.

Final generation results, independent-review outcome for entry 036, final accounting and artifact QA remain PENDING. The parent retains execution and finalization ownership.

- [x] Record 47 continuation tests PASS, including actual entry-036 preparation.
- [x] Record one same-Sonnet 6,000-token/medium-effort continuation filling three missing fields, preserving all ten complete fields, and passing structural assessment.
- [x] Record `chapter036-continuation-evidence.json`, current-run reservations $16.51003525, cumulative Claude reservations $13.449646, and single-supervisor resume with unchanged current core/model assignments.
- [ ] Parent: complete and record entry-036 independent review; currently PENDING.
- [ ] Parent: append subsequent generation, final accounting and artifact QA results. Final-book results remain PENDING.


### 2026-11-18 — External Claude credit stop after 42 PASS; export QA pending

Recorded 2026-11-18T21:15:22+05:30; parent-reported current stop. Forty-two entries PASS. During discussion for batch 043–047, Claude returned an HTTP 400 low-credit error. The current blocker is external provider credit, not a validator rejection. No process is active. The asynchronous user response concerning credits is pending; no credit purchase, funding approval or restart is inferred from that pending response. The 100-entry goal remains UNFINISHED.

Current-run accounting: 218 calls, comprising 101 Claude, 86 OpenAI and 31 Google calls; reservations $20.69834525. All-phase accounting: 344 calls / $29.62414725 reserved. Cumulative Claude reservations are $15.853638, below the unchanged $35 guard. Available provider credit and the local reservation guard are separate constraints; being below the guard does not resolve this credit failure. Reservations are not invoices. Parent usage evidence: `logs/author-research-generation-20261118/full-book-v26-usage-at-credit-stop.json`.

A QA agent is working on the 42-entry export. Export/rendering QA is ONGOING, and no final artifact-quality or delivery claim is made here. Original documents are reported preserved, with final rehash verification PENDING. Author approval remains PENDING and is not supplied by technical PASS or the user's generation authorization.

The current generation stop is recorded, but final delivery/QA results remain PENDING. The parent owns the credit-response follow-up, any authorized resume, final accounting reconciliation and final artifact evidence.

- [x] Record 42 PASS and batch 043–047 discussion stopped by Claude HTTP 400 low credit; external credit blocker, not validator failure.
- [x] Record no active process and pending asynchronous user credit response; no funding approval or restart implied.
- [x] Record current-run 218 calls (101 Claude / 86 OpenAI / 31 Google), $20.69834525 reserved; all phases 344 calls / $29.62414725; cumulative Claude $15.853638 below the $35 guard.
- [x] Record parent usage artifact `full-book-v26-usage-at-credit-stop.json`.
- [ ] QA agent/parent: finish 42-entry export QA and append verified artifact results; currently ONGOING.
- [ ] Rehash protected original documents/templates before claiming final preservation verification; currently PENDING.
- [ ] Parent: resolve the external-credit response before any authorized resume. The 100-entry goal remains UNFINISHED.
- [ ] Obtain author review/approval separately; PENDING. No final delivery or QA-success claim at this checkpoint.


### 2026-11-18 — User supersedes generation target with final 42-entry Word review edition

Recorded 2026-11-18T21:19:54+05:30. Following the explicit pause, the user authorizes only this metadata finalization and intentionally ends generation at 42 entries. The current deliverable is the 42-entry Word review edition with the established closing pages. The former 100-entry generation target is SUPERSEDED for this delivery; it is no longer the active credit-blocked objective. The earlier credit failure and incomplete-100 checkpoints remain historical evidence, not the current completion criterion.

Further generation is DEFERRED until author feedback and a new explicit user go-ahead. No paid calls, API calls, new expenses, model substitutions or code changes are authorized by this scope update. Preserve all five existing model assignments and the established first nine pages and closing. This documentation sidecar does not restart any process.

Final export/Word QA remains PENDING with the export agent. Do not claim final rendering success, verified preservation hashes, artifact delivery or author approval without the parent's final QA evidence. The parent will provide that evidence; this sidecar will wait for the update rather than undertake further work.

- [x] Record the user's intentional generation stop at 42 entries and supersession of the 100-entry target for the current delivery.
- [x] Set current deliverable to the 42-entry Word review edition with the established closing pages; retain the protected first nine pages and all five model assignments.
- [x] Defer all further generation until author feedback and a new explicit user go-ahead; no API calls, new expenses or code changes.
- [ ] Export agent/parent: finish final Word review-file QA, closing-page checks and protected-document verification; PENDING.
- [ ] Parent: provide final artifact/QA evidence before final-delivery claims. Author approval remains separate and PENDING.

Earlier unchecked tasks to reach 100 entries or resolve credit for immediate generation are superseded/deferred by this explicit user decision. They are retained above solely as historical checkpoints.


### 2026-11-18 — Final 42-entry Word review edition READY / DELIVERED; QA PASS

Recorded 2026-11-18T21:32:37+05:30; final QA evidence supplied by the parent. The intentionally scoped 42-entry Word review edition is READY / DELIVERED. Final QA PASS: 157 pages, all visually covered; 20/20 protected-page pixel checks passed; all 42 formulas and 84 case records unchanged; all orphan headings fixed. This sidecar records the supplied final evidence rather than claiming to have rerun the visual inspection.

Delivered Word review file: `deliverables/20261118-agentic-research/Udyam_Sutre_Agentic_Review_042_20261118_Reviewed.docx`

SHA-256: `2ccd7877111fb58ee23162ff4d3d71b6e9e70704f5d4de891be70ecaa64aee86`

QA receipt: `logs/author-research-generation-20261118/final-v26-qa/checkpoint-042-final-02/delivery-qa.json`

Generation ENDED BY USER at 42 entries. The former 100-entry target was superseded for this delivery; no 100-entry completion is claimed. Further generation remains deferred until author feedback and new explicit user authorization. All five model assignments remain unchanged, and the established opening/closing preservation requirement is supported by the reported protected-page checks.

Author/scholar review and approval remain PENDING. Technical delivery/QA success is not publication approval or blanket certification of interpretation or originality. This finalization updates documentation only: no API calls, expenses, generation restart or code changes.

- [x] Finalize the user-scoped 42-entry Word review edition as READY / DELIVERED.
- [x] Record final QA PASS: 157 visually covered pages, 20/20 protected pixel checks, 42 formulas and 84 case records unchanged, all orphan headings fixed.
- [x] Record the exact delivered DOCX path, SHA-256 and `delivery-qa.json` receipt above.
- [x] Close generation as ENDED BY USER at 42; retain the superseded 100-entry target as history only.
- [x] Supersede earlier pending final-export/QA checkpoints with this parent-supplied final QA evidence.
- [ ] Author/scholar review and approval remain PENDING; further generation awaits author feedback and new explicit user authorization.
